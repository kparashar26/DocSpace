
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.models.role import Role
from app.schemas.auth import UserRegister


def register_user(db: Session, user_data: UserRegister) -> User:
    email = str(user_data.email).strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise ValueError("Email is already registered")

    # Public registrations always receive the viewer role.
    viewer_role = db.scalar(
        select(Role).where(Role.name == "viewer")
    )

    if not viewer_role:
        raise RuntimeError(
            "Viewer role is missing from the roles table."
        )

    new_user = User(
        name=user_data.name.strip(),
        email=email,
        password_hash=hash_password(user_data.password),
        role_id=viewer_role.id,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()
        raise ValueError("Email is already registered")

    return new_user


def login_user(db: Session, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(User.email == normalized_email)
    )

    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(subject=str(user.id))

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }
