"""Serviço de cálculo orçamentário.

Consolida receitas, despesas fixas, gastos variáveis (lançamentos diários) e
parcelas de cartão de crédito de uma competência (ano/mês) para um usuário,
e produz os indicadores e a quebra por categoria usados nos dashboards e no
motor de plano de ação.

Todas as regras são determinísticas — sem chamadas externas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    CreditCardInstallment,
    DailyExpense,
    FixedExpense,
    FixedExpensePayment,
    Income,
    VariableGoal,
)


@dataclass
class CategoryLine:
    category_id: int | None
    category: str
    amount: float = 0.0
    target: float | None = None

    @property
    def deviation(self) -> float | None:
        if self.target is None:
            return None
        return round(self.amount - self.target, 2)

    @property
    def deviation_rate(self) -> float | None:
        if not self.target:
            return None
        return round((self.amount - self.target) / self.target, 4)


@dataclass
class MonthBudget:
    year: int
    month: int
    receita_bruta: float = 0.0
    receita_liquida: float = 0.0
    total_fixos: float = 0.0
    total_variaveis: float = 0.0
    total_parcelas: float = 0.0
    categorias: list[CategoryLine] = field(default_factory=list)
    fixos_pendentes: list[str] = field(default_factory=list)

    @property
    def competencia(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def total_gastos(self) -> float:
        return round(self.total_fixos + self.total_variaveis + self.total_parcelas, 2)

    @property
    def saldo_disponivel(self) -> float:
        return round(self.receita_liquida - self.total_gastos, 2)

    @property
    def investimento_meta(self) -> float:
        return round(self.receita_liquida * settings.min_investment_rate, 2)

    @property
    def investimento_previsto(self) -> float:
        return round(max(self.saldo_disponivel, 0.0), 2)

    @property
    def taxa_comprometimento(self) -> float:
        if self.receita_liquida <= 0:
            return 0.0
        return round(self.total_gastos / self.receita_liquida, 4)

    @property
    def taxa_investimento_prevista(self) -> float:
        if self.receita_liquida <= 0:
            return 0.0
        return round(self.investimento_previsto / self.receita_liquida, 4)

    @property
    def atende_meta_investimento(self) -> bool:
        return self.investimento_previsto >= self.investimento_meta and self.saldo_disponivel >= 0

    @property
    def desvios(self) -> list[CategoryLine]:
        """Categorias que estouraram a meta (deviation > 0)."""
        return [c for c in self.categorias if c.deviation is not None and c.deviation > 0]


def _f(value) -> float:
    return float(value) if value is not None else 0.0


def compute_month_budget(db: Session, user_id: int, year: int, month: int) -> MonthBudget:
    mb = MonthBudget(year=year, month=month)

    # --- Receita (contra cheque) ---
    incomes = db.scalars(
        select(Income).where(
            Income.user_id == user_id, Income.year == year, Income.month == month
        )
    ).all()
    mb.receita_bruta = round(sum(_f(i.gross_amount) for i in incomes), 2)
    mb.receita_liquida = round(sum(_f(i.net_amount) for i in incomes), 2)

    # Acumuladores por categoria
    lines: dict[int | None, CategoryLine] = {}

    def bucket(cat_id: int | None, cat_name: str) -> CategoryLine:
        if cat_id not in lines:
            lines[cat_id] = CategoryLine(category_id=cat_id, category=cat_name)
        return lines[cat_id]

    # --- Despesas fixas (valor planejado das ativas) ---
    fixed = db.scalars(
        select(FixedExpense).where(
            FixedExpense.user_id == user_id, FixedExpense.active.is_(True)
        )
    ).all()
    paid_index = {
        p.fixed_expense_id: p
        for p in db.scalars(
            select(FixedExpensePayment).where(
                FixedExpensePayment.year == year, FixedExpensePayment.month == month
            )
        ).all()
    }
    for fx in fixed:
        amount = _f(fx.amount)
        mb.total_fixos += amount
        cat_name = fx.category.name if fx.category else "Despesas Fixas"
        bucket(fx.category_id, cat_name).amount += amount
        payment = paid_index.get(fx.id)
        if payment is None or not payment.paid:
            mb.fixos_pendentes.append(fx.description)
    mb.total_fixos = round(mb.total_fixos, 2)

    # --- Gastos variáveis (lançamentos diários) ---
    dailies = db.scalars(
        select(DailyExpense).where(
            DailyExpense.user_id == user_id,
            extract("year", DailyExpense.expense_date) == year,
            extract("month", DailyExpense.expense_date) == month,
        )
    ).all()
    for dx in dailies:
        amount = _f(dx.amount)
        mb.total_variaveis += amount
        cat_name = dx.category.name if dx.category else "Sem categoria"
        bucket(dx.category_id, cat_name).amount += amount
    mb.total_variaveis = round(mb.total_variaveis, 2)

    # --- Parcelas de cartão ativas na competência ---
    installments = db.scalars(
        select(CreditCardInstallment).where(CreditCardInstallment.user_id == user_id)
    ).all()
    for it in installments:
        if it.is_active_in(year, month):
            amount = _f(it.installment_amount)
            mb.total_parcelas += amount
            cat_name = it.category.name if it.category else "Cartão de Crédito"
            bucket(it.category_id, cat_name).amount += amount
    mb.total_parcelas = round(mb.total_parcelas, 2)

    # --- Metas por categoria ---
    _apply_goals(db, user_id, year, month, mb.receita_liquida, lines)

    mb.categorias = sorted(lines.values(), key=lambda c: c.amount, reverse=True)
    for c in mb.categorias:
        c.amount = round(c.amount, 2)
    return mb


def _apply_goals(
    db: Session,
    user_id: int,
    year: int,
    month: int,
    receita_liquida: float,
    lines: dict[int | None, CategoryLine],
) -> None:
    goals = db.scalars(
        select(VariableGoal).where(VariableGoal.user_id == user_id)
    ).all()
    # Preferir meta específica da competência; senão a meta padrão (year=0,month=0).
    chosen: dict[int, VariableGoal] = {}
    for g in goals:
        specific = g.year == year and g.month == month
        default = g.year == 0 and g.month == 0
        if not (specific or default):
            continue
        current = chosen.get(g.category_id)
        if current is None or (specific and not (current.year == year and current.month == month)):
            chosen[g.category_id] = g

    for cat_id, g in chosen.items():
        target: float | None = None
        if g.target_amount is not None:
            target = _f(g.target_amount)
        if g.target_rate is not None:
            rate_target = receita_liquida * _f(g.target_rate)
            target = rate_target if target is None else min(target, rate_target)
        if cat_id in lines:
            lines[cat_id].target = round(target, 2) if target is not None else None
        elif target is not None:
            # Categoria com meta mas sem gasto ainda no mês.
            name = g.category.name if g.category else f"Categoria {cat_id}"
            lines[cat_id] = CategoryLine(
                category_id=cat_id, category=name, amount=0.0, target=round(target, 2)
            )
