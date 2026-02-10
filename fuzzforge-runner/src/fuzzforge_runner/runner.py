"""FuzzForge Runner - Main runner interface.

This module provides the high-level interface for FuzzForge OSS,
coordinating module execution, workflow orchestration, and storage.

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from fuzzforge_runner.executor import ModuleExecutor
from fuzzforge_runner.orchestrator import (
    StepResult,
    WorkflowDefinition,
    WorkflowOrchestrator,
    WorkflowResult,
    WorkflowStep,
)
from fuzzforge_runner.settings import Settings
from fuzzforge_runner.storage import LocalStorage

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger


def get_logger() -> BoundLogger:
    """Get structlog logger instance.

    :returns: Configured structlog logger.

    """
    from structlog import get_logger  # noqa: PLC0415

    return cast("BoundLogger", get_logger())


@dataclass
class ModuleInfo:
    """Information about an available module."""

    #: Module identifier/name.
    identifier: str

    #: Module description.
    description: str | None = None

    #: Module version.
    version: str | None = None

    #: Whether module image exists locally.
    available: bool = True

    #: Module category (analyzer, validator, fuzzer, reporter).
    category: str | None = None

    #: Target programming language (e.g., "rust", "python").
    language: str | None = None

    #: Pipeline stage name (e.g., "analysis", "fuzzing").
    pipeline_stage: str | None = None

    #: Numeric order in pipeline for sorting.
    pipeline_order: int | None = None

    #: Module identifiers that must run before this one.
    dependencies: list[str] | None = None

    #: Whether module supports continuous/background execution.
    continuous_mode: bool = False

    #: Expected runtime (e.g., "30s", "5m", "continuous").
    typical_duration: str | None = None

    #: Typical use cases and scenarios for this module.
    use_cases: list[str] | None = None

    #: Input requirements (e.g., ["rust-source-code", "Cargo.toml"]).
    input_requirements: list[str] | None = None

    #: Output artifacts produced (e.g., ["fuzzable_functions.json"]).
    output_artifacts: list[str] | None = None


class Runner:
    """Main FuzzForge Runner interface.

    Provides a unified interface for:
    - Module discovery and execution
    - Workflow orchestration
    - Project and asset management

    This is the primary entry point for OSS users and the MCP server.

    """

    #: Runner settings.
    _settings: Settings

    #: Module executor.
    _executor: ModuleExecutor

    #: Local storage backend.
    _storage: LocalStorage

    #: Workflow orchestrator.
    _orchestrator: WorkflowOrchestrator

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize an instance of the class.

        :param settings: Runner settings. If None, loads from environment.

        """
        self._settings = settings or Settings()
        self._executor = ModuleExecutor(self._settings)
        self._storage = LocalStorage(self._settings.storage.path)
        self._orchestrator = WorkflowOrchestrator(self._executor, self._storage)

    @property
    def settings(self) -> Settings:
        """Get runner settings.

        :returns: Current settings instance.

        """
        return self._settings

    @property
    def storage(self) -> LocalStorage:
        """Get storage backend.

        :returns: Storage instance.

        """
        return self._storage

    # -------------------------------------------------------------------------
    # Project Management
    # -------------------------------------------------------------------------

    def init_project(self, project_path: Path) -> Path:
        """Initialize a new project.

        Creates necessary storage directories for a project.

        :param project_path: Path to the project directory.
        :returns: Path to the project storage directory.

        """
        logger = get_logger()
        logger.info("initializing project", path=str(project_path))
        return self._storage.init_project(project_path)

    def set_project_assets(self, project_path: Path, assets_path: Path) -> Path:
        """Set source path for a project (no copying).

        Just stores a reference to the source directory.
        The source is mounted directly into containers at runtime.

        :param project_path: Path to the project directory.
        :param assets_path: Path to source directory.
        :returns: The assets path (unchanged).

        """
        logger = get_logger()
        logger.info("setting project assets", project=str(project_path), assets=str(assets_path))
        return self._storage.set_project_assets(project_path, assets_path)

    # -------------------------------------------------------------------------
    # Module Discovery
    # -------------------------------------------------------------------------

    def list_modules(self) -> list[ModuleInfo]:
        """List available modules.

        Discovers modules from the configured modules directory.

        :returns: List of available modules.

        """
        logger = get_logger()
        modules: list[ModuleInfo] = []

        modules_path = self._settings.modules_path
        if not modules_path.exists():
            logger.warning("modules directory not found", path=str(modules_path))
            return modules

        # Look for module directories (each should have a Dockerfile or be a built image)
        for item in modules_path.iterdir():
            if item.is_dir():
                # Check for module markers
                has_dockerfile = (item / "Dockerfile").exists()
                has_pyproject = (item / "pyproject.toml").exists()

                if has_dockerfile or has_pyproject:
                    modules.append(
                        ModuleInfo(
                            identifier=item.name,
                            available=has_dockerfile,
                        )
                    )

        logger.info("discovered modules", count=len(modules))
        return modules

    def list_module_images(
        self,
        filter_prefix: str = "fuzzforge-",
        include_all_tags: bool = True,
    ) -> list[ModuleInfo]:
        """List available module images from the container engine.

        Uses the container engine API to discover built module images.
        Reads metadata from pyproject.toml inside each image.

        :param filter_prefix: Prefix to filter images (default: "fuzzforge-").
        :param include_all_tags: If True, include all image tags, not just 'latest'.
        :returns: List of available module images.

        """
        import tomllib  # noqa: PLC0415

        logger = get_logger()
        modules: list[ModuleInfo] = []
        seen: set[str] = set()

        # Infrastructure images to skip
        skip_images = {"fuzzforge-modules-sdk", "fuzzforge-runner", "fuzzforge-api"}

        engine = self._executor._get_engine()
        images = engine.list_images(filter_prefix=filter_prefix)

        for image in images:
            # Only include :latest images unless include_all_tags is set
            if not include_all_tags and image.tag != "latest":
                continue

            # Extract module name from repository
            full_name = image.repository.split("/")[-1]

            # Skip infrastructure images
            if full_name in skip_images:
                continue

            # Extract clean module name (remove fuzzforge-module- prefix if present)
            if full_name.startswith("fuzzforge-module-"):
                module_name = full_name.replace("fuzzforge-module-", "")
            else:
                module_name = full_name

            # Skip UUID-like names (temporary/broken containers)
            if module_name.count("-") >= 4 and len(module_name) > 30:
                continue

            # Add unique modules
            if module_name not in seen:
                seen.add(module_name)

                # Read metadata from pyproject.toml inside the image
                image_ref = f"{image.repository}:{image.tag}"
                module_meta = self._get_module_metadata_from_image(engine, image_ref)

                # Get basic info from pyproject.toml [project] section
                project_info = module_meta.get("_project", {})
                fuzzforge_meta = module_meta.get("module", {})

                modules.append(
                    ModuleInfo(
                        identifier=fuzzforge_meta.get("identifier", module_name),
                        description=project_info.get("description"),
                        version=project_info.get("version", image.tag),
                        available=True,
                        category=fuzzforge_meta.get("category"),
                        language=fuzzforge_meta.get("language"),
                        pipeline_stage=fuzzforge_meta.get("pipeline_stage"),
                        pipeline_order=fuzzforge_meta.get("pipeline_order"),
                        dependencies=fuzzforge_meta.get("dependencies", []),
                        continuous_mode=fuzzforge_meta.get("continuous_mode", False),
                        typical_duration=fuzzforge_meta.get("typical_duration"),
                        use_cases=fuzzforge_meta.get("use_cases", []),
                        input_requirements=fuzzforge_meta.get("input_requirements", []),
                        output_artifacts=fuzzforge_meta.get("output_artifacts", []),
                    )
                )

        logger.info("listed module images", count=len(modules))
        return modules

    def _get_module_metadata_from_image(self, engine: Any, image_ref: str) -> dict:
        """Read module metadata from pyproject.toml inside a container image.

        :param engine: Container engine instance.
        :param image_ref: Image reference (e.g., "fuzzforge-rust-analyzer:latest").
        :returns: Dict with module metadata from [tool.fuzzforge] section.

        """
        import tomllib  # noqa: PLC0415

        logger = get_logger()

        try:
            # Read pyproject.toml from the image
            content = engine.read_file_from_image(image_ref, "/app/pyproject.toml")
            if not content:
                logger.debug("no pyproject.toml found in image", image=image_ref)
                return {}

            pyproject = tomllib.loads(content)

            # Return the [tool.fuzzforge] section plus [project] info
            result = pyproject.get("tool", {}).get("fuzzforge", {})
            result["_project"] = pyproject.get("project", {})
            return result

        except Exception as exc:
            logger.debug("failed to read metadata from image", image=image_ref, error=str(exc))
            return {}

    def get_module_info(self, module_identifier: str) -> ModuleInfo | None:
        """Get information about a specific module.

        :param module_identifier: Module identifier to look up.
        :returns: Module info, or None if not found.

        """
        modules = self.list_modules()
        for module in modules:
            if module.identifier == module_identifier:
                return module
        return None

    # -------------------------------------------------------------------------
    # Module Execution
    # -------------------------------------------------------------------------

    async def execute_module(
        self,
        module_identifier: str,
        project_path: Path,
        configuration: dict[str, Any] | None = None,
        assets_path: Path | None = None,
    ) -> StepResult:
        """Execute a single module.

        :param module_identifier: Module to execute.
        :param project_path: Path to the project directory.
        :param configuration: Optional module configuration.
        :param assets_path: Optional path to input assets.
        :returns: Execution result.

        """
        logger = get_logger()
        logger.info(
            "executing module",
            module=module_identifier,
            project=str(project_path),
        )

        return await self._orchestrator.execute_single_module(
            module_identifier=module_identifier,
            project_path=project_path,
            assets_path=assets_path,
            configuration=configuration,
        )

    # -------------------------------------------------------------------------
    # Workflow Execution
    # -------------------------------------------------------------------------

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        project_path: Path,
        initial_assets_path: Path | None = None,
    ) -> WorkflowResult:
        """Execute a workflow.

        :param workflow: Workflow definition with steps.
        :param project_path: Path to the project directory.
        :param initial_assets_path: Optional path to initial assets.
        :returns: Workflow execution result.

        """
        logger = get_logger()
        logger.info(
            "executing workflow",
            workflow=workflow.name,
            project=str(project_path),
            steps=len(workflow.steps),
        )

        return await self._orchestrator.execute_workflow(
            workflow=workflow,
            project_path=project_path,
            initial_assets_path=initial_assets_path,
        )

    def create_workflow(
        self,
        name: str,
        steps: list[tuple[str, dict[str, Any] | None]],
        description: str | None = None,
    ) -> WorkflowDefinition:
        """Create a workflow definition.

        Convenience method for creating workflows programmatically.

        :param name: Workflow name.
        :param steps: List of (module_identifier, configuration) tuples.
        :param description: Optional workflow description.
        :returns: Workflow definition.

        """
        workflow_steps = [
            WorkflowStep(
                module_identifier=module_id,
                configuration=config,
                name=f"step-{i}",
            )
            for i, (module_id, config) in enumerate(steps)
        ]

        return WorkflowDefinition(
            name=name,
            steps=workflow_steps,
            description=description,
        )

    # -------------------------------------------------------------------------
    # Results Management
    # -------------------------------------------------------------------------

    def get_execution_results(
        self,
        project_path: Path,
        execution_id: str,
    ) -> Path | None:
        """Get results for an execution.

        :param project_path: Path to the project directory.
        :param execution_id: Execution ID.
        :returns: Path to results archive, or None if not found.

        """
        return self._storage.get_execution_results(project_path, execution_id)

    def list_executions(self, project_path: Path) -> list[str]:
        """List all executions for a project.

        :param project_path: Path to the project directory.
        :returns: List of execution IDs.

        """
        return self._storage.list_executions(project_path)

    def extract_results(self, results_path: Path, destination: Path) -> Path:
        """Extract results archive to a directory.

        :param results_path: Path to results archive.
        :param destination: Destination directory.
        :returns: Path to extracted directory.

        """
        return self._storage.extract_results(results_path, destination)
