from enum import StrEnum


class ExecutionStatus(StrEnum):
    PENDING = "pending"      # async, waiting for the worker (or retrying)
    SUCCEEDED = "succeeded"
    FAILED = "failed"        # gave up after max attempts
    SKIPPED = "skipped"      # action type no longer exists
    