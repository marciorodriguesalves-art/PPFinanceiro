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
