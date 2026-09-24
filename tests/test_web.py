"""Testes da camada web (páginas servidas, não a API JSON)."""


def test_index_renderiza(client):
    """A página raiz deve renderizar o template (regressão do TemplateResponse)."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Controle Orçamentário" in res.text
    # o app referencia o Chart.js vendorizado localmente (sem CDN externo)
    assert "/static/vendor/chart.umd.min.js" in res.text


def test_health():
    from fastapi.testclient import TestClient

    from app.main import app

    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
