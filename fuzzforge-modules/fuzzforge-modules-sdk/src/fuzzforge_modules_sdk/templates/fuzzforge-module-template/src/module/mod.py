from __future__ import annotations

from typing import TYPE_CHECKING

from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResults
from fuzzforge_modules_sdk.api.modules.base import FuzzForgeModule

from module.models import Input, Output

if TYPE_CHECKING:
    from fuzzforge_modules_sdk.api.models import FuzzForgeModuleResource, FuzzForgeModulesSettingsType


class Module(FuzzForgeModule):
    """TODO."""

    def __init__(self) -> None:
        """Initialize an instance of the class."""
        name: str = "FIXME"
        version: str = "FIXME"
        FuzzForgeModule.__init__(self, name=name, version=version)

    @classmethod
    def _get_input_type(cls) -> type[Input]:
        """TODO."""
        return Input

    @classmethod
    def _get_output_type(cls) -> type[Output]:
        """TODO."""
        return Output

    def _prepare(self, settings: FuzzForgeModulesSettingsType) -> None:
        """TODO.

        :param settings: TODO.

        """

    def _run(self, resources: list[FuzzForgeModuleResource]) -> FuzzForgeModuleResults:  # noqa: ARG002
        """TODO.

        :param resources: TODO.
        :returns: TODO.

        """
        return FuzzForgeModuleResults.SUCCESS

    def _cleanup(self, settings: FuzzForgeModulesSettingsType) -> None:
        """TODO.

        :param settings: TODO.

        """
