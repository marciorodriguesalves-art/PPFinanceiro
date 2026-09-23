from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CreditCardInstallment, User
from app.schemas.installment import InstallmentCreate, InstallmentOut, InstallmentUpdate

router = APIRouter()


@router.get("", response_model=list[InstallmentOut])
def list_installments(
    active_year: int | None = Query(default=None),
    active_month: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[CreditCardInstallment]:
    items = list(
        db.scalars(
            select(CreditCardInstallment)
            .where(CreditCardInstallment.user_id == current.id)
            .order_by(CreditCardInstallment.description)
        ).all()
    )
    if active_year is not None and active_month is not None:
        items = [i for i in items if i.is_active_in(active_year, active_month)]
    return items


@router.post("", response_model=InstallmentOut, status_code=status.HTTP_201_CREATED)
def create_installment(
    payload: InstallmentCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> CreditCardInstallment:
    it = CreditCardInstallment(user_id=current.id, **payload.model_dump())
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.put("/{installment_id}", response_model=InstallmentOut)
def update_installment(
    installment_id: int,
    payload: InstallmentUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> CreditCardInstallment:
    it = db.get(CreditCardInstallment, installment_id)
    if not it or it.user_id != current.id:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(it, k, v)
    db.commit()
    db.refresh(it)
    return it


@router.delete("/{installment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_installment(
    installment_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    it = db.get(CreditCardInstallment, installment_id)
    if not it or it.user_id != current.id:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    db.delete(it)
    db.commit()
