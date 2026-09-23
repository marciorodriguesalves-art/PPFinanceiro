def _make_category(client, admin_headers, name="Mercado"):
    res = client.post(
        "/api/categories", headers=admin_headers, json={"name": name, "kind": "variavel"}
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_daily_expense_crud(client, admin_headers):
    cat = _make_category(client, admin_headers)
    res = client.post(
        "/api/daily-expenses",
        headers=admin_headers,
        json={"expense_date": "2026-09-05", "description": "Feira", "amount": 70.5,
              "category_id": cat},
    )
    assert res.status_code == 201, res.text
    eid = res.json()["id"]

    res = client.get("/api/daily-expenses?year=2026&month=9", headers=admin_headers)
    assert len(res.json()) == 1

    res = client.put(f"/api/daily-expenses/{eid}", headers=admin_headers, json={"amount": 80})
    assert res.json()["amount"] == 80.0

    assert client.delete(f"/api/daily-expenses/{eid}", headers=admin_headers).status_code == 204
    assert client.get("/api/daily-expenses?year=2026&month=9", headers=admin_headers).json() == []


def test_user_isolation(client, admin_headers, user_headers):
    cat = _make_category(client, admin_headers, "Lazer")
    client.post(
        "/api/daily-expenses",
        headers=admin_headers,
        json={"expense_date": "2026-09-05", "description": "Cinema", "amount": 40,
              "category_id": cat},
    )
    # o usuário comum não enxerga lançamentos do admin
    assert client.get("/api/daily-expenses?year=2026&month=9", headers=user_headers).json() == []


def test_fixed_expense_payment_flow(client, admin_headers):
    res = client.post(
        "/api/fixed-expenses",
        headers=admin_headers,
        json={"description": "Aluguel", "amount": 2500, "due_day": 5},
    )
    fid = res.json()["id"]
    res = client.post(
        f"/api/fixed-expenses/{fid}/payments",
        headers=admin_headers,
        json={"year": 2026, "month": 9, "paid": True, "paid_date": "2026-09-05"},
    )
    assert res.status_code == 200
    assert res.json()["paid"] is True
