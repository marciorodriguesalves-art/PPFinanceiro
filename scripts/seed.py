"""Popula o banco com dados iniciais e um cenário de demonstração.

Uso::

    python -m scripts.seed

Cria o administrador (credenciais do .env), um usuário comum, categorias e um
mês de exemplo baseado em um contra cheque e em uma fatura de cartão reais.
Idempotente: se o cenário já existe, apenas garante os usuários e categorias.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    Category,
    CategoryKind,
    CreditCardInstallment,
    DailyExpense,
    FixedExpense,
    FixedExpensePayment,
    Income,
    PaymentMethod,
    Role,
    User,
    VariableGoal,
)
from app.security import hash_password
from app.services.importers import parse_statement_csv

_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_FATURA = _ROOT / "app/static/samples/fatura_nubank_exemplo.csv"

CATEGORIES = [
    ("Moradia", CategoryKind.fixa),
    ("Educação", CategoryKind.fixa),
    ("Saúde", CategoryKind.ambos),
    ("Alimentação", CategoryKind.variavel),
    ("Mercado", CategoryKind.variavel),
    ("Feira", CategoryKind.variavel),
    ("Farmácia", CategoryKind.variavel),
    ("Transporte", CategoryKind.variavel),
    ("Vestuário", CategoryKind.variavel),
    ("Amazon", CategoryKind.variavel),
    ("Tecnologia", CategoryKind.variavel),
    ("Lazer", CategoryKind.variavel),
    ("Igreja/Doação", CategoryKind.variavel),
    ("Assinaturas", CategoryKind.fixa),
    ("Cartão de Crédito", CategoryKind.variavel),
    ("Outros", CategoryKind.variavel),
]

# (descrição, categoria, valor, dia venc.)
FIXED = [
    ("Aluguel", "Moradia", 2500.00, 5),
    ("Escola do Biel", "Educação", 1450.00, 8),
    ("Internet (Net)", "Moradia", 129.90, 10),
    ("Água", "Moradia", 95.00, 12),
    ("IPTU", "Moradia", 210.00, 15),
    ("Natação", "Educação", 260.00, 5),
    ("Judô", "Educação", 220.00, 5),
    ("Yoga", "Saúde", 180.00, 5),
    ("Seguro do carro", "Transporte", 320.00, 20),
    ("Academia", "Saúde", 149.90, 6),
    ("Anthropic / Claude", "Assinaturas", 110.00, 3),
]

GOALS = [
    ("Alimentação", 0.08),
    ("Mercado", 0.10),
    ("Farmácia", 0.02),
    ("Transporte", 0.06),
    ("Lazer", 0.05),
]


def get_or_create_user(db, name, email, password, role) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(name=name, email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        cats: dict[str, Category] = {}
        for name, kind in CATEGORIES:
            c = db.scalar(select(Category).where(Category.name == name))
            if not c:
                c = Category(name=name, kind=kind)
                db.add(c)
                db.flush()
            cats[name] = c

        admin = get_or_create_user(
            db, settings.admin_name, settings.admin_email, settings.admin_password, Role.admin
        )
        get_or_create_user(db, "Usuário Demo", "user@orcamento.com.br", "user123", Role.user)
        db.commit()

        if db.scalar(select(Income).where(Income.user_id == admin.id)):
            print("Cenário de demonstração já existe. Usuários e categorias garantidos.")
            return

        # Receita (contra cheque real de Ago/2026, replicada em Set/2026).
        for y, m in ((2026, 8), (2026, 9)):
            db.add(
                Income(
                    user_id=admin.id, year=y, month=m, description="Salário",
                    source="Contra cheque", gross_amount=19114.09, net_amount=13559.58,
                    received_date=date(y, 9 if m == 8 else 10, 4),
                )
            )

        # Despesas fixas + baixa de pagamento em Ago/2026.
        for desc, cat, amount, due in FIXED:
            fx = FixedExpense(
                user_id=admin.id, category_id=cats[cat].id, description=desc,
                amount=amount, due_day=due, active=True,
            )
            db.add(fx)
            db.flush()
            db.add(
                FixedExpensePayment(
                    fixed_expense_id=fx.id, year=2026, month=8, paid=True,
                    paid_date=date(2026, 8, due), amount_paid=amount,
                )
            )

        # Metas de gasto variável (fração da renda líquida).
        for cat, rate in GOALS:
            db.add(
                VariableGoal(
                    user_id=admin.id, category_id=cats[cat].id,
                    year=0, month=0, target_rate=rate,
                )
            )

        # Importa a fatura real do cartão (Set/2026): lançamentos + parcelas.
        if SAMPLE_FATURA.exists():
            content = SAMPLE_FATURA.read_text(encoding="utf-8")
            parsed = parse_statement_csv(content, layout="cartao")
            for p in parsed:
                cat_id = cats.get("Cartão de Crédito").id
                if (p.installment_total or 0) > 1:
                    offset = (p.installment_current or 1) - 1
                    sm0 = (9 - 1) - offset
                    sy = 2026 + (sm0 // 12)
                    sm = (sm0 % 12) + 1
                    db.add(
                        CreditCardInstallment(
                            user_id=admin.id, category_id=cat_id, description=p.description,
                            card="Nubank", installment_amount=p.amount,
                            installments_total=p.installment_total, start_year=sy, start_month=sm,
                        )
                    )
                else:
                    db.add(
                        DailyExpense(
                            user_id=admin.id, category_id=cat_id, expense_date=p.expense_date,
                            description=p.description, amount=p.amount,
                            payment_method=PaymentMethod.credito,
                        )
                    )

        db.commit()
        print("Seed concluído.")
        print(f"  Admin: {settings.admin_email} / {settings.admin_password}")
        print("  Usuário: user@orcamento.com.br / user123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
