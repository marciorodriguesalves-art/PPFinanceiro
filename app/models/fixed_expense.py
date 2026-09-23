from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FixedExpense(Base):
    """Despesa fixa recorrente (aluguel, escola, assinaturas...)."""

    __tablename__ = "fixed_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # dia do vencimento
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    category = relationship("Category", lazy="joined")
    payments = relationship(
        "FixedExpensePayment", back_populates="fixed_expense", cascade="all, delete-orphan"
    )


class FixedExpensePayment(Base):
    """Status de pagamento de uma despesa fixa em uma competência (mês)."""

    __tablename__ = "fixed_expense_payments"
    __table_args__ = (
        UniqueConstraint("fixed_expense_id", "year", "month", name="uq_fixed_payment_competencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_expense_id: Mapped[int] = mapped_column(
        ForeignKey("fixed_expenses.id", ondelete="CASCADE"), index=True
    )
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    month: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_paid: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    fixed_expense = relationship("FixedExpense", back_populates="payments")
