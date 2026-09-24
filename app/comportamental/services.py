"""Serviços da camada comportamental.

Faz a ponte entre o banco (ORM do projeto) e o motor de diagnóstico puro
(engine.py). Os pontos que dependem do schema existente do seu MVP estão
marcados com  # >>> INTEGRAÇÃO  — são os únicos lugares a ajustar quando
plugar no scaffold real.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    CreditCardInstallment,
    DailyExpense,
    FixedExpense,
    Income,
    PaymentMethod,
    VariableGoal,
)

from . import constants as C
from . import engine, models

ZERO = Decimal("0")


# --------------------------------------------------------------------------- #
# Regras determinísticas de "ambiente" (Fase 1)
# --------------------------------------------------------------------------- #
def valor_mensal_reserva(custo_anual: Decimal) -> Decimal:
    """1/12 do custo anual estimado — a caixinha de gastos sazonais."""
    return (custo_anual / 12).quantize(Decimal("0.01"))


def pague_se_primeiro(
    receita_liquida: Decimal, meta_pct: Decimal = C.META_INVESTIMENTO_PADRAO
) -> Decimal:
    """Quanto reservar para investimento ANTES do consumo (primeira 'despesa')."""
    return (receita_liquida * meta_pct).quantize(Decimal("0.01"))


def saldo_disponivel_apos_metas(
    receita_liquida: Decimal,
    reservas_mensais: Iterable[Decimal],
    meta_investimento: Decimal,
) -> Decimal:
    """Saldo que sobra depois de investir e reservar os sazonais.

    É o número que o dashboard deve mostrar como 'disponível' — não a receita
    cheia — para materializar o pague-se-primeiro.
    """
    total_reservas = sum(reservas_mensais, ZERO)
    return (receita_liquida - meta_investimento - total_reservas).quantize(Decimal("0.01"))


def anualizar_recorrencias(recorrencias: Iterable[models.Recorrencia]) -> dict:
    ativos = [r for r in recorrencias if r.ativa]
    mensal = sum((r.valor_mensal for r in ativos), ZERO)
    return {
        "quantidade": len(ativos),
        "total_mensal": mensal.quantize(Decimal("0.01")),
        "total_anual": (mensal * 12).quantize(Decimal("0.01")),
        "itens": [
            {
                "descricao": r.descricao,
                "mensal": r.valor_mensal,
                "anual": r.custo_anual,
                "relevancia": r.relevancia,
            }
            for r in sorted(ativos, key=lambda r: r.valor_mensal, reverse=True)
        ],
    }


# --------------------------------------------------------------------------- #
# Diagnóstico (Fase 2) — orquestra motor + persistência
# --------------------------------------------------------------------------- #
def construir_diagnostico(
    lancamentos: list[engine.LancamentoIn],
    contexto: engine.ContextoDiagnostico,
    historico: list[engine.ResumoMes] | None = None,
) -> engine.Diagnostico:
    """Wrapper fino sobre o motor puro (útil para testes e para a Fase 0)."""
    return engine.diagnosticar(lancamentos, contexto, historico)


def gerar_diagnostico_para_usuario(
    db: Session,
    usuario_id: int,
    periodo: str,
    *,
    persistir: bool = True,
) -> engine.Diagnostico:
    """Carrega dados do usuário, roda o motor e (opcional) persiste o resultado."""
    lancs = _carregar_lancamentos(db, usuario_id, periodo)
    contexto = _carregar_contexto(db, usuario_id, periodo)
    historico = _carregar_historico(db, usuario_id, periodo)

    diag = engine.diagnosticar(lancs, contexto, historico)

    if persistir:
        _persistir(db, usuario_id, diag)
    return diag


def _persistir(db: Session, usuario_id: int, diag: engine.Diagnostico) -> models.Diagnostico:
    """Grava/atualiza o diagnóstico do período (idempotente por usuário+período)."""
    existente = db.scalar(
        select(models.Diagnostico).where(
            models.Diagnostico.usuario_id == usuario_id,
            models.Diagnostico.periodo == diag.periodo,
        )
    )
    if existente:
        db.delete(existente)
        db.flush()

    registro = models.Diagnostico(
        usuario_id=usuario_id,
        periodo=diag.periodo,
        total_analisado=diag.total_analisado,
        qtd_lancamentos=diag.qtd_lancamentos,
        padroes=[
            models.DiagnosticoPadrao(
                ordem=i,
                chave=p.chave,
                titulo=p.titulo,
                evidencia=p.evidencia,
                vies=p.vies,
                confianca=p.confianca,
                recomendacao=p.recomendacao,
                valor_envolvido=p.valor_envolvido,
            )
            for i, p in enumerate(diag.padroes)
        ],
        ressalvas=[models.DiagnosticoRessalva(texto=t) for t in diag.ressalvas],
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


# --------------------------------------------------------------------------- #
# Carregadores — ligam o motor ao schema real do MVP (Income, DailyExpense,
# FixedExpense, CreditCardInstallment, VariableGoal). Tudo filtrado por usuário
# e competência, como manda a convenção do projeto (ver CLAUDE.md).
# --------------------------------------------------------------------------- #

# Meio de pagamento do projeto -> vocabulário do motor (cartao_credito dilui a
# "dor de pagar"; os demais mantêm o próprio nome).
_MEIO_PAGAMENTO = {
    PaymentMethod.credito: C.MEIO_CARTAO_CREDITO,
}
_MESES_HISTORICO = 6


def _dec(valor) -> Decimal:
    """Converte valor monetário (Decimal do Numeric, ou float) para Decimal 2 casas."""
    if valor is None:
        return ZERO
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _ano_mes(periodo: str) -> tuple[int, int]:
    ano, mes = periodo.split("-")
    return int(ano), int(mes)


def _passo_mes(ano: int, mes: int, delta: int) -> tuple[int, int]:
    indice = (ano * 12 + (mes - 1)) + delta
    return indice // 12, (indice % 12) + 1


def _carregar_lancamentos(
    db: Session, usuario_id: int, periodo: str
) -> list[engine.LancamentoIn]:
    """Consolida receita, gastos variáveis, despesas fixas e parcelas do período
    em uma lista neutra de ``LancamentoIn`` para o motor."""
    ano, mes = _ano_mes(periodo)
    lancs: list[engine.LancamentoIn] = []

    # Receita (contra cheque) — usada p/ contabilidade mental (entradas atípicas).
    for inc in db.scalars(
        select(Income).where(
            Income.user_id == usuario_id, Income.year == ano, Income.month == mes
        )
    ):
        lancs.append(
            engine.LancamentoIn(
                data=inc.received_date or date(ano, mes, 1),
                descricao=inc.description or "Receita",
                valor=_dec(inc.net_amount),
                categoria="Receita",
                tipo="receita",
            )
        )

    # Gastos variáveis (lançamentos diários).
    dailies = db.scalars(
        select(DailyExpense).where(
            DailyExpense.user_id == usuario_id,
            extract("year", DailyExpense.expense_date) == ano,
            extract("month", DailyExpense.expense_date) == mes,
        )
    )
    for dx in dailies:
        lancs.append(
            engine.LancamentoIn(
                data=dx.expense_date,
                descricao=dx.description or "Lançamento",
                valor=_dec(dx.amount),
                categoria=dx.category.name if dx.category else "Sem categoria",
                tipo="despesa",
                meio_pagamento=_MEIO_PAGAMENTO.get(
                    dx.payment_method,
                    dx.payment_method.value if dx.payment_method else None,
                ),
            )
        )

    # Despesas fixas ativas — recorrentes (assinaturas/fixos) do período.
    for fx in db.scalars(
        select(FixedExpense).where(
            FixedExpense.user_id == usuario_id, FixedExpense.active.is_(True)
        )
    ):
        dia = min(fx.due_day or 1, 28)
        lancs.append(
            engine.LancamentoIn(
                data=date(ano, mes, dia),
                descricao=fx.description,
                valor=_dec(fx.amount),
                categoria=fx.category.name if fx.category else "Despesas Fixas",
                tipo="despesa",
                recorrente=True,
            )
        )

    # Parcelas de cartão ativas na competência.
    for it in db.scalars(
        select(CreditCardInstallment).where(
            CreditCardInstallment.user_id == usuario_id
        )
    ):
        numero = it.installment_number_for(ano, mes)
        if numero is None:
            continue
        lancs.append(
            engine.LancamentoIn(
                data=date(ano, mes, 1),
                descricao=it.description,
                valor=_dec(it.installment_amount),
                categoria=it.category.name if it.category else "Cartão de Crédito",
                tipo="despesa",
                meio_pagamento=C.MEIO_CARTAO_CREDITO,
                parcela_atual=numero,
                parcela_total=it.installments_total,
            )
        )

    return lancs


def _carregar_contexto(
    db: Session, usuario_id: int, periodo: str
) -> engine.ContextoDiagnostico:
    """Receita líquida do período, meta de investimento e metas variáveis (por
    fração da receita) — respeitando a precedência meta específica > meta padrão."""
    ano, mes = _ano_mes(periodo)

    receita = db.scalars(
        select(Income.net_amount).where(
            Income.user_id == usuario_id, Income.year == ano, Income.month == mes
        )
    ).all()
    receita_liquida = sum((_dec(v) for v in receita), ZERO) if receita else None

    # Metas por categoria: prefere a meta da competência; senão a padrão (0/0).
    escolhidas: dict[int, VariableGoal] = {}
    for g in db.scalars(
        select(VariableGoal).where(VariableGoal.user_id == usuario_id)
    ):
        especifica = g.year == ano and g.month == mes
        padrao = g.year == 0 and g.month == 0
        if not (especifica or padrao):
            continue
        atual = escolhidas.get(g.category_id)
        if atual is None or (especifica and not (atual.year == ano and atual.month == mes)):
            escolhidas[g.category_id] = g

    metas_variaveis: dict[str, Decimal] = {}
    for g in escolhidas.values():
        if g.target_rate is not None and g.category:
            metas_variaveis[g.category.name] = _dec(g.target_rate)

    return engine.ContextoDiagnostico(
        periodo=periodo,
        receita_liquida=receita_liquida,
        meta_investimento_pct=Decimal(str(settings.min_investment_rate)),
        metas_variaveis=metas_variaveis,
    )


def _carregar_historico(
    db: Session, usuario_id: int, periodo: str
) -> list[engine.ResumoMes]:
    """Ticket médio por categoria (gastos variáveis) dos meses anteriores, para
    detectar inflação do estilo de vida."""
    ano, mes = _ano_mes(periodo)
    resumos: list[engine.ResumoMes] = []
    for delta in range(1, _MESES_HISTORICO + 1):
        h_ano, h_mes = _passo_mes(ano, mes, -delta)
        dailies = db.scalars(
            select(DailyExpense).where(
                DailyExpense.user_id == usuario_id,
                extract("year", DailyExpense.expense_date) == h_ano,
                extract("month", DailyExpense.expense_date) == h_mes,
            )
        ).all()
        if not dailies:
            continue
        por_cat: dict[str, list[Decimal]] = {}
        for dx in dailies:
            nome = dx.category.name if dx.category else "Sem categoria"
            por_cat.setdefault(nome, []).append(_dec(dx.amount))
        ticket = {
            cat: (sum(vals, ZERO) / len(vals)).quantize(Decimal("0.01"))
            for cat, vals in por_cat.items()
        }
        resumos.append(
            engine.ResumoMes(periodo=f"{h_ano:04d}-{h_mes:02d}", ticket_medio_por_categoria=ticket)
        )
    return resumos
