# Import every module's models here so Alembic can detect them.
# e.g. from app.modules.users.models import User  # noqa: F401
from app.db.base import Base  # noqa: F401
from app.modules.users.models import Department, Permission, Role, User  # noqa: F401
from app.modules.forms.models import Form
