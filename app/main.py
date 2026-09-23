from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import api_router
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title=settings.app_name,
    description="Sistema de Controle Orçamentário — MVP (FastAPI + PostgreSQL)",
    version="0.1.0",
)

app.include_router(api_router)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/health", tags=["infra"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html", {"request": request, "app_name": settings.app_name}
    )
