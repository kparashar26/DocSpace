
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.api.deps import require_permission
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User


def test_permissions():
    db = SessionLocal()

    test_cases = [
        ("admin", "documents.upload", True),
        ("editor", "documents.upload", True),
        ("viewer", "documents.upload", False),

        ("admin", "documents.view", True),
        ("editor", "documents.view", True),
        ("viewer", "documents.view", True),

        ("admin", "users.manage", True),
        ("editor", "users.manage", False),
        ("viewer", "users.manage", False),
    ]

    passed = 0
    failed = 0

    try:
        roles = {
            role.name: role
            for role in db.scalars(select(Role)).all()
        }

        for role_name, permission_code, expected in test_cases:

            role = roles.get(role_name)

            if role is None:
                print(f"FAIL: Role '{role_name}' not found")
                failed += 1
                continue

            test_user = User(
                id=uuid4(),
                name="Permission Test",
                email=f"{role_name}-test@example.com",
                password_hash="not-used",
                role_id=role.id,
            )

            checker = require_permission(permission_code)

            try:
                checker(current_user=test_user, db=db)
                actual = True
            except HTTPException as error:
                actual = False if error.status_code == 403 else None

            if actual == expected:
                print(
                    f"PASS: {role_name} -> {permission_code}"
                )
                passed += 1
            else:
                print(
                    f"FAIL: {role_name} -> {permission_code} "
                    f"(Expected: {expected}, Got: {actual})"
                )
                failed += 1

        print("\nPERMISSION TEST SUMMARY")
        print("-----------------------")
        print("Passed:", passed)
        print("Failed:", failed)
        print("Total:", passed + failed)

    finally:
        db.close()


if __name__ == "__main__":
    test_permissions()
