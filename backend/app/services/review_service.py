from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.product import Product
from app.models.review import ProductReview
from app.schemas.review import ReviewPage, ReviewRead, ReviewWrite


def require_active_product(db: Session, product_id: int) -> None:
    if db.scalar(select(Product.id).where(Product.id == product_id, Product.is_active.is_(True))) is None:
        raise LookupError("Producto no encontrado.")


def review_read(review: ProductReview) -> ReviewRead:
    return ReviewRead(id=review.id, product_id=review.product_id, author_name=review.author.full_name,
                      rating=review.rating, comment=review.comment,
                      created_at=review.created_at, updated_at=review.updated_at)


def get_own_review(db: Session, product_id: int, user_id: int) -> ProductReview | None:
    return db.scalar(select(ProductReview).options(joinedload(ProductReview.author)).where(
        ProductReview.product_id == product_id, ProductReview.user_id == user_id))


def list_reviews(db: Session, product_id: int, limit: int, offset: int) -> ReviewPage:
    total, average = db.execute(select(func.count(ProductReview.id), func.avg(ProductReview.rating)).where(
        ProductReview.product_id == product_id)).one()
    items = db.scalars(select(ProductReview).options(joinedload(ProductReview.author)).where(
        ProductReview.product_id == product_id).order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
        .limit(limit).offset(offset)).all()
    return ReviewPage(items=[review_read(item) for item in items], total=total,
                      average_rating=round(float(average), 1) if average is not None else None,
                      limit=limit, offset=offset)


def _is_own_review_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint == "uq_product_reviews_product_user" or (
        "UNIQUE constraint failed: product_reviews.product_id, product_reviews.user_id" in str(exc.orig))


def save_review(db: Session, product_id: int, user_id: int, payload: ReviewWrite) -> ProductReview:
    review = get_own_review(db, product_id, user_id)
    if review is None:
        review = ProductReview(product_id=product_id, user_id=user_id)
        db.add(review)
    review.rating = payload.rating
    review.comment = payload.comment
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if not _is_own_review_conflict(exc):
            raise
        # Otra petición creó la misma reseña: una sola actualización, sin reintentos ilimitados.
        review = get_own_review(db, product_id, user_id)
        if review is None:
            raise
        review.rating = payload.rating
        review.comment = payload.comment
        db.commit()
    db.refresh(review)
    return review
