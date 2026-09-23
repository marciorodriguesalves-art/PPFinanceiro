from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import DailyExpense, User
from app.schemas.daily_expense import DailyExpenseCreate, DailyExpenseOut, DailyExpenseUpdate

router = APIRouter()


@router.get("", response_model=list[DailyExpenseOut])
def list_daily(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[DailyExpense]:
    stmt = select(DailyExpense).where(DailyExpense.user_id == current.id)
    if year is not None:
        stmt = stmt.where(extract("year", DailyExpense.expense_date) == year)
    if month is not None:
        stmt = stmt.where(extract("month", DailyExpense.expense_date) == month)
    return list(db.scalars(stmt.order_by(DailyExpense.expense_date.desc())).all())


@router.post("", response_model=DailyExpenseOut, status_code=status.HTTP_201_CREATED)
def create_daily(
    payload: DailyExpenseCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> DailyExpense:
    dx = DailyExpense(user_id=current.id, **payload.model_dump())
    db.add(dx)
    db.commit()
    db.refresh(dx)
    return dx


@router.put("/{expense_id}", response_model=DailyExpenseOut)
def update_daily(
    expense_id: int,
    payload: DailyExpenseUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> DailyExpense:
    dx = db.get(DailyExpense, expense_id)
    if not dx or dx.user_id != current.id:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(dx, k, v)
    db.commit()
    db.refresh(dx)
    return dx


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_daily(
    expense_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    dx = db.get(DailyExpense, expense_id)
    if not dx or dx.user_id != current.id:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")
    db.delete(dx)
    db.commit()
