import hashlib
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate

PASSWORD_HASH_ITERATIONS = 600_000


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt.hex()}${password_hash.hex()}"


def get_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id.asc()).all()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def create_user(db: Session, payload: UserCreate) -> User:
    email = payload.email.lower()
    if get_user_by_email(db, email) is not None:
        raise ValueError("Ya existe un usuario con ese correo electrónico.")

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=_hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
