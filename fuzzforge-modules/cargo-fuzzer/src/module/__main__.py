from typing import TYPE_CHECKING

from fuzzforge_modules_sdk.api import logs

from module.mod import Module

if TYPE_CHECKING:
    from fuzzforge_modules_sdk.api.modules.base import FuzzForgeModule


def main() -> None:
    """TODO."""
    logs.configure()
    module: FuzzForgeModule = Module()
    module.main()


if __name__ == "__main__":
    main()
