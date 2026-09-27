"""Simulação realista de um ano de uso do sistema.

Gera, para o usuário administrador:
- **Despesas fixas** constantes o ano todo (não mudam de mês a mês).
- **Gastos diários** e **parcelas de cartão** que VARIAM: meses regulares e meses
  de gasto elevado (IPVA/seguro em março, férias em julho, Natal em dezembro,
  IPTU/material escolar em janeiro), com compras de impulso concentradas em fins
  de semana e microtransações — tudo para exercitar o laudo comportamental.
- **Receita** mensal constante + entradas atípicas (Bônus/PLR em março, 13º em
  dezembro) para acionar o detector de "contabilidade mental".
- Um **ano anterior (2025)** como baseline mais baixo, para o Dashboard comparar
  (CY×PY) e o motor detectar inflação do estilo de vida em 2026.

Uso:
    python -m scripts.simulate

É reprodutível (semente fixa) e idempotente: limpa os dados de 2025/2026 do
usuário antes de gerar de novo. Não altera categorias nem metas existentes.
"""

from __future__ import annotations

import calendar
import random
from datetime import date

from sqlalchemy import delete, extract, select

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

ANOS = (2025, 2026)
HOJE = date(2026, 9, 26)
CC = PaymentMethod.credito

# Categorias padrão (nome, natureza) — criadas se não existirem.
CATEGORIAS = [
    ("Moradia", CategoryKind.fixa),
    ("Educação", CategoryKind.fixa),
    ("Assinaturas", CategoryKind.fixa),
    ("Saúde", CategoryKind.ambos),
    ("Alimentação", CategoryKind.variavel),
    ("Mercado", CategoryKind.variavel),
    ("Farmácia", CategoryKind.variavel),
    ("Transporte", CategoryKind.variavel),
    ("Vestuário", CategoryKind.variavel),
    ("Amazon", CategoryKind.variavel),
    ("Tecnologia", CategoryKind.variavel),
    ("Lazer", CategoryKind.variavel),
    ("Outros", CategoryKind.variavel),
]

# Despesas fixas constantes o ano todo (descrição, categoria, valor, dia venc.).
FIXAS = [
    ("Aluguel", "Moradia", 2500.00, 5),
    ("Condomínio", "Moradia", 620.00, 10),
    ("Energia", "Moradia", 240.00, 12),
    ("Água", "Moradia", 95.00, 12),
    ("Internet", "Moradia", 129.90, 10),
    ("Escola do filho", "Educação", 1450.00, 8),
    ("Plano de saúde", "Saúde", 890.00, 6),
    ("Streamings", "Assinaturas", 89.90, 3),
    ("Academia", "Assinaturas", 149.90, 6),
]

# Metas padrão por categoria (fração da receita líquida).
METAS = {
    "Alimentação": 0.08,
    "Transporte": 0.05,
    "Lazer": 0.04,
    "Vestuário": 0.03,
    "Amazon": 0.02,
    "Mercado": 0.10,
}

# Perfil de 2026: nível de gasto e eventos por mês.
PERFIL = {
    1: {"nivel": "alto", "sazonais": [
        ("IPTU 2026", "Moradia", 1250.0, PaymentMethod.boleto),
        ("Material escolar", "Educação", 780.0, PaymentMethod.debito)]},
    2: {"nivel": "regular"},
    3: {"nivel": "alto", "bonus": True, "sazonais": [
        ("IPVA 2026", "Transporte", 1180.0, PaymentMethod.boleto),
        ("Seguro do carro", "Transporte", 980.0, PaymentMethod.boleto)]},
    4: {"nivel": "regular"},
    5: {"nivel": "regular"},
    6: {"nivel": "regular", "micro": True},
    7: {"nivel": "alto", "sazonais": [
        ("Passagens aéreas férias", "Lazer", 1900.0, CC),
        ("Hotel férias", "Lazer", 1400.0, CC)]},
    8: {"nivel": "regular"},
    9: {"nivel": "regular"},
    10: {"nivel": "regular"},
    11: {"nivel": "regular", "micro": True},
    12: {"nivel": "alto", "decimo": True, "sazonais": [
        ("Presentes de Natal", "Lazer", 900.0, CC),
        ("Presente Natal família", "Vestuário", 650.0, CC)]},
}

