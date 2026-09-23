from datetime import date

from app.models import (
    Category,
    CreditCardInstallment,
    DailyExpense,
    Income,
    Role,
    User,
    VariableGoal,
)
from app.security import hash_password
from app.services.action_plan import build_action_plan
from app.services.budget import compute_month_budget


def _user(db) -> User:
    u = User(name="U", email="u@t.local", hashed_password=hash_password("x"), role=Role.user)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _cat(db, name) -> Category:
    c = Category(name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_budget_basic_and_investment_met(db):
    u = _user(db)
    cat = _cat(db, "Lazer")
    db.add(Income(user_id=u.id, year=2026, month=9, net_amount=1000, gross_amount=1200))
    db.add(
        DailyExpense(
            user_id=u.id, category_id=cat.id, expense_date=date(2026, 9, 3),
            description="Cinema", amount=500,
        )
    )
    db.add(VariableGoal(user_id=u.id, category_id=cat.id, year=0, month=0, target_rate=0.2))
    db.commit()

    mb = compute_month_budget(db, u.id, 2026, 9)
    assert mb.receita_liquida == 1000
    assert mb.total_variaveis == 500
    assert mb.saldo_disponivel == 500
    assert mb.investimento_meta == 100.0  # 10% de 1000
    assert mb.atende_meta_investimento is True

    desvios = mb.desvios
    assert len(desvios) == 1
    assert desvios[0].target == 200.0
    assert desvios[0].deviation == 300.0


def test_action_plan_flags_overspend(db):
    u = _user(db)
    cat = _cat(db, "Mercado")
    db.add(Income(user_id=u.id, year=2026, month=9, net_amount=1000))
    db.add(
        DailyExpense(
            user_id=u.id, category_id=cat.id, expense_date=date(2026, 9, 3),
            description="Compras", amount=1200,
        )
    )
    db.commit()

    mb = compute_month_budget(db, u.id, 2026, 9)
    assert mb.saldo_disponivel == -200
    assert mb.atende_meta_investimento is False

    plan = build_action_plan(mb)
    tipos = {i.tipo for i in plan.itens}
    assert "comprometimento" in tipos
    assert "investimento" in tipos
    # precisa cortar para cobrir déficit + meta de investimento (100)
    assert plan.corte_total_sugerido >= 300
    assert plan.investimento_projetado_pos_ajuste >= mb.investimento_meta


def test_installment_active_window(db):
    u = _user(db)
    it = CreditCardInstallment(
        user_id=u.id, description="TV", installment_amount=100,
        installments_total=3, start_year=2026, start_month=8,
    )
    db.add(Income(user_id=u.id, year=2026, month=9, net_amount=1000))
    db.add(it)
    db.commit()

    assert it.is_active_in(2026, 8) is True
    assert it.is_active_in(2026, 10) is True
    assert it.is_active_in(2026, 11) is False

    mb = compute_month_budget(db, u.id, 2026, 9)
    assert mb.total_parcelas == 100


def test_no_income_returns_informative_plan(db):
    u = _user(db)
    mb = compute_month_budget(db, u.id, 2026, 9)
    plan = build_action_plan(mb)
    assert plan.itens == []
    assert "receita" in plan.resumo.lower()
