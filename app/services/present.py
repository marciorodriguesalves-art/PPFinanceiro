"""Conversão do orçamento consolidado para os schemas de apresentação."""

from __future__ import annotations

from app.schemas.reports import CategorySpend, KPIs
from app.services.budget import MonthBudget


def build_kpis(mb: MonthBudget) -> KPIs:
    return KPIs(
        receita_liquida=mb.receita_liquida,
        receita_bruta=mb.receita_bruta,
        total_gastos=mb.total_gastos,
        total_fixos=mb.total_fixos,
        total_variaveis=mb.total_variaveis,
        total_parcelas=mb.total_parcelas,
        saldo_disponivel=mb.saldo_disponivel,
        investimento_meta=mb.investimento_meta,
        investimento_previsto=mb.investimento_previsto,
        taxa_comprometimento=mb.taxa_comprometimento,
        taxa_investimento_prevista=mb.taxa_investimento_prevista,
        atende_meta_investimento=mb.atende_meta_investimento,
    )


def build_category_spends(mb: MonthBudget) -> list[CategorySpend]:
    return [
        CategorySpend(
            category_id=c.category_id,
            category=c.category,
            amount=c.amount,
            target=c.target,
            deviation=c.deviation,
            deviation_rate=c.deviation_rate,
        )
        for c in mb.categorias
    ]
