from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

# Hash ficticio para que el login tarde lo mismo exista o no el correo.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password")


def get_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def create_user(db: Session, payload: UserCreate, role: UserRole = UserRole.CUSTOMER) -> User:
    email = payload.email.lower()
    if get_user_by_email(db, email) is not None:
        raise ValueError("Ya existe un usuario con ese correo electrónico.")

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=role.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
