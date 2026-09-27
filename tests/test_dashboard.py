"""Testes do agregado anual do Dashboard."""

from datetime import date

from app.models import Category, DailyExpense, Income, PaymentMethod


def test_overview_annual_soma_os_meses(client, db, admin, admin_headers):
    cat = Category(name="Mercado")
    db.add(cat)
    db.flush()
    # Dois meses com dados em 2026.
    db.add(Income(user_id=admin.id, year=2026, month=1, gross_amount=5000, net_amount=4000))
    db.add(Income(user_id=admin.id, year=2026, month=2, gross_amount=5000, net_amount=4000))
    db.add(DailyExpense(
        user_id=admin.id, category_id=cat.id, expense_date=date(2026, 1, 10),
        description="Compra", amount=300, payment_method=PaymentMethod.debito,
    ))
    db.add(DailyExpense(
        user_id=admin.id, category_id=cat.id, expense_date=date(2026, 2, 10),
        description="Compra", amount=500, payment_method=PaymentMethod.debito,
    ))
    db.commit()

    res = client.get("/api/dashboard/overview-annual/2026", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["competencia"] == "2026"
    assert body["meses_com_dados"] == 2
    assert body["kpis"]["receita_liquida"] == 8000.0   # 4000 + 4000
    assert body["kpis"]["total_variaveis"] == 800.0     # 300 + 500
    merc = next(c for c in body["gastos_por_categoria"] if c["category"] == "Mercado")
    assert merc["amount"] == 800.0
