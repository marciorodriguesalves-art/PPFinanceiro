"""Motor de regras determinístico para o plano de ação orçamentário.

A partir do orçamento consolidado do mês (:class:`MonthBudget`), produz uma
lista priorizada de ações para: (1) eliminar desvios de meta por categoria,
(2) garantir a meta mínima de investimento (padrão 10% da receita líquida) e
(3) sinalizar comprometimento excessivo da renda e despesas fixas pendentes.

Sem chamadas externas — extensível: veja `build_action_plan` para plugar,
no futuro, uma camada de recomendações via LLM sobre o mesmo diagnóstico.
"""

from __future__ import annotations

from app.config import settings
from app.schemas.reports import ActionItem, ActionPlan
from app.services.budget import MonthBudget


def build_action_plan(mb: MonthBudget) -> ActionPlan:
    itens: list[ActionItem] = []
    prioridade = 0

    if mb.receita_liquida <= 0:
        return ActionPlan(
            competencia=mb.competencia,
            resumo=(
                "Sem receita líquida cadastrada para esta competência. "
                "Importe o contra cheque ou lance a receita para gerar o diagnóstico."
            ),
            itens=[],
            corte_total_sugerido=0.0,
            saldo_projetado_pos_ajuste=round(-mb.total_gastos, 2),
            investimento_projetado_pos_ajuste=0.0,
        )

    pct_meta = int(round(settings.min_investment_rate * 100))

    # (1) Comprometimento acima da renda — mais crítico.
    if mb.taxa_comprometimento > 1.0:
        prioridade += 1
        estouro = round(mb.total_gastos - mb.receita_liquida, 2)
        itens.append(
            ActionItem(
                prioridade=prioridade,
                categoria="Orçamento geral",
                tipo="comprometimento",
                mensagem=(
                    f"Os gastos ({_brl(mb.total_gastos)}) superam a receita líquida "
                    f"({_brl(mb.receita_liquida)}). É preciso cortar ao menos "
                    f"{_brl(estouro)} só para equilibrar o mês."
                ),
                valor_sugerido_corte=estouro,
            )
        )

    # (2) Desvios de meta por categoria (do maior para o menor).
    desvios = sorted(mb.desvios, key=lambda c: c.deviation or 0, reverse=True)
    total_desvios = round(sum((c.deviation or 0) for c in desvios), 2)
    for c in desvios:
        prioridade += 1
        itens.append(
            ActionItem(
                prioridade=prioridade,
                categoria=c.category,
                tipo="desvio_meta",
                mensagem=(
                    f"'{c.category}' gastou {_brl(c.amount)} contra a meta de "
                    f"{_brl(c.target or 0)} — {_pct(c.deviation_rate)} acima. "
                    f"Reduza cerca de {_brl(c.deviation or 0)}."
                ),
                valor_sugerido_corte=round(c.deviation or 0, 2),
            )
        )

    # (3) Meta de investimento (mínimo % da receita líquida).
    required_for_investment = round(max(0.0, mb.investimento_meta - mb.saldo_disponivel), 2)
    if not mb.atende_meta_investimento:
        prioridade += 1
        restante = round(max(0.0, required_for_investment - total_desvios), 2)
        if restante > 0:
            msg = (
                f"Para investir os {pct_meta}% mínimos ({_brl(mb.investimento_meta)}), "
                f"além de corrigir os desvios acima, corte mais {_brl(restante)} "
                f"em gastos discricionários."
            )
            corte = restante
        else:
            msg = (
                f"Corrigindo os desvios de meta você já libera espaço para investir os "
                f"{pct_meta}% mínimos ({_brl(mb.investimento_meta)})."
            )
            corte = 0.0
        itens.append(
            ActionItem(
                prioridade=prioridade,
                categoria="Investimentos",
                tipo="investimento",
                mensagem=msg,
                valor_sugerido_corte=corte,
            )
        )

    # (4) Despesas fixas ainda não pagas na competência.
    if mb.fixos_pendentes:
        prioridade += 1
        lista = ", ".join(mb.fixos_pendentes[:6])
        extra = "" if len(mb.fixos_pendentes) <= 6 else f" (+{len(mb.fixos_pendentes) - 6})"
        itens.append(
            ActionItem(
                prioridade=prioridade,
                categoria="Despesas fixas",
                tipo="fixo_pendente",
                mensagem=f"Há despesas fixas sem baixa de pagamento: {lista}{extra}.",
                valor_sugerido_corte=0.0,
            )
        )

    corte_total = round(max(total_desvios, required_for_investment), 2)
    saldo_projetado = round(mb.saldo_disponivel + corte_total, 2)
    investimento_projetado = round(max(saldo_projetado, 0.0), 2)

    resumo = _resumo(mb, corte_total, pct_meta)
    return ActionPlan(
        competencia=mb.competencia,
        resumo=resumo,
        itens=itens,
        corte_total_sugerido=corte_total,
        saldo_projetado_pos_ajuste=saldo_projetado,
        investimento_projetado_pos_ajuste=investimento_projetado,
    )


def _resumo(mb: MonthBudget, corte_total: float, pct_meta: int) -> str:
    if mb.atende_meta_investimento and not mb.desvios:
        return (
            f"Orçamento saudável: comprometimento em {_pct(mb.taxa_comprometimento)} da renda e "
            f"investimento previsto de {_brl(mb.investimento_previsto)} "
            f"({_pct(mb.taxa_investimento_prevista)}), acima da meta de {pct_meta}%."
        )
    partes = []
    if mb.desvios:
        partes.append(f"{len(mb.desvios)} categoria(s) acima da meta")
    if not mb.atende_meta_investimento:
        partes.append(f"investimento abaixo dos {pct_meta}% mínimos")
    diagnostico = " e ".join(partes) if partes else "ajustes pontuais"
    return (
        f"Foram identificados: {diagnostico}. Corte sugerido de {_brl(corte_total)} "
        f"eleva o saldo para {_brl(round(mb.saldo_disponivel + corte_total, 2))} e "
        f"garante a meta de investimento."
    )


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%".replace(".", ",")
