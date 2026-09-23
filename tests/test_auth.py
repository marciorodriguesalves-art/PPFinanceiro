def test_login_ok(client, admin):
    res = client.post(
        "/api/auth/login", data={"username": "admin@test.com", "password": "admin123"}
    )
    assert res.status_code == 200
    assert res.json()["token_type"] == "bearer"


def test_login_wrong_password(client, admin):
    res = client.post("/api/auth/login", data={"username": "admin@test.com", "password": "x"})
    assert res.status_code == 401


def test_me(client, admin_headers):
    res = client.get("/api/auth/me", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_protected_requires_token(client):
    assert client.get("/api/incomes").status_code == 401


def test_admin_only_users_endpoint(client, user_headers):
    # usuário comum não pode listar usuários
    assert client.get("/api/users", headers=user_headers).status_code == 403


def test_admin_can_manage_users(client, admin_headers):
    res = client.post(
        "/api/users",
        headers=admin_headers,
        json={"name": "Novo", "email": "novo@test.com", "password": "secret6", "role": "user"},
    )
    assert res.status_code == 201
    assert client.get("/api/users", headers=admin_headers).status_code == 200
