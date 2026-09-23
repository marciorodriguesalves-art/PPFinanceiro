from fastapi import APIRouter

from app.api.routes import (
    auth,
    categories,
    daily_expenses,
    dashboard,
    fixed_expenses,
    goals,
    imports,
    incomes,
    installments,
    reports,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["usuários"])
api_router.include_router(categories.router, prefix="/categories", tags=["categorias"])
api_router.include_router(incomes.router, prefix="/incomes", tags=["receitas"])
api_router.include_router(fixed_expenses.router, prefix="/fixed-expenses", tags=["despesas fixas"])
api_router.include_router(daily_expenses.router, prefix="/daily-expenses", tags=["gastos diários"])
api_router.include_router(installments.router, prefix="/installments", tags=["parcelas"])
api_router.include_router(goals.router, prefix="/goals", tags=["metas"])
api_router.include_router(imports.router, prefix="/imports", tags=["importação"])
api_router.include_router(reports.router, prefix="/reports", tags=["relatórios"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
