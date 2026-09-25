"""Rotas FastAPI da camada comportamental.

Monte no app com:  app.include_router(comportamental_router)
Ajuste `get_db` e `usuario_atual` para as dependências reais do seu projeto.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User

from . import models, schemas, services


def usuario_atual(current: User = Depends(get_current_user)) -> int:
    """Adapta a dependência de auth do projeto para o id do usuário logado."""
    return current.id


router = APIRouter(prefix="/comportamental", tags=["comportamental"])


# --- Diagnóstico -----------------------------------------------------------
@router.post("/diagnosticos", response_model=schemas.DiagnosticoOut)
def gerar_diagnostico(
    payload: schemas.GerarDiagnosticoIn,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    """Roda o motor de diagnóstico sobre o período e (opcional) persiste."""
    diag = services.gerar_diagnostico_para_usuario(
        db, usuario_id, payload.periodo, persistir=payload.persistir
    )
    return schemas.DiagnosticoOut(
        periodo=diag.periodo,
        total_analisado=diag.total_analisado,
        qtd_lancamentos=diag.qtd_lancamentos,
        padroes=[schemas.PadraoOut(**p.to_dict()) for p in diag.padroes],
        ressalvas=diag.ressalvas,
    )


@router.get("/diagnosticos/{periodo}", response_model=schemas.DiagnosticoOut)
def obter_diagnostico(
    periodo: str,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    registro = db.scalar(
        select(models.Diagnostico).where(
            models.Diagnostico.usuario_id == usuario_id,
            models.Diagnostico.periodo == periodo,
        )
    )
    if not registro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnóstico não encontrado.")
    return schemas.DiagnosticoOut(
        id=registro.id,
        periodo=registro.periodo,
        total_analisado=registro.total_analisado,
        qtd_lancamentos=registro.qtd_lancamentos,
        gerado_em=registro.gerado_em,
        padroes=[schemas.PadraoOut.model_validate(p) for p in registro.padroes],
        ressalvas=[r.texto for r in registro.ressalvas],
    )


# --- Metas sugeridas a partir do diagnóstico -------------------------------
@router.get("/metas-sugeridas/{periodo}")
def metas_sugeridas(
    periodo: str,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    """Tetos de gasto propostos por categoria (editáveis) com base no mês."""
    return services.sugerir_metas(db, usuario_id, periodo)


# --- Recorrências (raio-x) -------------------------------------------------
@router.get("/recorrencias/anualizado")
def recorrencias_anualizadas(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    recs = db.scalars(
        select(models.Recorrencia).where(models.Recorrencia.usuario_id == usuario_id)
    ).all()
    return services.anualizar_recorrencias(recs)


@router.post("/recorrencias", response_model=schemas.RecorrenciaOut, status_code=201)
def criar_recorrencia(
    payload: schemas.RecorrenciaCreate,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    rec = models.Recorrencia(usuario_id=usuario_id, **payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# --- Reservas sazonais (caixinhas) -----------------------------------------
@router.post("/reservas", response_model=schemas.ReservaSazonalOut, status_code=201)
def criar_reserva(
    payload: schemas.ReservaSazonalCreate,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    reserva = models.ReservaSazonal(usuario_id=usuario_id, **payload.model_dump())
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva


@router.get("/reservas", response_model=list[schemas.ReservaSazonalOut])
def listar_reservas(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(usuario_atual),
):
    return db.scalars(
        select(models.ReservaSazonal).where(
            models.ReservaSazonal.usuario_id == usuario_id
        )
    ).all()
