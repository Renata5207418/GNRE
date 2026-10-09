from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import GNREProcessamento


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/resumo")
def resumo(db: Session = Depends(get_db)):
    """
    Resumo usando o banco SQLite original.
    Somente consultas, sem qualquer alteração nos registros.
    """
    total = db.scalar(select(func.count(GNREProcessamento.id))) or 0
    com_pdf = db.scalar(
        select(func.count(GNREProcessamento.id)).where(
            GNREProcessamento.pdf_base64.is_not(None),
            func.length(GNREProcessamento.pdf_base64) > 0,
        )
    ) or 0

    resultado = db.execute(
        select(
            GNREProcessamento.status,
            func.count(GNREProcessamento.id).label("quantidade"),
        )
        .group_by(GNREProcessamento.status)
        .order_by(GNREProcessamento.status)
    ).all()

    status = [
        {
            "status": nome_status or "Sem status",
            "quantidade": quantidade,
        }
        for nome_status, quantidade in resultado
    ]

    return {
        "total_guias": total,
        "guias_com_pdf": com_pdf,
        "guias_sem_pdf": total - com_pdf,
        "por_status": status,
    }