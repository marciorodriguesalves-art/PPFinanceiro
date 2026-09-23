from sqlalchemy import Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CategoryKind


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(CategoryKind), default=CategoryKind.variavel, nullable=False
    )
    # Meta padrão como fração da receita líquida (ex.: 0.08 = 8%). Opcional.
    default_target_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
