"""Seed a fresh database with permissions, roles, departments, test users,
forms and their workflows. Safe to run more than once (skips what exists).

    uv run python -m scripts.seed
"""

import asyncio

from sqlalchemy import select

from app.core.permissions import PERMISSIONS
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.modules.forms.models import Form
from app.modules.forms.registry import load_plugins
from app.modules.users.models import Department, Permission, Role, User
from app.workflow.enums import EscalationAction
from app.workflow.models import ApprovalMode, AssigneeType, Workflow, WorkflowStep

DEFAULT_PASSWORD = "Passw0rd!"  # testing only; auth uses the `cif` header

ROLES = {
    "Admin": ("Full access", "*"),
    "HR": ("HR approvers", ["request:read", "approval:act"]),
    "Employee": ("Can submit requests", ["request:create", "request:read"]),
}

DEPARTMENTS = [  # (code, name)
    ("HR", "Human Resources"),
    ("IT", "Information Technology"),
]

# email (= cif while testing), name, department, manager email, roles, superuser
USERS = [
    ("admin@example.com", "System Admin", None, None, ["Admin"], True),
    ("vanna@example.com", "Vanna", "IT", None, ["Employee"], False),
    ("sokha@example.com", "Sokha", "IT", "vanna@example.com", ["Employee"], False),
    ("dara@example.com", "Dara", "IT", "sokha@example.com", ["Employee"], False),
    ("lina@example.com", "Lina", "HR", "vanna@example.com", ["Employee", "HR"], False),
    ("hugo@example.com", "Hugo", "HR", "lina@example.com", ["Employee", "HR"], False),
]

DEPARTMENT_HEADS = {"IT": "vanna@example.com", "HR": "lina@example.com"}

FORMS = {  # code -> (name, category)
    "LEAVE_REQUEST": ("Leave Request", "HR"),
    "PROXY_REQUEST": ("Proxy Request", "General"),
}

# Steps reference roles by name; resolved to ids below.
WORKFLOWS = {
    "LEAVE_REQUEST": {
        "name": "Leave approval",
        "completed_status": "approved",
        "steps": [
            dict(
                name="Manager",
                status="submitted",
                action_label="Approve",
                assignee_type=AssigneeType.REQUESTER_MANAGER,
                require_comment_on=["reject", "return"],
                remind_after_hours=24,
                escalate_after_hours=72,
                escalation_action=EscalationAction.NOTIFY_MANAGER,
            ),
            dict(
                name="Department Head",
                status="reviewed",
                action_label="Approve",
                assignee_type=AssigneeType.DEPARTMENT_HEAD,
                conditions=[{"field": "days", "op": "gt", "value": 3}],
                return_to="previous",
            ),
            dict(
                name="HR",
                status="hr_review",
                action_label="Confirm",
                assignee_type=AssigneeType.ROLE,
                role="HR",
                mode=ApprovalMode.ANY,
                remind_after_hours=8,
                escalate_after_hours=24,
                escalation_action=EscalationAction.REASSIGN_MANAGER,
            ),
        ],
    },
    "PROXY_REQUEST": {
        "name": "Proxy acknowledgement",
        "completed_status": "active",
        "steps": [
            dict(
                name="Proxy acknowledges",
                status="submitted",
                action_label="Accept",
                assignee_type=AssigneeType.FORM_FIELD,
                assignee_field="proxy_id",
                allow_return=False,
                require_comment_on=["reject"],
            ),
        ],
    },
}


async def seed() -> None:
    async with SessionLocal() as db:
        # 1. Permissions
        perms = {p.code: p for p in await db.scalars(select(Permission))}
        for code, desc in PERMISSIONS.items():
            if code not in perms:
                perms[code] = Permission(code=code, description=desc)
                db.add(perms[code])

        # 2. Roles
        roles = {r.name: r for r in await db.scalars(select(Role))}
        for name, (desc, codes) in ROLES.items():
            role = roles.get(name) or Role(name=name, description=desc)
            role.permissions = (
                list(perms.values())
                if codes == "*"
                else [perms[c] for c in codes if c in perms]
            )
            db.add(role)
            roles[name] = role

        # 3. Departments (heads set after users exist)
        depts = {d.code: d for d in await db.scalars(select(Department))}
        for code, name in DEPARTMENTS:
            if code not in depts:
                depts[code] = Department(code=code, name=name)
                db.add(depts[code])
        await db.flush()

        # 4. Users (two passes: create, then link managers)
        users = {u.email: u for u in await db.scalars(select(User))}
        for email, full_name, dept, _, role_names, is_super in USERS:
            if email not in users:
                users[email] = User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(DEFAULT_PASSWORD),
                    is_superuser=is_super,
                    department_id=depts[dept].id if dept else None,
                    roles=[roles[r] for r in role_names],
                )
                db.add(users[email])
        await db.flush()
        for email, *_, manager, _, _ in USERS:
            if manager:
                users[email].manager_id = users[manager].id
        for code, email in DEPARTMENT_HEADS.items():
            depts[code].head_id = users[email].id

        # 5. Forms (only codes that have a plugin)
        plugins = set(load_plugins())
        admin = users["admin@example.com"]
        existing_forms = set(await db.scalars(select(Form.code)))
        for code, (name, category) in FORMS.items():
            if code not in plugins:
                print(f"Skip form {code}: no plugin found")
                continue
            if code not in existing_forms:
                db.add(
                    Form(
                        code=code, name=name, category=category, created_by_id=admin.id
                    )
                )
        await db.flush()

        # 6. Workflows (skip forms that already have an active one)
        active = set(
            await db.scalars(select(Workflow.form_code).where(Workflow.is_active))
        )
        registered = set(await db.scalars(select(Form.code)))
        for code, wf in WORKFLOWS.items():
            if code in active or code not in registered:
                continue
            steps = []
            for no, s in enumerate(wf["steps"], start=1):
                s = dict(s)
                role = s.pop("role", None)
                steps.append(
                    WorkflowStep(
                        step_no=no,
                        assignee_role_id=roles[role].id if role else None,
                        **s,
                    )
                )
            db.add(
                Workflow(
                    form_code=code,
                    name=wf["name"],
                    completed_status=wf["completed_status"],
                    is_active=True,
                    steps=steps,
                )
            )

        await db.commit()
        print(
            f"Seeded {len(perms)} permissions, {len(roles)} roles, {len(users)} users"
        )
        print(
            f"Test users log in with header  cif: <email>  (password: {DEFAULT_PASSWORD})"
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
