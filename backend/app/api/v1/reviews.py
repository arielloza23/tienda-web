from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.review import ReviewPage, ReviewRead, ReviewWrite
from app.services.review_service import get_own_review, list_reviews, require_active_product, review_read, save_review

router = APIRouter(prefix="/products/{product_id}/reviews", tags=["reviews"])


def active_product(product_id: int, db: Session = Depends(get_db)) -> int:
    try:
        require_active_product(db, product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return product_id


@router.get("", response_model=ReviewPage)
def read_reviews(product_id: int = Depends(active_product), limit: int = Query(10, ge=1, le=50),
                 offset: int = Query(0, ge=0), db: Session = Depends(get_db)) -> ReviewPage:
    return list_reviews(db, product_id, limit, offset)


@router.get("/me", response_model=ReviewRead | None)
def read_my_review(product_id: int = Depends(active_product), current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ReviewRead | None:
    review = get_own_review(db, product_id, current_user.id)
    return review_read(review) if review else None


@router.put("/me", response_model=ReviewRead)
def write_my_review(payload: ReviewWrite, product_id: int = Depends(active_product),
                    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReviewRead:
    return review_read(save_review(db, product_id, current_user.id, payload))
