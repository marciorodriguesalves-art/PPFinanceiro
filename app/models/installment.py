from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CreditCardInstallment(Base):
    """Compra parcelada ativa no cartão de crédito."""

    __tablename__ = "credit_card_installments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    card: Mapped[str | None] = mapped_column(String(60), nullable=True)
    installment_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    installments_total: Mapped[int] = mapped_column(Integer, default=1)
    # Competência da 1ª parcela
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)

    category = relationship("Category", lazy="joined")

    def installment_number_for(self, year: int, month: int) -> int | None:
        """Número da parcela (1-based) que cai na competência informada, ou None."""
        offset = (year - self.start_year) * 12 + (month - self.start_month)
        if 0 <= offset < self.installments_total:
            return offset + 1
        return None

    def is_active_in(self, year: int, month: int) -> bool:
        return self.installment_number_for(year, month) is not None
