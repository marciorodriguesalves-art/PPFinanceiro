from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Income, User
from app.schemas.income import IncomeCreate, IncomeOut, IncomeUpdate

router = APIRouter()


@router.get("", response_model=list[IncomeOut])
def list_incomes(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[Income]:
    stmt = select(Income).where(Income.user_id == current.id)
    if year is not None:
        stmt = stmt.where(Income.year == year)
    if month is not None:
        stmt = stmt.where(Income.month == month)
    return list(db.scalars(stmt.order_by(Income.year, Income.month)).all())


@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: IncomeCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Income:
    income = Income(user_id=current.id, **payload.model_dump())
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


@router.put("/{income_id}", response_model=IncomeOut)
def update_income(
    income_id: int,
    payload: IncomeUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Income:
    income = db.get(Income, income_id)
    if not income or income.user_id != current.id:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(income, k, v)
    db.commit()
    db.refresh(income)
    return income


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    income = db.get(Income, income_id)
    if not income or income.user_id != current.id:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    db.delete(income)
    db.commit()
