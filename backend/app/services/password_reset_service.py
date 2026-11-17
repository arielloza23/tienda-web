"""Tokens de un uso; ninguna URL, dirección o credencial se registra en logs."""
import hashlib
import logging
import secrets
import smtplib
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = logging.getLogger(__name__)
FORGOT_MESSAGE = "Si la cuenta está activa, recibirás instrucciones para recuperar el acceso."
INVALID_TOKEN = "El enlace no es válido o ha vencido. Solicita uno nuevo."
_rate_lock = threading.Lock()
_request_times: dict[str, list[float]] = {}


def is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from and settings.password_reset_url
                and (settings.smtp_starttls or settings.smtp_port == 465)
                and (not settings.smtp_user or settings.smtp_password))


def allow_request(identifier: str) -> bool:
    # Límite por dirección de red, sin almacenar la IP ni el correo en claro.
    key = hashlib.sha256(identifier.encode()).hexdigest()
    now = time.monotonic()
    with _rate_lock:
        for stale in [key for key, values in _request_times.items() if not values or values[-1] < now - 3600]:
            del _request_times[stale]
        values = [value for value in _request_times.get(key, []) if value > now - 3600]
        if len(values) >= 10 or len(_request_times) >= 10000 and key not in _request_times:
            return False
        _request_times[key] = values + [now]
        return True


def send_reset_email(email: str, token: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Recupera tu acceso a la tienda"
    message["From"] = settings.smtp_from
    message["To"] = email
    link = settings.password_reset_url + "?token=" + quote(token, safe="")
    message.set_content("Para cambiar tu contraseña abre este enlace (vence en 30 minutos):\n" + link + "\nSi no lo solicitaste, ignora este correo.")
    context = ssl.create_default_context()
    if settings.smtp_starttls:
        transport = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        transport = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
    with transport as smtp:
        if settings.smtp_starttls:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def request_password_reset(db: Session, email: str) -> tuple[str, str] | None:
    user = db.query(User).filter(User.email == email.lower(), User.is_active.is_(True)).with_for_update().first()
    if user is None:
        return
    now = datetime.now(timezone.utc)
    recent = db.query(PasswordResetToken.id).filter(PasswordResetToken.user_id == user.id,
        PasswordResetToken.created_at > now - timedelta(seconds=60)).first()
    if recent is not None:
        return
    # Una nueva solicitud revoca todos los enlaces anteriores.
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)).update({"used_at": now}, synchronize_session=False)
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
        created_at=now, expires_at=now + timedelta(minutes=30)))
    recipient = user.email
    db.commit()
    return recipient, token


def deliver_reset_email(email: str, token: str) -> None:
    # Tarea posterior a la respuesta; no comparte Session ni retrasa el 202.
    try:
        send_reset_email(email, token)
    except (OSError, smtplib.SMTPException, ValueError):
        # Respuesta idéntica para cuentas existentes y desconocidas.
        logger.warning("No se pudo entregar un correo de recuperación.")


def reset_password(db: Session, token: str, password: str) -> None:
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(token.encode()).hexdigest()
    record = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == digest,
        PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > now).first()
    if record is None:
        raise ValueError(INVALID_TOKEN)
    user = db.query(User).filter(User.id == record.user_id, User.is_active.is_(True)).with_for_update().first()
    if user is None:
        raise ValueError(INVALID_TOKEN)
    password_hash = hash_password(password)
    # The account lock and password hashing can outlive the remaining token lifetime.
    now = datetime.now(timezone.utc)
    consumed = db.execute(update(PasswordResetToken).where(PasswordResetToken.id == record.id,
        PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at > now).values(used_at=now).execution_options(synchronize_session=False))
    if consumed.rowcount != 1:
        db.rollback()
        raise ValueError(INVALID_TOKEN)
    user.password_hash = password_hash
    user.token_version += 1
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)).update({"used_at": now}, synchronize_session=False)
    db.commit()
