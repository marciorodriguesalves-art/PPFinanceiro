from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    """Configurações por usuário (ex.: meta de investimento personalizada)."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), default="")
