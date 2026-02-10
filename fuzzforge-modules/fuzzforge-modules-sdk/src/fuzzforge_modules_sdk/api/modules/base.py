from abc import ABC, abstractmethod
import json
import time
from datetime import datetime, timezone
from shutil import rmtree
from typing import TYPE_CHECKING, Any, Final, final

from structlog import get_logger

from fuzzforge_modules_sdk.api.constants import (
    PATH_TO_ARTIFACTS,
    PATH_TO_INPUT,
    PATH_TO_LOGS,
    PATH_TO_PROGRESS,
    PATH_TO_RESULTS,
    PATH_TO_STREAM,
)
from fuzzforge_modules_sdk.api.exceptions import FuzzForgeModuleError
from fuzzforge_modules_sdk.api.models import (
    FuzzForgeModuleArtifact,
    FuzzForgeModuleArtifacts,
    FuzzForgeModuleInputBase,
    FuzzForgeModuleOutputBase,
    FuzzForgeModuleResource,
    FuzzForgeModuleResults,
    FuzzForgeModulesSettingsType,
)

if TYPE_CHECKING:
    from pathlib import Path

    from structlog.stdlib import BoundLogger


class FuzzForgeModule(ABC):
    """FuzzForge Modules' base."""

    __artifacts: dict[str, FuzzForgeModuleArtifact]

    #: The logger associated with the module.
    __logger: Final[BoundLogger]

    #: The name of the module.
    __name: Final[str]

    #: The version of the module.
    __version: Final[str]

    #: Start time for progress tracking.
    __start_time: float

    #: Custom output data set by the module.
    __output_data: dict[str, Any]

    def __init__(self, name: str, version: str) -> None:
        """Initialize an instance of the class.

        :param name: The name of the module.
        :param version: The version of the module.

        """
        self.__artifacts = {}
        self.__logger = get_logger("module")
        self.__name = name
        self.__version = version
        self.__start_time = time.time()
        self.__output_data = {}
        
        # Initialize streaming output files
        PATH_TO_PROGRESS.parent.mkdir(exist_ok=True, parents=True)
        PATH_TO_STREAM.parent.mkdir(exist_ok=True, parents=True)

    @final
    def get_logger(self) -> BoundLogger:
        """Return the logger associated with the module."""
        return self.__logger

    @final
    def get_name(self) -> str:
        """Return the name of the module."""
        return self.__name

    @final
    def get_version(self) -> str:
        """Return the version of the module."""
        return self.__version

    @final
    def set_output(self, **kwargs: Any) -> None:
        """Set custom output data to be included in results.json.

        Call this from _run() to add module-specific fields to the output.

        :param kwargs: Key-value pairs to include in the output.

        Example:
            self.set_output(
                total_targets=4,
                valid_targets=["target1", "target2"],
                results=[...]
            )

        """
        self.__output_data.update(kwargs)

    @final
    def emit_progress(
        self,
        progress: int,
        status: str = "running",
        message: str = "",
        metrics: dict[str, Any] | None = None,
        current_task: str = "",
    ) -> None:
        """Emit a progress update to the progress file.

        This method writes to /data/output/progress.json which can be polled
        by the orchestrator or UI to show real-time progress.

        :param progress: Progress percentage (0-100).
        :param status: Current status ("initializing", "running", "completed", "failed").
        :param message: Human-readable status message.
        :param metrics: Dictionary of metrics (e.g., {"executions": 1000, "coverage": 50}).
        :param current_task: Name of the current task being performed.

        """
        elapsed = time.time() - self.__start_time
        
        progress_data = {
            "module": self.__name,
            "version": self.__version,
            "status": status,
            "progress": max(0, min(100, progress)),
            "message": message,
            "current_task": current_task,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
        }
        
        PATH_TO_PROGRESS.write_text(json.dumps(progress_data, indent=2))

    @final
    def emit_event(self, event: str, **data: Any) -> None:
        """Emit a streaming event to the stream file.

        This method appends to /data/output/stream.jsonl which can be tailed
        by the orchestrator or UI for real-time event streaming.

        :param event: Event type (e.g., "crash_found", "target_started", "metrics").
        :param data: Additional event data as keyword arguments.

        """
        elapsed = time.time() - self.__start_time
        
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "module": self.__name,
            "event": event,
            **data,
        }
        
        # Append to stream file (create if doesn't exist)
        with PATH_TO_STREAM.open("a") as f:
            f.write(json.dumps(event_data) + "\n")

    @final
    def get_elapsed_seconds(self) -> float:
        """Return the elapsed time since module start.

        :returns: Elapsed time in seconds.

        """
        return time.time() - self.__start_time

    @final
    def _register_artifact(self, name: str, kind: FuzzForgeModuleArtifacts, description: str, path: Path) -> None:
        """Register an artifact.

        :param name: The name of the artifact.
        :param kind: The type of the artifact.
        :param description: The description of the artifact.
        :param path: The path of the artifact on the file system.

        """
        source: Path = path.resolve(strict=True)
        destination: Path = PATH_TO_ARTIFACTS.joinpath(name).resolve()
        if destination.parent != PATH_TO_ARTIFACTS:
            message: str = f"path '{destination} is not a direct descendant of path '{PATH_TO_ARTIFACTS}'"
            raise FuzzForgeModuleError(message)
        if destination.exists(follow_symlinks=False):
            if destination.is_file() or destination.is_symlink():
                destination.unlink()
            elif destination.is_dir():
                rmtree(destination)
            else:
                message = f"unable to remove resource at path '{destination}': unsupported resource type"
                raise FuzzForgeModuleError(message)
        destination.parent.mkdir(exist_ok=True, parents=True)
        source.copy(destination)
        self.__artifacts[name] = FuzzForgeModuleArtifact(
            description=description,
            kind=kind,
            name=name,
            path=path,
        )

    @final
    def main(self) -> None:
        """TODO."""
        result = FuzzForgeModuleResults.SUCCESS

        try:
            buffer: bytes = PATH_TO_INPUT.read_bytes()
            data = self._get_input_type().model_validate_json(buffer)
            self._prepare(settings=data.settings)
        except:  # noqa: E722
            self.get_logger().exception(event="exception during 'prepare' step")
            result = FuzzForgeModuleResults.FAILURE

        if result != FuzzForgeModuleResults.FAILURE:
            try:
                result = self._run(resources=data.resources)
            except:  # noqa: E722
                self.get_logger().exception(event="exception during 'run' step")
                result = FuzzForgeModuleResults.FAILURE

        if result != FuzzForgeModuleResults.FAILURE:
            try:
                self._cleanup(settings=data.settings)
            except:  # noqa: E722
                self.get_logger().exception(event="exception during 'cleanup' step")

        output = self._get_output_type()(
            artifacts=list(self.__artifacts.values()),
            logs=PATH_TO_LOGS,
            result=result,
            **self.__output_data,
        )
        buffer = output.model_dump_json().encode("utf-8")
        PATH_TO_RESULTS.parent.mkdir(exist_ok=True, parents=True)
        PATH_TO_RESULTS.write_bytes(buffer)

    @classmethod
    @abstractmethod
    def _get_input_type(cls) -> type[FuzzForgeModuleInputBase[Any]]:
        """TODO."""
        message: str = f"method '_get_input_type' is not implemented for class '{cls.__name__}'"
        raise NotImplementedError(message)

    @classmethod
    @abstractmethod
    def _get_output_type(cls) -> type[FuzzForgeModuleOutputBase]:
        """TODO."""
        message: str = f"method '_get_output_type' is not implemented for class '{cls.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def _prepare(self, settings: FuzzForgeModulesSettingsType) -> None:
        """TODO.

        :param settings: TODO.

        """
        message: str = f"method '_prepare' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def _run(self, resources: list[FuzzForgeModuleResource]) -> FuzzForgeModuleResults:
        """TODO.

        :param resources: TODO.
        :returns: TODO.

        """
        message: str = f"method '_run' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)

    @abstractmethod
    def _cleanup(self, settings: FuzzForgeModulesSettingsType) -> None:
        """TODO.

        :param settings: TODO.

        """
        message: str = f"method '_cleanup' is not implemented for class '{self.__class__.__name__}'"
        raise NotImplementedError(message)
