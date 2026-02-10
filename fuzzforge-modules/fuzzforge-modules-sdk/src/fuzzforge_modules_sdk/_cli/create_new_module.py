from __future__ import annotations

from importlib.resources import files
from shutil import copytree, ignore_patterns
from typing import TYPE_CHECKING

from tomlkit import dumps, parse

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable
    from pathlib import Path

    from tomlkit import TOMLDocument


def create_new_module(name: str, directory: Path) -> None:
    source: Traversable = files("fuzzforge_modules_sdk").joinpath("templates").joinpath("fuzzforge-module-template")
    destination: Path = directory.joinpath(name)  # TODO: sanitize path
    copytree(
        src=str(source),
        dst=destination,
        ignore=ignore_patterns("__pycache__", "*.egg-info", "*.pyc", ".mypy_cache", ".ruff_cache", ".venv"),
    )

    # update the file 'pyproject.toml'
    path: Path = destination.joinpath("pyproject.toml")
    data: TOMLDocument = parse(path.read_text())
    data["project"]["name"] = name  # type: ignore[index]
    del data["tool"]["uv"]["sources"]  # type: ignore[index, union-attr]
    path.write_text(dumps(data))
