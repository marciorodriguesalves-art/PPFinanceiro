"""Schemas Pydantic v2 da camada comportamental (entrada/saída da API)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Reserva sazonal -------------------------------------------------------
class ReservaSazonalBase(BaseModel):
    descricao: str = Field(max_length=120)
    categoria: str | None = None
    custo_anual_estimado: Decimal


class ReservaSazonalCreate(ReservaSazonalBase):
    pass


class ReservaSazonalOut(ReservaSazonalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    saldo_acumulado: Decimal
    valor_mensal: Decimal
    ativa: bool


# --- Recorrência -----------------------------------------------------------
class RecorrenciaBase(BaseModel):
    descricao: str = Field(max_length=120)
    categoria: str | None = None
    valor_mensal: Decimal
    relevancia: str = "media"


class RecorrenciaCreate(RecorrenciaBase):
    pass


class RecorrenciaOut(RecorrenciaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    custo_anual: Decimal
    ativa: bool


# --- Diagnóstico -----------------------------------------------------------
class PadraoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chave: str
    titulo: str
    evidencia: str
    vies: str
    confianca: str
    recomendacao: str
    valor_envolvido: Decimal


class DiagnosticoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    periodo: str
    total_analisado: Decimal
    qtd_lancamentos: int
    gerado_em: dt.datetime | None = None
    padroes: list[PadraoOut] = []
    ressalvas: list[str] = []


class GerarDiagnosticoIn(BaseModel):
    """Parâmetros para gerar o diagnóstico de um período."""

    periodo: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-09"])
    persistir: bool = True
