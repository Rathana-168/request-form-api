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
    TASK_REMINDER = "task_reminder"
    TASK_ESCALATED = "task_escalated"
    TASK_REASSIGNED = "task_reassigned"


class EscalationAction(StrEnum):
    NOTIFY_MANAGER = "notify_manager"      # tell the approver's manager, task stays
    REASSIGN_MANAGER = "reassign_manager"  # move the task to the approver's manager
