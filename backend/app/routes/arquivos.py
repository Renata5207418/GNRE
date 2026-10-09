from __future__ import annotations
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.export_service import filtros_guias, gerar_excel_guias
from app.services.pdf_service import (
    LimiteZIPExcedido,
    PDFInvalido,
    decodificar_pdf,
    iterar_arquivo,
    montar_zip_guias,
    nome_pdf_seguro,
    obter_guia_com_pdf,
)


router = APIRouter(prefix="/guias", tags=["Guias - Arquivos"])


class SelecionarGuias(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)

    @field_validator("ids")
    @classmethod
    def conferir_ids(cls, ids: list[int]) -> list[int]:
        if any(guia_id <= 0 for guia_id in ids):
            raise ValueError("Todos os IDs devem ser positivos.")
        return list(dict.fromkeys(ids))


def interpretar_ids_csv(ids: str | None) -> list[int] | None:
    if ids is None:
        return None
    try:
        numeros = list(dict.fromkeys(int(v.strip()) for v in ids.split(",")))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="O parâmetro 'ids' deve conter números separados por vírgula.",
        ) from exc

    if not numeros or len(numeros) > 200 or any(n <= 0 for n in numeros):
        raise HTTPException(
            status_code=422,
            detail="Informe de 1 a 200 IDs inteiros positivos.",
        )
    return numeros


@router.get("/{guia_id}/pdf")
def baixar_pdf(
    guia_id: int,
    visualizar: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    guia = obter_guia_com_pdf(db, guia_id)
    if guia is None:
        raise HTTPException(404, detail="Guia GNRE não encontrada.")

    try:
        conteudo_pdf = decodificar_pdf(guia.pdf_base64)
    except PDFInvalido as exc:
        raise HTTPException(409, detail=str(exc)) from exc

    nome = nome_pdf_seguro(guia.get_pdf_name())
    disposicao = "inline" if visualizar else "attachment"
    return Response(
        content=conteudo_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposicao}; filename="{nome}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/download-lote")
def baixar_pdfs_em_zip(
    dados: SelecionarGuias,
    db: Session = Depends(get_db),
):
    try:
        arquivo, incluidos, ignorados = montar_zip_guias(db, dados.ids)
    except LimiteZIPExcedido as exc:
        raise HTTPException(413, detail=str(exc)) from exc
    except PDFInvalido as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc

    return StreamingResponse(
        iterar_arquivo(arquivo),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="guias_selecionadas.zip"',
            "Cache-Control": "private, no-store",
            "X-Guias-Incluidas": str(incluidos),
            "X-Guias-Ignoradas": str(ignorados),
        },
    )


@router.get("/exportar/excel")
def exportar_resultados_excel(
    ids: str | None = Query(default=None),
    codigo_dominio: str | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    ano: int | None = None,
    status: str | None = None,
    uf_favorecida: str | None = Query(default=None, min_length=2, max_length=2),
    db: Session = Depends(get_db),
):
    filtros = filtros_guias(
        ids=interpretar_ids_csv(ids),
        codigo_dominio=codigo_dominio,
        mes=mes,
        ano=ano,
        status=status,
        uf_favorecida=uf_favorecida,
    )

    try:
        arquivo, total = gerar_excel_guias(db, filtros=filtros)
    except ValueError as exc:
        raise HTTPException(413, detail=str(exc)) from exc

    nome = f"resultado_gnre_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return StreamingResponse(
        iterar_arquivo(arquivo),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{nome}"',
            "Cache-Control": "private, no-store",
            "X-Total-Exportado": str(total),
        },
    )
