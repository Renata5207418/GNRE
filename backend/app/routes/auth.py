import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.auth_models import  UsuarioGNRE, RecuperacaoSenhaGNRE
from app.config import settings
from app.database import get_db
from app.services.auth_service import (
    COOKIE_SESSAO,
    autenticar,
    criar_recuperacao,
    criar_sessao,
    hash_token,
    encerrar_sessao,
    registrar,
    redefinir_senha,
    usuario_da_sessao,
)
from app.services.email_service import email_configurado, enviar_recuperacao


log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"],
)


def verificar_origem(request: Request) -> None:
    """
    Bloqueia operações originadas de
    páginas externas não autorizadas.
    """
    if request.method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:
        origem = request.headers.get("origin")

        permitidas = set(
            settings.cors_origins_list
        )

        permitidas.add(f"{request.url.scheme}://{request.url.netloc}")

        if origem and origem not in permitidas:
            raise HTTPException(
                status_code=403,
                detail="Origem não autorizada.",
            )


class Cadastro(BaseModel):
    nome: str = Field(
        min_length=2,
        max_length=120,
    )

    email: EmailStr

    senha: str = Field(
        min_length=12,
        max_length=128,
    )


class Login(BaseModel):
    email: EmailStr
    senha: str
    lembrar: bool = False


class SolicitarReset(BaseModel):
    email: EmailStr


class RedefinirSenha(BaseModel):
    token: str = Field(
        min_length=20,
        max_length=200,
    )

    nova_senha: str = Field(
        min_length=12,
        max_length=128,
    )


def dados_usuario(usuario: UsuarioGNRE) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
    }


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> UsuarioGNRE:
    usuario = usuario_da_sessao(db, request.cookies.get(COOKIE_SESSAO))

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Sessão ausente ou expirada.",
        )

    return usuario


@router.post("/cadastro", status_code=201)
def cadastrar(payload: Cadastro, db: Session = Depends(get_db)):
    try:
        usuario = registrar(
            db,
            nome=payload.nome,
            email=str(payload.email),
            senha=payload.senha,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return dados_usuario(usuario)


@router.post("/login")
def entrar(payload: Login, response: Response, db: Session = Depends(get_db)):
    usuario = autenticar(
        db,
        email=str(payload.email),
        senha=payload.senha,
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "E-mail ou senha inválidos, "
                "ou acesso temporariamente bloqueado."
            ),
        )

    token, duracao = criar_sessao(
        db,
        usuario.id,
        lembrar=payload.lembrar,
    )

    response.set_cookie(
        key=COOKIE_SESSAO,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="strict",
        max_age=duracao,
        path="/api",
    )

    return dados_usuario(usuario)


@router.get("/me")
def perfil(usuario: UsuarioGNRE = Depends(usuario_atual)):
    return dados_usuario(usuario)


@router.post("/logout")
def sair(request: Request, response: Response, db: Session = Depends(get_db)):
    encerrar_sessao(db, request.cookies.get(COOKIE_SESSAO))

    response.delete_cookie(
        key=COOKIE_SESSAO,
        path="/api",
        samesite="strict",
        secure=settings.AUTH_COOKIE_SECURE,
    )

    return {"ok": True}


@router.get("/recuperacao-disponivel")
def recuperacao_disponivel():
    return {
        "disponivel": email_configurado()
    }


@router.post("/esqueci-senha")
def esqueci_senha(payload: SolicitarReset, db: Session = Depends(get_db)):
    if not email_configurado():
        raise HTTPException(
            status_code=503,
            detail=(
                "Recuperação por e-mail "
                "ainda não configurada."
            ),
        )

    usuario = db.scalar(
        select(UsuarioGNRE).where(
            UsuarioGNRE.email
            == str(payload.email).strip().lower()
        )
    )

    if usuario and usuario.ativo:
        token = criar_recuperacao(
            db,
            usuario,
        )

        if token:
            try:
                enviar_recuperacao(
                    usuario.email,
                    token,
                )

            except Exception:
                db.execute(
                    delete(RecuperacaoSenhaGNRE).where(
                        RecuperacaoSenhaGNRE.token_hash
                        == hash_token(token)
                    )
                )

                db.commit()

                log.exception(
                    "Falha ao enviar e-mail "
                    "de recuperação GNRE"
                )

                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Serviço de e-mail indisponível. "
                        "Tente mais tarde."
                    ),
                )

    return {
        "mensagem": (
            "Se o e-mail estiver cadastrado, "
            "enviaremos instruções de recuperação."
        )
    }


@router.post("/redefinir-senha")
def redefinir(payload: RedefinirSenha, db: Session = Depends(get_db)):
    try:
        sucesso = redefinir_senha(
            db,
            token=payload.token,
            nova_senha=payload.nova_senha,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if not sucesso:
        raise HTTPException(
            status_code=400,
            detail=(
                "Link inválido, expirado "
                "ou já utilizado."
            ),
        )

    return {
        "mensagem": (
            "Senha redefinida. "
            "Entre novamente na sua conta."
        )
    }
