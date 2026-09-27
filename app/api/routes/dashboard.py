from typing import Any

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.action_plan import build_action_plan
from app.services.budget import compute_month_budget
from app.services.present import build_category_spends, build_kpis

router = APIRouter()

Y = Path(ge=2000, le=2100)
M = Path(ge=1, le=12)


@router.get("/overview/{year}/{month}")
def overview(
    year: int = Y,
    month: int = M,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Dados agregados para os dashboards do mês (composição, categorias, KPIs, plano)."""
    mb = compute_month_budget(db, current.id, year, month)
    kpis = build_kpis(mb)
    spends = build_category_spends(mb)
    composicao = [
        {"label": "Despesas fixas", "value": mb.total_fixos},
        {"label": "Gastos variáveis", "value": mb.total_variaveis},
        {"label": "Parcelas cartão", "value": mb.total_parcelas},
    ]
    return {
        "competencia": mb.competencia,
        "kpis": kpis.model_dump(),
        "composicao": composicao,
        "gastos_por_categoria": [s.model_dump() for s in spends],
        "desvios": [s.model_dump() for s in spends if (s.deviation or 0) > 0],
        "plano_acao": build_action_plan(mb).model_dump(),
    }


@router.get("/overview-annual/{year}")
def overview_annual(
    year: int = Y,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Agregado do ANO inteiro (soma dos 12 meses) — mesmo formato do overview
    mensal, para o Dashboard avaliar o ano. Meses sem dados somam zero, então
    funciona mesmo com poucos meses lançados."""
    tot = dict.fromkeys(
        ("receita_liquida", "receita_bruta", "total_gastos", "total_fixos",
         "total_variaveis", "total_parcelas", "saldo_disponivel",
         "investimento_meta", "investimento_previsto"), 0.0,
    )
    cat_amount: dict = {}
    cat_target: dict = {}
    cat_name: dict = {}
    meses_com_dados = 0
    for m in range(1, 13):
        mb = compute_month_budget(db, current.id, year, m)
        if mb.total_gastos > 0 or mb.receita_liquida > 0:
            meses_com_dados += 1
        tot["receita_liquida"] += mb.receita_liquida
        tot["receita_bruta"] += mb.receita_bruta
        tot["total_gastos"] += mb.total_gastos
        tot["total_fixos"] += mb.total_fixos
        tot["total_variaveis"] += mb.total_variaveis
        tot["total_parcelas"] += mb.total_parcelas
        tot["saldo_disponivel"] += mb.saldo_disponivel
        tot["investimento_meta"] += mb.investimento_meta
        tot["investimento_previsto"] += mb.investimento_previsto
        for c in mb.categorias:
            cat_amount[c.category_id] = cat_amount.get(c.category_id, 0.0) + c.amount
            cat_name[c.category_id] = c.category
            if c.target is not None:
                cat_target[c.category_id] = cat_target.get(c.category_id, 0.0) + c.target

    receita = tot["receita_liquida"]
    kpis = {
        **{k: round(v, 2) for k, v in tot.items()},
        "taxa_comprometimento": round(tot["total_gastos"] / receita, 4) if receita > 0 else 0.0,
        "taxa_investimento_prevista": (
            round(tot["investimento_previsto"] / receita, 4) if receita > 0 else 0.0
        ),
        "atende_meta_investimento": (
            tot["investimento_previsto"] >= tot["investimento_meta"]
            and tot["saldo_disponivel"] >= 0
        ),
    }

    categorias = []
    for cid, amount in cat_amount.items():
        target = cat_target.get(cid)
        deviation = round(amount - target, 2) if target is not None else None
        categorias.append({
            "category_id": cid,
            "category": cat_name[cid],
            "amount": round(amount, 2),
            "target": round(target, 2) if target is not None else None,
            "deviation": deviation,
            "deviation_rate": round(deviation / target, 4) if target else None,
        })
    categorias.sort(key=lambda c: c["amount"], reverse=True)

    composicao = [
        {"label": "Despesas fixas", "value": round(tot["total_fixos"], 2)},
        {"label": "Gastos variáveis", "value": round(tot["total_variaveis"], 2)},
        {"label": "Parcelas cartão", "value": round(tot["total_parcelas"], 2)},
    ]
    return {
        "competencia": str(year),
        "meses_com_dados": meses_com_dados,
        "kpis": kpis,
        "composicao": composicao,
        "gastos_por_categoria": categorias,
        "desvios": [c for c in categorias if (c["deviation"] or 0) > 0],
    }


@router.get("/series/{year}")
def series(
    year: int = Y,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Série mensal do ano para gráficos de evolução e saldo por mês."""
    pontos = []
    for m in range(1, 13):
        mb = compute_month_budget(db, current.id, year, m)
        pontos.append(
            {
                "competencia": mb.competencia,
                "mes": m,
                "receita": mb.receita_liquida,
                "gastos": mb.total_gastos,
                "fixos": mb.total_fixos,
                "variaveis": mb.total_variaveis,
                "parcelas": mb.total_parcelas,
                "saldo": mb.saldo_disponivel,
                "investimento": mb.investimento_previsto,
                "meta_investimento": mb.investimento_meta,
            }
        )
    return {"year": year, "pontos": pontos}
