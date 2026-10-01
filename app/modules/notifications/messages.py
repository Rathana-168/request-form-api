from app.modules.notifications.models import NotificationType
from app.workflow.enums import WorkflowEvent

# event -> (type, title, body). Placeholders: {no} request number, {form} form name,
# {actor} who acted, {step} step name, {comment} approver's comment
MESSAGES: dict[WorkflowEvent, tuple[NotificationType, str, str | None]] = {
    WorkflowEvent.TASK_ASSIGNED: (
        NotificationType.TASK_ASSIGNED,
        "{no} needs your approval",
        "{form} from {requester} ({step})",
    ),
    WorkflowEvent.APPROVED: (
        NotificationType.APPROVED,
        "{no} was approved",
        "Your {form} was fully approved.",
    ),
    WorkflowEvent.REJECTED: (
        NotificationType.REJECTED,
        "{no} was rejected",
        "Rejected by {actor}. {comment}",
    ),
    WorkflowEvent.RETURNED: (
        NotificationType.RETURNED,
        "{no} was returned",
        "Returned by {actor} for changes. {comment}",
    ),
    WorkflowEvent.CANCELLED: (
        NotificationType.CANCELLED,
        "{no} was cancelled",
        "{requester} cancelled this request.",
    ),
    WorkflowEvent.TASK_REMINDER: (
        NotificationType.TASK_REMINDER,
        "{no} is still waiting for your approval",
        "{form} from {requester} ({step})",
    ),
    WorkflowEvent.TASK_ESCALATED: (
        NotificationType.TASK_ESCALATED,
        "{no} is overdue",
        "{form} from {requester} has waited {hours}h for {approver} ({step}).",
    ),
    WorkflowEvent.TASK_REASSIGNED: (
        NotificationType.TASK_REASSIGNED,
        "{no} was reassigned",
        "Overdue with {approver} after {hours}h, now assigned to their manager ({step}).",
    ),
    WorkflowEvent.TASK_ASSIGNED_AS_PROXY: (
        NotificationType.TASK_ASSIGNED_AS_PROXY,
        "{no} needs approval on behalf of {principal}",
        "{form} from {requester} ({step}). You are {principal}'s proxy.",
    ),
    WorkflowEvent.ACTED_BY_PROXY: (
        NotificationType.ACTED_BY_PROXY,
        "{proxy} {verb} {no} on your behalf",
        "{form} from {requester} ({step}).",
    ),
}
