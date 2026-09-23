from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.reports import ActionPlan, AnnualReport, MonthlyStatement, MonthPoint
from app.services.action_plan import build_action_plan
from app.services.budget import compute_month_budget
from app.services.present import build_category_spends, build_kpis

router = APIRouter()

Y = Path(ge=2000, le=2100)
M = Path(ge=1, le=12)


@router.get("/monthly/{year}/{month}", response_model=MonthlyStatement)
def monthly_statement(
    year: int = Y,
    month: int = M,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> MonthlyStatement:
    """Extrato mensal completo: KPIs, gastos por categoria, desvios e plano de ação."""
    mb = compute_month_budget(db, current.id, year, month)
    plano = build_action_plan(mb)
    spends = build_category_spends(mb)
    desvios = [s for s in spends if s.deviation is not None and s.deviation > 0]
    return MonthlyStatement(
        competencia=mb.competencia,
        kpis=build_kpis(mb),
        gastos_por_categoria=spends,
        desvios=desvios,
        fixos_pendentes=mb.fixos_pendentes,
        plano_acao=plano,
        projecao_economia_12m=round(plano.investimento_projetado_pos_ajuste * 12, 2),
    )


@router.get("/action-plan/{year}/{month}", response_model=ActionPlan)
def action_plan(
    year: int = Y,
    month: int = M,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ActionPlan:
    mb = compute_month_budget(db, current.id, year, month)
    return build_action_plan(mb)


@router.get("/annual/{year}", response_model=AnnualReport)
def annual_report(
    year: int = Y,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> AnnualReport:
    meses: list[MonthPoint] = []
    r_tot = g_tot = s_tot = i_tot = 0.0
    for m in range(1, 13):
        mb = compute_month_budget(db, current.id, year, m)
        meses.append(
            MonthPoint(
                competencia=mb.competencia,
                receita=mb.receita_liquida,
                gastos=mb.total_gastos,
                saldo=mb.saldo_disponivel,
                investimento=mb.investimento_previsto,
            )
        )
        r_tot += mb.receita_liquida
        g_tot += mb.total_gastos
        s_tot += mb.saldo_disponivel
        i_tot += mb.investimento_previsto
    return AnnualReport(
        year=year,
        meses=meses,
        receita_total=round(r_tot, 2),
        gastos_total=round(g_tot, 2),
        saldo_total=round(s_tot, 2),
        investimento_total=round(i_tot, 2),
    )
