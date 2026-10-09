
from datetime import date, datetime
from decimal import Decimal
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import GNREProcessamento


router = APIRouter(prefix="/guias", tags=["Guias"])


class GuiaResumo(BaseModel):
    id: int
    codigo_dominio: str
    numero_recibo: str | None
    status: str
    erro_mensagem: str | None
    data_envio: datetime
    uf_favorecida: str
    inscricao_estadual: str | None
    receita: str
    mes: int
    ano: int
    data_vencimento: date
    valor_tipo_11: Decimal
    tem_pdf: bool


class PaginaGuias(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    total_paginas: int
    items: list[GuiaResumo]


COLUNAS_GUIA = (
    GNREProcessamento.id,
    GNREProcessamento.codigo_dominio,
    GNREProcessamento.numero_recibo,
    GNREProcessamento.status,
    GNREProcessamento.erro_mensagem,
    GNREProcessamento.data_envio,
    GNREProcessamento.uf_favorecida,
    GNREProcessamento.inscricao_estadual,
    GNREProcessamento.receita,
    GNREProcessamento.mes,
    GNREProcessamento.ano,
    GNREProcessamento.data_vencimento,
    GNREProcessamento.valor_tipo_11,
    case(
        (
            func.length(
                GNREProcessamento.pdf_base64
            ) > 0,
            True,
        ),
        else_=False,
    ).label("tem_pdf"),
)


@router.get("", response_model=PaginaGuias)
def listar_guias(
    codigo_dominio: str | None = None,
    mes: int | None = Query(
        default=None,
        ge=1,
        le=12,
    ),
    ano: int | None = None,
    status: str | None = None,
    uf_favorecida: str | None = None,
    pagina: int = Query(
        default=1,
        ge=1,
    ),
    por_pagina: int = Query(
        default=30,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    """
    Lista as guias GNRE com filtros e paginação.
    """

    filtros = []

    if codigo_dominio:
        filtros.append(
            GNREProcessamento.codigo_dominio
            == codigo_dominio
        )

    if mes is not None:
        filtros.append(
            GNREProcessamento.mes == mes
        )

    if ano is not None:
        filtros.append(
            GNREProcessamento.ano == ano
        )

    if status:
        filtros.append(
            GNREProcessamento.status == status
        )

    if uf_favorecida:
        filtros.append(
            GNREProcessamento.uf_favorecida
            == uf_favorecida.upper()
        )

    consulta_total = (
        select(func.count(GNREProcessamento.id))
        .where(*filtros)
    )

    total = db.scalar(consulta_total) or 0

    offset = (pagina - 1) * por_pagina

    consulta = (
        select(*COLUNAS_GUIA)
        .where(*filtros)
        .order_by(GNREProcessamento.id.desc())
        .offset(offset)
        .limit(por_pagina)
    )

    resultados = db.execute(consulta).all()

    items = [
        GuiaResumo.model_validate(
            dict(resultado._mapping)
        )
        for resultado in resultados
    ]

    total_paginas = (
        (total + por_pagina - 1) // por_pagina
    )

    return PaginaGuias(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        total_paginas=total_paginas,
        items=items,
    )


@router.get("/{guia_id}", response_model=GuiaResumo)
def detalhar_guia(guia_id: int, db: Session = Depends(get_db)):
    """
    Retorna os detalhes de uma guia pelo ID.
    """
    consulta = (
        select(*COLUNAS_GUIA)
        .where(GNREProcessamento.id == guia_id)
    )

    resultado = db.execute(consulta).first()

    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Guia GNRE não encontrada.",
        )

    return GuiaResumo.model_validate(
        dict(resultado._mapping)
    )
