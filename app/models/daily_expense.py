from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PaymentMethod


class DailyExpense(Base):
    """Lançamento diário de gasto variável."""

    __tablename__ = "daily_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    expense_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(160), default="")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.debito
    )

    category = relationship("Category", lazy="joined")
