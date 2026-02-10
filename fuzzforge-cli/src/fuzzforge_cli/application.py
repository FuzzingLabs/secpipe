"""FuzzForge CLI application."""

from pathlib import Path
from typing import Annotated

from fuzzforge_runner import Runner, Settings
from typer import Context as TyperContext
from typer import Option, Typer

from fuzzforge_cli.commands import mcp, modules, projects
from fuzzforge_cli.context import Context

application: Typer = Typer(
    name="fuzzforge",
    help="FuzzForge OSS - Security research orchestration platform.",
)


@application.callback()
def main(
    project_path: Annotated[
        Path,
        Option(
            "--project",
            "-p",
            envvar="FUZZFORGE_PROJECT__DEFAULT_PATH",
            help="Path to the FuzzForge project directory.",
        ),
    ] = Path.cwd(),
    modules_path: Annotated[
        Path,
        Option(
            "--modules",
            "-m",
            envvar="FUZZFORGE_MODULES_PATH",
            help="Path to the modules directory.",
        ),
    ] = Path.home() / ".fuzzforge" / "modules",
    storage_path: Annotated[
        Path,
        Option(
            "--storage",
            envvar="FUZZFORGE_STORAGE__PATH",
            help="Path to the storage directory.",
        ),
    ] = Path.home() / ".fuzzforge" / "storage",
    engine_type: Annotated[
        str,
        Option(
            "--engine",
            envvar="FUZZFORGE_ENGINE__TYPE",
            help="Container engine type (docker or podman).",
        ),
    ] = "docker",
    engine_socket: Annotated[
        str,
        Option(
            "--socket",
            envvar="FUZZFORGE_ENGINE__SOCKET",
            help="Container engine socket path.",
        ),
    ] = "",
    context: TyperContext = None,  # type: ignore[assignment]
) -> None:
    """FuzzForge OSS - Security research orchestration platform.

    Execute security research modules in isolated containers.

    """
    from fuzzforge_runner.settings import EngineSettings, ProjectSettings, StorageSettings

    settings = Settings(
        engine=EngineSettings(
            type=engine_type,  # type: ignore[arg-type]
            socket=engine_socket,
        ),
        storage=StorageSettings(
            path=storage_path,
        ),
        project=ProjectSettings(
            default_path=project_path,
            modules_path=modules_path,
        ),
    )

    runner = Runner(settings)

    context.obj = Context(
        runner=runner,
        project_path=project_path,
    )


application.add_typer(mcp.application)
application.add_typer(modules.application)
application.add_typer(projects.application)
