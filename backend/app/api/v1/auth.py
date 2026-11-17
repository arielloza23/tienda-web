from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest, AuthMessage
from app.services import password_reset_service
from app.schemas.user import UserRead
from app.services.user_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
        )
    return TokenResponse(access_token=create_access_token(user.id, token_version=user.token_version))


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/forgot-password", response_model=AuthMessage, status_code=202)
def forgot_password(payload: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not password_reset_service.is_configured():
        raise HTTPException(status_code=503, detail="La recuperación por correo todavía no está configurada.")
    if password_reset_service.allow_request(request.client.host if request.client else "unknown"):
        pending = password_reset_service.request_password_reset(db, str(payload.email))
        if pending is not None:
            background_tasks.add_task(password_reset_service.deliver_reset_email, *pending)
    return AuthMessage(message=password_reset_service.FORGOT_MESSAGE)


@router.post("/reset-password", response_model=AuthMessage)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        password_reset_service.reset_password(db, payload.token, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthMessage(message="Contraseña actualizada. Inicia sesión con tu nueva contraseña.")
