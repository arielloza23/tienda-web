from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_authenticated_admin
from app.db.session import get_db
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate, ProductStockUpdate
from app.services.product_service import StockConflict, update_stock, ProductConflict, create_product, get_admin_products, get_product_by_id, get_products, update_product
from app.services.image_service import MAX_UPLOAD_BYTES, ImageStorageError, upload_product_image

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)) -> list[ProductRead]:
    return get_products(db)


@router.get("/admin", response_model=list[ProductRead], dependencies=[Depends(require_authenticated_admin)])
def list_admin_products(db: Session = Depends(get_db)) -> list[ProductRead]:
    return get_admin_products(db)


@router.post("/images", status_code=201, dependencies=[Depends(require_authenticated_admin)])
def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    try:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="La foto debe pesar como máximo 8 MiB.")
        return {"url": upload_product_image(content)}
    except ImageStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        file.file.close()


@router.get("/{product_id}", response_model=ProductRead)
def read_product(product_id: Annotated[int, Path(gt=0, le=2147483647)], db: Session = Depends(get_db)) -> ProductRead:
    product = get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado.")
    return product


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_new_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductRead:
    try:
        return create_product(db, payload)
    except ProductConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{product_id}", response_model=ProductRead, dependencies=[Depends(require_authenticated_admin)])
def edit_product(product_id: Annotated[int, Path(gt=0, le=2147483647)], payload: ProductUpdate, db: Session = Depends(get_db)) -> ProductRead:
    try:
        product = update_product(db, product_id, payload)
    except ProductConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return product


@router.patch("/{product_id}/stock", response_model=ProductRead, dependencies=[Depends(require_authenticated_admin)])
def edit_stock(product_id: Annotated[int, Path(gt=0, le=2147483647)], payload: ProductStockUpdate, db: Session = Depends(get_db)) -> ProductRead:
    try:
        product = update_stock(db, product_id, payload)
    except StockConflict as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return product
