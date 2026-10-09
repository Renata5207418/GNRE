from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.routes.auth import usuario_atual
from app.auth_models import UsuarioGNRE
from app.services.certificado_service import (
    TAMANHO_MAXIMO_PFX,
    cadastrar_certificado,
    desativar_certificado,
    listar_certificados,
    listar_vinculos,
    vincular_certificado,
)


router = APIRouter(
    prefix="/certificados",
    tags=["Certificados digitais"],
)


class VinculoEntrada(BaseModel):
    codigo_dominio: str = Field(
        min_length=1,
        max_length=100,
    )

    certificado_id: int = Field(gt=0)


@router.get("")
def certificados(db: Session = Depends(get_db)):
    return listar_certificados(db)


@router.get("/vinculos")
def vinculos(db: Session = Depends(get_db)):
    return listar_vinculos(db)


@router.post("", status_code=201)
async def adicionar(
    arquivo: UploadFile = File(...),
    senha: str = Form(...),
    nome_exibicao: str = Form(...),
    db: Session = Depends(get_db),
    usuario: UsuarioGNRE = Depends(usuario_atual),
):
    try:
        dados = await arquivo.read(
            TAMANHO_MAXIMO_PFX + 1
        )

    finally:
        await arquivo.close()

    if len(dados) > TAMANHO_MAXIMO_PFX:
        raise HTTPException(
            status_code=413,
            detail="PFX/P12 maior que 5 MB.",
        )

    try:
        return cadastrar_certificado(
            db,
            nome_arquivo=arquivo.filename or "",
            conteudo_pfx=dados,
            senha=senha,
            nome_exibicao=nome_exibicao,
            usuario=usuario.email,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Certificado já cadastrado.",
        ) from exc


@router.post("/vinculos", status_code=201)
def criar_vinculo(
    entrada: VinculoEntrada,
    db: Session = Depends(get_db),
    usuario: UsuarioGNRE = Depends(usuario_atual),
):
    try:
        return vincular_certificado(
            db,
            codigo_dominio=entrada.codigo_dominio,
            certificado_id=entrada.certificado_id,
            usuario=usuario.email,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Conflito ao vincular certificado.",
        ) from exc


@router.patch("/{certificado_id}/desativar")
def desativar(certificado_id: int, db: Session = Depends(get_db), usuario: UsuarioGNRE = Depends(usuario_atual)):
    try:
        return desativar_certificado(
            db,
            certificado_id,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
