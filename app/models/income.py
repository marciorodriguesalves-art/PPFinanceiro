from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Income(Base):
    """Receita mensal — tipicamente derivada do contra cheque."""

    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    month: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(120), default="Salário")
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    @property
    def competencia(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
