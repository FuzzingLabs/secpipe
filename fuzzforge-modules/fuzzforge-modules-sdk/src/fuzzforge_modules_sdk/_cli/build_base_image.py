from importlib.resources import files
from pathlib import Path
from shutil import copyfile, copytree
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

import os

from podman import PodmanClient
from tomlkit import TOMLDocument, parse

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable


def _get_default_podman_socket() -> str:
    """Get the default Podman socket path for the current user."""
    uid = os.getuid()
    return f"unix:///run/user/{uid}/podman/podman.sock"


PATH_TO_SOURCES: Path = Path(__file__).parent.parent


def _build_podman_image(directory: Path, tag: str, socket: str | None = None) -> None:
    if socket is None:
        socket = _get_default_podman_socket()
    with PodmanClient(base_url=socket) as client:
        client.images.build(
            dockerfile="Dockerfile",
            nocache=True,
            path=directory,
            tag=tag,
        )


def build_base_image(engine: Literal["podman"], socket: str | None = None) -> None:
    with TemporaryDirectory() as directory:
        path_to_assets: Traversable = files("fuzzforge_modules_sdk").joinpath("assets")
        copyfile(
            src=str(path_to_assets.joinpath("Dockerfile")),
            dst=Path(directory).joinpath("Dockerfile"),
        )
        copyfile(
            src=str(path_to_assets.joinpath("pyproject.toml")),
            dst=Path(directory).joinpath("pyproject.toml"),
        )
        copytree(src=str(PATH_TO_SOURCES), dst=Path(directory).joinpath("src").joinpath(PATH_TO_SOURCES.name))

        # update the file 'pyproject.toml'
        path: Path = Path(directory).joinpath("pyproject.toml")
        data: TOMLDocument = parse(path.read_text())
        name: str = data["project"]["name"]  # type: ignore[assignment, index]
        version: str = data["project"]["version"]  # type: ignore[assignment, index]
        tag: str = f"{name}:{version}"

        match engine:
            case "podman":
                _build_podman_image(
                    directory=Path(directory),
                    socket=socket,
                    tag=tag,
                )
            case _:
                message: str = f"unsupported engine '{engine}'"
                raise Exception(message)  # noqa: TRY002
