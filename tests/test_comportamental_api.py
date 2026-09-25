"""Testes de integração da camada comportamental.

Exercitam os carregadores reais (Income, DailyExpense, FixedExpense,
CreditCardInstallment) ligados ao motor, a persistência do diagnóstico e o
isolamento por usuário das reservas/recorrências.
"""

from datetime import date

from app.models import (
    Category,
    CreditCardInstallment,
    DailyExpense,
    FixedExpense,
    Income,
    PaymentMethod,
)


def _seed_mes(db, user_id: int) -> None:
    cat = Category(name="Lazer")
    db.add(cat)
    db.flush()

    # Receita líquida de R$ 10.000 em set/2026.
    db.add(
        Income(
            user_id=user_id,
            year=2026,
            month=9,
            description="Salário",
            gross_amount=13000,
            net_amount=10000,
        )
    )
    # Gastos variáveis no cartão de crédito.
    for dia, valor in ((5, 224.85), (12, 123.52), (19, 107.61)):
        db.add(
            DailyExpense(
                user_id=user_id,
                category_id=cat.id,
                expense_date=date(2026, 9, dia),
                description="Compra",
                amount=valor,
                payment_method=PaymentMethod.credito,
            )
        )
    # Despesa fixa recorrente.
    db.add(
        FixedExpense(
            user_id=user_id, category_id=cat.id, description="Streaming", amount=55.90, due_day=10
        )
    )
    # Parcela ativa em set/2026 (compra 6ª parcela de 8) → sobra futura.
    db.add(
        CreditCardInstallment(
            user_id=user_id,
            category_id=cat.id,
            description="Adidas",
            installment_amount=104.28,
            installments_total=7,
            start_year=2026,
            start_month=6,
        )
    )
    db.commit()


def test_diagnostico_gera_e_persiste_padroes(client, db, admin, admin_headers):
    _seed_mes(db, admin.id)

    res = client.post(
        "/api/comportamental/diagnosticos",
        headers=admin_headers,
        json={"periodo": "2026-09", "persistir": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["periodo"] == "2026-09"
    assert body["qtd_lancamentos"] > 0
    assert float(body["total_analisado"]) > 0
    chaves = {p["chave"] for p in body["padroes"]}
    # Sem investimento lançado, a meta de 10% dispara; a parcela ativa dispara parcelamento.
    assert "investimento" in chaves
    assert "parcelamento" in chaves

    # Persistiu: dá para recuperar depois, com id.
    got = client.get("/api/comportamental/diagnosticos/2026-09", headers=admin_headers)
    assert got.status_code == 200, got.text
    assert got.json()["id"] is not None
    assert {p["chave"] for p in got.json()["padroes"]} == chaves


def test_diagnostico_sem_dados_traz_ressalvas(client, admin_headers):
    res = client.post(
        "/api/comportamental/diagnosticos",
        headers=admin_headers,
        json={"periodo": "2026-01", "persistir": False},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["qtd_lancamentos"] == 0
    # Sem receita e sem histórico, o motor sinaliza as limitações.
    assert body["ressalvas"]


def test_recorrencias_anualizado(client, admin_headers):
    client.post(
        "/api/comportamental/recorrencias",
        headers=admin_headers,
        json={"descricao": "Streaming", "valor_mensal": "39.90", "relevancia": "baixa"},
    )
    res = client.get("/api/comportamental/recorrencias/anualizado", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["quantidade"] == 1
    assert float(body["total_anual"]) == 478.80  # 39.90 * 12


def test_metas_sugeridas_corta_impulso(client, db, admin, admin_headers):
    cat = Category(name="Lazer")  # categoria de impulso
    db.add(cat)
    db.flush()
    db.add(
        Income(user_id=admin.id, year=2026, month=8, gross_amount=13000, net_amount=10000)
    )
    db.add(
        DailyExpense(
            user_id=admin.id, category_id=cat.id, expense_date=date(2026, 8, 10),
            description="Cinema", amount=100, payment_method=PaymentMethod.credito,
        )
    )
    db.commit()

    res = client.get("/api/comportamental/metas-sugeridas/2026-08", headers=admin_headers)
    assert res.status_code == 200, res.text
    lazer = next(s for s in res.json() if s["category"] == "Lazer")
    assert lazer["impulso"] is True
    assert lazer["sugerido"] == 80.0  # corte de 20% sobre 100


def test_reservas_isolamento_por_usuario(client, admin_headers, user_headers):
    res = client.post(
        "/api/comportamental/reservas",
        headers=admin_headers,
        json={"descricao": "IPVA", "custo_anual_estimado": "1200.00"},
    )
    assert res.status_code == 201, res.text
    assert float(res.json()["valor_mensal"]) == 100.0  # 1200 / 12

    # O admin vê a própria reserva; o outro usuário não enxerga nada.
    assert len(client.get("/api/comportamental/reservas", headers=admin_headers).json()) == 1
    assert client.get("/api/comportamental/reservas", headers=user_headers).json() == []
