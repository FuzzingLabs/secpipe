from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class FuzzForgeError(Exception):
    """Base exception for all FuzzForge custom exceptions.

    All domain exceptions should inherit from this base to enable
    consistent exception handling and hierarchy navigation.

    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize FuzzForge error.

        :param message: Error message.
        :param details: Optional error details dictionary.

        """
        Exception.__init__(self, message)
        self.message = message
        self.details = details or {}
