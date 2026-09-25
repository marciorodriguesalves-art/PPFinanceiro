"""Testes da rota de importação — foco no multi-mês (competência vem da data)."""


def _post_csv(client, headers, content: str):
    return client.post(
        "/api/imports/statement",
        headers=headers,
        data={"year": "2026", "month": "1", "layout": "cartao", "create_installments": "true"},
        files={"file": ("fatura.csv", content, "text/csv")},
    )


def test_import_deriva_competencia_da_data_multi_mes(client, admin, admin_headers):
    # Um único arquivo com lançamentos em julho e agosto de 2026.
    csv = "date,title,amount\n2026-07-05,Mercado A,100.00\n2026-08-09,Mercado B,150.00\n"
    res = _post_csv(client, admin_headers, csv)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["lancamentos_criados"] == 2
    assert body["competencias"] == ["2026-07", "2026-08"]

    # Cada lançamento cai no seu próprio mês, independente do form (month=1).
    jul = client.get("/api/daily-expenses?year=2026&month=7", headers=admin_headers).json()
    ago = client.get("/api/daily-expenses?year=2026&month=8", headers=admin_headers).json()
    assert [r["description"] for r in jul] == ["Mercado A"]
    assert [r["description"] for r in ago] == ["Mercado B"]


def test_import_parcela_deriva_inicio_da_data(client, admin, admin_headers):
    # Parcela 3/5 lançada em agosto/2026 -> 1ª parcela em junho/2026.
    csv = "date,title,amount\n2026-08-15,Loja X - Parcela 3/5,200.00\n"
    res = _post_csv(client, admin_headers, csv)
    assert res.status_code == 200, res.text
    assert res.json()["parcelas_criadas"] == 1

    insts = client.get(
        "/api/installments?active_year=2026&active_month=8", headers=admin_headers
    ).json()
    assert len(insts) == 1
    assert insts[0]["start_year"] == 2026
    assert insts[0]["start_month"] == 6  # 8 - (3-1) = 6