# Parcelamentos que atravessam os meses (desc, categoria, valor, nº, ano, mês início).
PARCELAS = [
    ("Notebook Dell", "Tecnologia", 450.00, 10, 2026, 2),
    ("Curso de idiomas", "Educação", 120.00, 8, 2026, 4),
    ("Viagem parcelada", "Lazer", 380.00, 6, 2026, 7),
    ("Tênis de corrida", "Vestuário", 165.00, 5, 2026, 8),
    ("Geladeira", "Outros", 210.00, 12, 2026, 9),
    # Baseline 2025 (menos e menores).
    ("Celular", "Tecnologia", 250.00, 10, 2025, 3),
    ("Sofá", "Outros", 300.00, 6, 2025, 7),
]


def _weekends(year: int, month: int) -> list[date]:
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, n + 1) if date(year, month, d).weekday() >= 5]


def _any_day(year: int, month: int) -> date:
    return date(year, month, random.randint(1, calendar.monthrange(year, month)[1]))


def _rng(a: float, b: float) -> float:
    return round(random.uniform(a, b), 2)


def gerar_receita(db, uid, year, month, *, bonus=False, decimo=False):
    db.add(Income(
        user_id=uid, year=year, month=month, description="Salário", source="Contra cheque",
        gross_amount=19114.09, net_amount=13559.58, received_date=date(year, month, 5),
    ))
    if bonus:
        db.add(Income(
            user_id=uid, year=year, month=month, description="Bônus PLR", source="Empresa",
            gross_amount=4200.00, net_amount=4200.00, received_date=date(year, month, 20),
        ))
    if decimo:
        db.add(Income(
            user_id=uid, year=year, month=month, description="13º Salário", source="Empresa",
            gross_amount=6800.00, net_amount=6800.00, received_date=date(year, month, 20),
        ))


def _add(db, uid, cat, cname, d, desc, amount, method=CC):
    db.add(DailyExpense(
        user_id=uid, category_id=cat.get(cname), expense_date=d,
        description=desc, amount=round(amount, 2), payment_method=method,
    ))


def gerar_mes(db, uid, cat, year, month, nivel, *, micro=False, sazonais=None):
    wends = _weekends(year, month)
    base = 0.85 if year == 2025 else 1.0  # baseline mais baixo no ano anterior

    for _ in range(4):  # mercado semanal
        _add(db, uid, cat, "Mercado", _any_day(year, month), "Supermercado", _rng(260, 430) * base)

    n_food = 12 if nivel == "alto" else 6
    for _ in range(n_food):  # alimentação / delivery (fim de semana)
        d = random.choice(wends) if wends and random.random() < 0.6 else _any_day(year, month)
        desc = random.choice(["Restaurante", "iFood", "Padaria", "Bar", "Delivery"])
        _add(db, uid, cat, "Alimentação", d, desc, _rng(38, 210) * base)

    for _ in range(12 if nivel == "alto" else 8):  # transporte (Uber), em pares
        _add(db, uid, cat, "Transporte", _any_day(year, month), "Uber", _rng(18, 36))

    for _ in range(random.randint(1, 3)):
        _add(db, uid, cat, "Farmácia", _any_day(year, month), "Farmácia", _rng(28, 120))

    if random.random() < 0.4:
        _add(db, uid, cat, "Saúde", _any_day(year, month),
             random.choice(["Consulta", "Exame", "Fisioterapia"]), _rng(120, 340))

    n_imp = 8 if nivel == "alto" else 3  # impulso, concentrado em fins de semana
    faixa = (80, 480) if nivel == "alto" else (45, 220)
    rotulos = {"Lazer": "Cinema/Lazer", "Vestuário": "Loja de roupas",
               "Amazon": "Compra Amazon", "Tecnologia": "Eletrônicos"}
    for _ in range(n_imp):
        c = random.choice(list(rotulos))
        d = random.choice(wends) if wends and random.random() < 0.7 else _any_day(year, month)
        _add(db, uid, cat, c, d, rotulos[c], _rng(*faixa) * base)

    if micro or nivel == "alto":  # microtransações que passam despercebidas
        for _ in range(random.randint(8, 12)):
            _add(db, uid, cat, "Outros", _any_day(year, month),
                 random.choice(["Café", "App", "Lanche", "Banca", "Pedágio"]), _rng(6, 34))

    for desc, cname, val, method in (sazonais or []):
        _add(db, uid, cat, cname, date(year, month, 15), desc, val, method)


