from app.modules.notifications.models import NotificationType
from app.workflow.enums import WorkflowEvent

# event -> (type, title, body). Placeholders: {no} request number, {form} form name,
# {actor} who acted, {step} step name, {comment} approver's comment
MESSAGES: dict[WorkflowEvent, tuple[NotificationType, str, str | None]] = {
    WorkflowEvent.TASK_ASSIGNED: (NotificationType.TASK_ASSIGNED,
                          "{no} needs your approval", "{form} from {requester} ({step})"),
    WorkflowEvent.APPROVED: (NotificationType.APPROVED,
                     "{no} was approved", "Your {form} was fully approved."),
    WorkflowEvent.REJECTED: (NotificationType.REJECTED,
                     "{no} was rejected", "Rejected by {actor}. {comment}"),
    WorkflowEvent.RETURNED: (NotificationType.RETURNED,
                     "{no} was returned", "Returned by {actor} for changes. {comment}"),
    WorkflowEvent.CANCELLED: (NotificationType.CANCELLED,
                      "{no} was cancelled", "{requester} cancelled this request."),
}