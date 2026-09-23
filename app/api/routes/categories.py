from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter()


@router.get("", response_model=list[CategoryOut], dependencies=[Depends(get_current_user)])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)).all())


@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> Category:
    if db.scalar(select(Category).where(Category.name == payload.name)):
        raise HTTPException(status_code=409, detail="Categoria já existe")
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put(
    "/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)]
)
def update_category(
    category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)
) -> Category:
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> None:
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    db.delete(cat)
    db.commit()
