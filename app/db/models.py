# Import every module's models here so Alembic can detect them.
# e.g. from app.modules.users.models import User
from app.db.base import Base  # noqa: F401
from app.modules.approvals.models import ApprovalProxy, ApprovalTask  # noqa: F401
from app.modules.comments.models import RequestComment  # noqa: F401
from app.modules.forms.models import Form  # noqa: F401
from app.modules.forms.registry import load_plugins
from app.modules.notifications.models import Notification  # noqa: F401
from app.modules.org.models import Department  # noqa: F40
from app.modules.requests.models import (  # noqa: F401
    Request,
    RequestCounter,
    RequestHistory,
)
from app.modules.users.models import (  # noqa: F401
    Department,
    EmployeeProfile,
    Permission,
    Role,
    User,
)
from app.rules.models import RuleExecution, WorkflowRule  # noqa: F401
from app.workflow.models import Workflow, WorkflowStep  # noqa: F401
from app.events.models import OutboxEvent  # noqa: F401

load_plugins()  # registers every form plugin's table