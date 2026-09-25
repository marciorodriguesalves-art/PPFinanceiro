"""Cria o usuário administrador inicial — SEM dados de demonstração.

Uso em produção (após as migrations):
    docker compose -f docker-compose.prod.yml exec app python -m scripts.create_admin

Idempotente: se o admin (settings.admin_email) já existir, não faz nada.
Diferente de scripts.seed, que também popula um cenário de exemplo.
"""

from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == settings.admin_email))
        if existing:
            print(f"Admin já existe: {settings.admin_email}")
            return
        db.add(
            User(
                name=settings.admin_name,
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                role=Role.admin,
            )
        )
        db.commit()
        print(f"Admin criado: {settings.admin_email} — troque a senha após o primeiro login.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
