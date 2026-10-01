from enum import StrEnum


class WorkflowEvent(StrEnum):
    SUBMITTED = "submitted"
    STEP_APPROVED = "step_approved"
    STEP_REJECTED = "step_rejected"
    APPROVED = "approved"      # all steps done
    REJECTED = "rejected"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    TASK_ASSIGNED = "task_assigned"