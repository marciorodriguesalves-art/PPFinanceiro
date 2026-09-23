import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password

# Por padrão os testes rodam em SQLite in-memory (rápido, sem dependências).
# No CI definimos TEST_DATABASE_URL apontando para o PostgreSQL de teste, para
# validar o código contra o mesmo banco usado em produção.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    engine = create_engine(TEST_DATABASE_URL, future=True)
else:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(autouse=True)
def _db_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin(db) -> User:
    user = User(
        name="Admin",
        email="admin@test.com",
        hashed_password=hash_password("admin123"),
        role=Role.admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user(db) -> User:
    u = User(
        name="User",
        email="user@test.com",
        hashed_password=hash_password("user123"),
        role=Role.user,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_headers(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": "Bearer " + res.json()["access_token"]}


@pytest.fixture
def admin_headers(client, admin) -> dict:
    return auth_headers(client, "admin@test.com", "admin123")


@pytest.fixture
def user_headers(client, user) -> dict:
    return auth_headers(client, "user@test.com", "user123")
