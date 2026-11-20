import hashlib
import json
import secrets
import threading
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.api.deps import require_authenticated_admin
from app.db.session import get_db
from app.schemas.analytics import AnalyticsBatch
from app.services.analytics_service import dashboard, ingest_events

router = APIRouter(prefix="/analytics", tags=["analytics"])
MAX_BODY_BYTES = 16384
_rate_lock = threading.Lock()
_rate_buckets = {}
_rate_salt = secrets.token_bytes(32)


def _limit(key: str, maximum: int, cost: int = 1):
    now = time.monotonic()
    with _rate_lock:
        for stale in [k for k, (start, _) in _rate_buckets.items() if now - start >= 60]:
            del _rate_buckets[stale]
        start, used = _rate_buckets.get(key, (now, 0))
        if used + cost > maximum or (key not in _rate_buckets and len(_rate_buckets) >= 10000):
            raise HTTPException(429, "Demasiadas interacciones.", headers={"Retry-After": "60"})
        _rate_buckets[key] = (start, used + cost)


async def bounded_batch(request: Request):
    # No se guarda IP ni user-agent; la clave de limite expira y cambia al reiniciar.
    address = request.client.host if request.client else "unknown"
    _limit("ip:" + hashlib.sha256(_rate_salt + address.encode()).hexdigest(), 120)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(413, "Lote demasiado grande.")
        body.extend(chunk)
    try:
        payload = AnalyticsBatch.model_validate(json.loads(body))
    except (ValidationError, ValueError, UnicodeError):
        # Evita reflejar texto libre o datos personales enviados por error.
        raise HTTPException(422, "Lote de interacciones no valido.") from None
    for sid in {str(e.session_id) for e in payload.events}:
        _limit("session:" + sid, 240, sum(str(e.session_id) == sid for e in payload.events))
    return payload


@router.post("/events", status_code=202)
def create_events(payload: AnalyticsBatch = Depends(bounded_batch), db: Session = Depends(get_db)):
    try:
        return ingest_events(db, payload)
    except LookupError as exc:
        raise HTTPException(422, str(exc)) from None
    except ValueError:
        raise HTTPException(409, "El identificador de evento ya tiene otro contenido.") from None


@router.get("/dashboard", dependencies=[Depends(require_authenticated_admin)])
def read_dashboard(response: Response, days: int = Query(30), db: Session = Depends(get_db)):
    if days not in (7, 30, 90):
        raise HTTPException(422, "Selecciona 7, 30 o 90 dias.")
    response.headers["Cache-Control"] = "no-store"
    return dashboard(db, days)
