from ldap3 import ALL, Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


logger = get_logger(__name__)

class LdapAuthProvider:
    def __init__(self, users: UserRepository):
        self.users = users

    async def authenticate(self, staff_id: str, password: str) -> User | None:
        if not staff_id or not password:   # empty password = anonymous bind, always "succeeds"
            return None
        if not await run_in_threadpool(self._ldap_check, staff_id, password):
            return None
        return await self.users.get_by_staff_id(staff_id)

    def _ldap_check(self, staff_id: str, password: str) -> bool:
        settings = get_settings()
        server = Server(settings.LDAP_URL, get_info=ALL, connect_timeout=settings.LDAP_TIMEOUT)
        try:
            # 1) find the user's DN with the service account
            with Connection(server, settings.LDAP_BIND_DN, settings.LDAP_BIND_PASSWORD,
                            auto_bind=True) as svc:
                flt = f"({settings.LDAP_STAFF_ID_ATTR}={escape_filter_chars(staff_id)})"
                svc.search(settings.LDAP_BASE_DN, flt, attributes=[])
                if len(svc.entries) != 1:
                    return False
                user_dn = svc.entries[0].entry_dn

            # 2) verify the password by binding as the user
            with Connection(server, user_dn, password, auto_bind=True):
                return True
        except LDAPException as e:
            logger.warning("LDAP auth failed for %s: %s", staff_id, e)
            return False