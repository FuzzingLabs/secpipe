from enum import StrEnum


class TemporalQueues(StrEnum):
    """Enumeration of available `Temporal Task Queues`."""

    #: The default task queue.
    DEFAULT = "default-task-queue"
