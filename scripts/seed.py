import asyncio
import getpass

from sqlalchemy import select

from app.core.permissions import PERMISSIONS
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.modules.users.models import Permission, Role, User


async def seed() -> None:
    async with SessionLocal() as db:
        # 1. Permissions (insert only missing ones)
        existing = {p.code: p for p in await db.scalars(select(Permission))}
        for code, desc in PERMISSIONS.items():
            if code not in existing:
                existing[code] = Permission(code=code, description=desc)
                db.add(existing[code])

        # 2. Admin role with every permission
        admin = await db.scalar(select(Role).where(Role.name == "Admin"))
        if not admin:
            admin = Role(name="Admin", description="Full access")
            db.add(admin)
        admin.permissions = list(existing.values())

        # 3. First superuser
        if not await db.scalar(select(User).where(User.is_superuser.is_(True))):
            email = input("Superuser email: ").strip().lower()
            full_name = input("Full name: ").strip()
            password = getpass.getpass("Password (min 8 chars): ")
            if len(password) < 8:
                raise SystemExit("Password too short")
            db.add(
                User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    is_superuser=True,
                    roles=[admin],
                )
            )
            print(f"Created superuser {email}")

        await db.commit()
        print(f"Seeded {len(existing)} permissions and the Admin role")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
