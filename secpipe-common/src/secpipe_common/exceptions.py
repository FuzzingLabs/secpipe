from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class SecPipeError(Exception):
    """Base exception for all SecPipe custom exceptions.

    All domain exceptions should inherit from this base to enable
    consistent exception handling and hierarchy navigation.

    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize SecPipe error.

        :param message: Error message.
        :param details: Optional error details dictionary.

        """
        Exception.__init__(self, message)
        self.message = message
        self.details = details or {}
