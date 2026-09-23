from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import FixedExpense, FixedExpensePayment, User
from app.schemas.fixed_expense import (
    FixedExpenseCreate,
    FixedExpenseOut,
    FixedExpensePaymentOut,
    FixedExpenseUpdate,
    PaymentMark,
)

router = APIRouter()


def _get_owned(db: Session, expense_id: int, user: User) -> FixedExpense:
    fx = db.get(FixedExpense, expense_id)
    if not fx or fx.user_id != user.id:
        raise HTTPException(status_code=404, detail="Despesa fixa não encontrada")
    return fx


@router.get("", response_model=list[FixedExpenseOut])
def list_fixed(
    db: Session = Depends(get_db), current: User = Depends(get_current_user)
) -> list[FixedExpense]:
    return list(
        db.scalars(
            select(FixedExpense)
            .where(FixedExpense.user_id == current.id)
            .order_by(FixedExpense.description)
        ).all()
    )


@router.post("", response_model=FixedExpenseOut, status_code=status.HTTP_201_CREATED)
def create_fixed(
    payload: FixedExpenseCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> FixedExpense:
    fx = FixedExpense(user_id=current.id, **payload.model_dump())
    db.add(fx)
    db.commit()
    db.refresh(fx)
    return fx


@router.put("/{expense_id}", response_model=FixedExpenseOut)
def update_fixed(
    expense_id: int,
    payload: FixedExpenseUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> FixedExpense:
    fx = _get_owned(db, expense_id, current)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(fx, k, v)
    db.commit()
    db.refresh(fx)
    return fx


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fixed(
    expense_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    fx = _get_owned(db, expense_id, current)
    db.delete(fx)
    db.commit()


@router.post("/{expense_id}/payments", response_model=FixedExpensePaymentOut)
def mark_payment(
    expense_id: int,
    payload: PaymentMark,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> FixedExpensePayment:
    """Marca (ou atualiza) o pagamento da despesa fixa em uma competência."""
    fx = _get_owned(db, expense_id, current)
    payment = db.scalar(
        select(FixedExpensePayment).where(
            FixedExpensePayment.fixed_expense_id == fx.id,
            FixedExpensePayment.year == payload.year,
            FixedExpensePayment.month == payload.month,
        )
    )
    if payment is None:
        payment = FixedExpensePayment(
            fixed_expense_id=fx.id, year=payload.year, month=payload.month
        )
        db.add(payment)
    payment.paid = payload.paid
    payment.paid_date = payload.paid_date
    payment.amount_paid = payload.amount_paid if payload.amount_paid is not None else fx.amount
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{expense_id}/payments", response_model=list[FixedExpensePaymentOut])
def list_payments(
    expense_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[FixedExpensePayment]:
    fx = _get_owned(db, expense_id, current)
    return list(
        db.scalars(
            select(FixedExpensePayment)
            .where(FixedExpensePayment.fixed_expense_id == fx.id)
            .order_by(FixedExpensePayment.year, FixedExpensePayment.month)
        ).all()
    )
