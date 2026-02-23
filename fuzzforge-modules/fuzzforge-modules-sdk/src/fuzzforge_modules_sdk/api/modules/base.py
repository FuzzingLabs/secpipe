from abc import ABC, abstractmethod
import json
import signal
import threading
import time
from datetime import datetime, timezone
from shutil import rmtree
from typing import TYPE_CHECKING, Any, Final, final

from structlog import get_logger

from fuzzforge_modules_sdk.api.constants import (
    PATH_TO_ARTIFACTS,
    PATH_TO_INPUT,
    PATH_TO_LOGS,
    PATH_TO_RESULTS,
)
from fuzzforge_modules_sdk.api.exceptions import FuzzForgeModuleError
from fuzzforge_modules_sdk.api.models import (
    FuzzForgeModuleArtifact,
    FuzzForgeModuleArtifacts,
    FuzzForgeModuleInputBase,
    FuzzForgeModuleOutputBase,
    FuzzForgeModuleResource,
    FuzzForgeModuleResults,
    FuzzForgeModuleStatus,
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

    #: Event set when stop is requested (SIGTERM received).
    #: Using :class:`threading.Event` so multi-threaded modules can
    #: efficiently wait on it via :pymethod:`threading.Event.wait`.
    __stop_requested: threading.Event

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
        self.__stop_requested = threading.Event()

        # Register SIGTERM handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_sigterm)

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
    def is_stop_requested(self) -> bool:
        """Check if stop was requested (SIGTERM received).

        Long-running modules should check this periodically and exit gracefully
        when True. Results will be written automatically on SIGTERM.

        The underlying :class:`threading.Event` can be obtained via
        :meth:`stop_event` for modules that need to *wait* on it.

        :returns: True if SIGTERM was received.

        """
        return self.__stop_requested.is_set()

    @final
    def stop_event(self) -> threading.Event:
        """Return the stop :class:`threading.Event`.

        Multi-threaded modules can use ``self.stop_event().wait(timeout)``
        instead of polling :meth:`is_stop_requested` in a busy-loop.

        :returns: The threading event that is set on SIGTERM.

        """
        return self.__stop_requested

    @final
    def _handle_sigterm(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM signal for graceful shutdown.

        Sets the stop event and emits a final progress update, then returns.
        The normal :meth:`main` lifecycle (run → cleanup → write results) will
        complete as usual once :meth:`_run` observes :meth:`is_stop_requested`
        and returns, giving the module a chance to do any last-minute work
        before the process exits.

        :param signum: Signal number.
        :param frame: Current stack frame.

        """
        self.__stop_requested.set()
        self.get_logger().info("received SIGTERM, stopping after current operation")

        # Emit final progress update
        self.emit_progress(
            progress=100,
            status=FuzzForgeModuleStatus.STOPPED,
            message="Module stopped by orchestrator (SIGTERM)",
        )

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
        status: FuzzForgeModuleStatus = FuzzForgeModuleStatus.RUNNING,
        message: str = "",
        metrics: dict[str, Any] | None = None,
        current_task: str = "",
    ) -> None:
        """Emit a structured progress event to stdout (JSONL).

        Progress is written as a single JSON line to stdout so that the
        orchestrator can capture it via ``kubectl logs`` without requiring
        any file-system access inside the container.

        :param progress: Progress percentage (0-100).
        :param status: Current module status.
        :param message: Human-readable status message.
        :param metrics: Dictionary of metrics (e.g., {"executions": 1000, "coverage": 50}).
        :param current_task: Name of the current task being performed.

        """
        self.emit_event(
            "progress",
            status=status.value,
            progress=max(0, min(100, progress)),
            message=message,
            current_task=current_task,
            metrics=metrics or {},
        )

    @final
    def emit_event(self, event: str, **data: Any) -> None:
        """Emit a structured event to stdout as a single JSONL line.

        All module events (including progress updates) are written to stdout
        so the orchestrator can stream them in real time via ``kubectl logs``.

        :param event: Event type (e.g., ``"crash_found"``, ``"target_started"``,
            ``"progress"``, ``"metrics"``).
        :param data: Additional event data as keyword arguments.

        """
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(self.get_elapsed_seconds(), 2),
            "module": self.__name,
            "event": event,
            **data,
        }
        print(json.dumps(event_data), flush=True)

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
        """Execute the module lifecycle: prepare → run → cleanup → write results."""
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
        PATH_TO_RESULTS.parent.mkdir(exist_ok=True, parents=True)
        PATH_TO_RESULTS.write_bytes(output.model_dump_json().encode("utf-8"))

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
