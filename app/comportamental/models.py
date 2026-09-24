"""Modelos SQLAlchemy 2.0 da camada comportamental.

Tabelas NOVAS, aditivas ao schema existente do Sistema de Controle Orçamentário.
Não alteram nada do que já existe; apenas se apoiam nos lançamentos já
importados (contra cheque, fatura Nubank) via período/usuário.

Ajuste o import de `Base` para o declarative base real do seu projeto.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:  # usa o Base do projeto se disponível
    from app.database import Base  # type: ignore
except Exception:  # pragma: no cover - fallback para uso isolado/testes
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):  # type: ignore[no-redef]
        pass


_MONEY = Numeric(12, 2)


class ReservaSazonal(Base):
    """Caixinha para gastos irregulares (IPVA, IPTU, matrícula, seguro, presentes).

    Combate a contabilidade mental e o esquecimento de despesas grandes:
    guarda-se 1/12 do custo anual estimado por mês.
    """

    __tablename__ = "reserva_sazonal"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    descricao: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str | None] = mapped_column(String(60), default=None)
    custo_anual_estimado: Mapped[Decimal] = mapped_column(_MONEY)
    saldo_acumulado: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    ativa: Mapped[bool] = mapped_column(default=True)
    criada_em: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    @property
    def valor_mensal(self) -> Decimal:
        return (self.custo_anual_estimado / 12).quantize(Decimal("0.01"))


class Recorrencia(Base):
    """Assinaturas e despesas fixas, com custo anualizado e sinal de uso/relevância.

    Combate aversão à perda / efeito posse: exibir o custo anual muda a decisão
    de manter ou cancelar muito mais do que a mensalidade.
    """

    __tablename__ = "recorrencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    descricao: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str | None] = mapped_column(String(60), default=None)
    valor_mensal: Mapped[Decimal] = mapped_column(_MONEY)
    relevancia: Mapped[str] = mapped_column(String(20), default="media")  # alta|media|baixa
    ativa: Mapped[bool] = mapped_column(default=True)
    atualizada_em: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    @property
    def custo_anual(self) -> Decimal:
        return (self.valor_mensal * 12).quantize(Decimal("0.01"))


class Diagnostico(Base):
    """Resultado de uma análise comportamental de um período (mês)."""

    __tablename__ = "diagnostico"
    __table_args__ = (
        UniqueConstraint("usuario_id", "periodo", name="uq_diagnostico_usuario_periodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # "2026-09"
    total_analisado: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))
    qtd_lancamentos: Mapped[int] = mapped_column(default=0)
    gerado_em: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    padroes: Mapped[list[DiagnosticoPadrao]] = relationship(
        back_populates="diagnostico",
        cascade="all, delete-orphan",
        order_by="DiagnosticoPadrao.ordem",
    )
    ressalvas: Mapped[list[DiagnosticoRessalva]] = relationship(
        back_populates="diagnostico",
        cascade="all, delete-orphan",
    )


class DiagnosticoPadrao(Base):
    __tablename__ = "diagnostico_padrao"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostico_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostico.id", ondelete="CASCADE"), index=True
    )
    ordem: Mapped[int] = mapped_column(default=0)
    chave: Mapped[str] = mapped_column(String(60))
    titulo: Mapped[str] = mapped_column(String(160))
    evidencia: Mapped[str] = mapped_column(Text)
    vies: Mapped[str] = mapped_column(String(200))
    confianca: Mapped[str] = mapped_column(String(10))  # alta|media|baixa
    recomendacao: Mapped[str] = mapped_column(Text)
    valor_envolvido: Mapped[Decimal] = mapped_column(_MONEY, default=Decimal("0"))

    diagnostico: Mapped[Diagnostico] = relationship(back_populates="padroes")


class DiagnosticoRessalva(Base):
    __tablename__ = "diagnostico_ressalva"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostico_id: Mapped[int] = mapped_column(
        ForeignKey("diagnostico.id", ondelete="CASCADE"), index=True
    )
    texto: Mapped[str] = mapped_column(Text)

    diagnostico: Mapped[Diagnostico] = relationship(back_populates="ressalvas")
