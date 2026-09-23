from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VariableGoal(Base):
    """Meta de gasto variável por categoria.

    A meta pode ser expressa como fração da receita líquida (target_rate)
    e/ou como valor absoluto (target_amount). Quando ambos existem, o
    serviço de orçamento usa o menor limite.
    """

    __tablename__ = "variable_goals"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", "year", "month", name="uq_goal_competencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    # year/month = 0 significa meta padrão válida para qualquer mês.
    year: Mapped[int] = mapped_column(Integer, default=0)
    month: Mapped[int] = mapped_column(Integer, default=0)
    target_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    target_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    category = relationship("Category", lazy="joined")