def _limpar(db, uid):
    db.execute(delete(Income).where(Income.user_id == uid, Income.year.in_(ANOS)))
    db.execute(delete(DailyExpense).where(
        DailyExpense.user_id == uid,
        extract("year", DailyExpense.expense_date).in_(ANOS),
    ))
    db.execute(delete(CreditCardInstallment).where(CreditCardInstallment.user_id == uid))


def _ensure_categorias(db) -> dict:
    existentes = {c.name: c for c in db.scalars(select(Category)).all()}
    for nome, kind in CATEGORIAS:
        if nome not in existentes:
            c = Category(name=nome, kind=kind)
            db.add(c)
            existentes[nome] = c
    db.flush()
    return {nome: c.id for nome, c in existentes.items()}


def _reset_fixas(db, uid, cat) -> list[FixedExpense]:
    """Substitui as despesas fixas do usuário pelo conjunto limpo da simulação,
    para não herdar itens do seed antigo (ex.: fixos com nome sazonal)."""
    ids = [f.id for f in db.scalars(
        select(FixedExpense).where(FixedExpense.user_id == uid)
    ).all()]
    if ids:
        db.execute(delete(FixedExpensePayment).where(
            FixedExpensePayment.fixed_expense_id.in_(ids)))
        db.execute(delete(FixedExpense).where(FixedExpense.id.in_(ids)))
    db.flush()
    novas = [
        FixedExpense(user_id=uid, category_id=cat.get(cn), description=desc,
                     amount=val, due_day=dia, active=True)
        for desc, cn, val, dia in FIXAS
    ]
    db.add_all(novas)
    db.flush()
    return novas


def _ensure_metas(db, uid, cat):
    existentes = {
        g.category_id for g in db.scalars(
            select(VariableGoal).where(VariableGoal.user_id == uid)
        ).all()
    }
    for nome, rate in METAS.items():
        cid = cat.get(nome)
        if cid and cid not in existentes:
            db.add(VariableGoal(user_id=uid, category_id=cid, year=0, month=0, target_rate=rate))
    db.flush()


def main() -> None:
    random.seed(42)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == settings.admin_email))
        if admin is None:
            admin = User(
                name=settings.admin_name, email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password), role=Role.admin,
            )
            db.add(admin)
            db.flush()
        uid = admin.id

        cat = _ensure_categorias(db)
        fixas = _reset_fixas(db, uid, cat)
        _ensure_metas(db, uid, cat)
        _limpar(db, uid)

        # Receitas + gastos, ano a ano.
        for year in ANOS:
            for month in range(1, 13):
                cfg = PERFIL[month] if year == 2026 else {"nivel": "regular"}
                gerar_receita(db, uid, year, month,
                              bonus=cfg.get("bonus", False), decimo=cfg.get("decimo", False))
                gerar_mes(db, uid, cat, year, month, cfg["nivel"],
                          micro=cfg.get("micro", False), sazonais=cfg.get("sazonais"))

        # Parcelamentos ao longo dos meses.
        for desc, cname, val, total, ano, mes in PARCELAS:
            db.add(CreditCardInstallment(
                user_id=uid, category_id=cat.get(cname), description=desc, card="Cartão",
                installment_amount=val, installments_total=total, start_year=ano, start_month=mes,
            ))

        # Baixa de pagamento das fixas nos meses passados.
        for f in fixas:
            for year in ANOS:
                for month in range(1, 13):
                    if date(year, month, 28) <= HOJE:
                        db.add(FixedExpensePayment(
                            fixed_expense_id=f.id, year=year, month=month, paid=True,
                            paid_date=date(year, month, min(f.due_day or 5, 28)),
                            amount_paid=f.amount,
                        ))

        db.commit()

        # Resumo.
        for year in ANOS:
            diarios = db.scalars(select(DailyExpense.amount).where(
                DailyExpense.user_id == uid,
                extract("year", DailyExpense.expense_date) == year,
            )).all()
            soma = sum(float(v) for v in diarios)
            print(f"{year}: {len(diarios)} gastos diários — soma R$ {soma:,.2f}")
        print("Simulação concluída para", settings.admin_email)
    finally:
        db.close()


if __name__ == "__main__":
    main()
