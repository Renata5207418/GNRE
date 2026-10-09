import hashlib
import secrets
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth_models import RecuperacaoSenhaGNRE, SessaoGNRE, UsuarioGNRE, agora_utc


COOKIE_SESSAO = "gnre_session"
HASHEADOR = PasswordHasher()
SEGUNDOS_SESSAO_NORMAL = 12 * 60 * 60
SEGUNDOS_SESSAO_LEMBRAR = 7 * 24 * 60 * 60


def hash_token(token: str) -> str:
    """Guarda somente o SHA-256 do token no banco."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def email_normalizado(email: str) -> str:
    return email.strip().lower()


def validar_senha(senha: str) -> None:
    if not 12 <= len(senha) <= 128:
        raise ValueError("A senha deve ter entre 12 e 128 caracteres.")


def registrar(
    db: Session,
    *,
    nome: str,
    email: str,
    senha: str,
) -> UsuarioGNRE:
    """Cria usuário comum, com acesso igual aos demais usuários."""
    validar_senha(senha)
    nome_limpo = nome.strip()
    if not 2 <= len(nome_limpo) <= 120:
        raise ValueError("O nome deve ter entre 2 e 120 caracteres.")

    usuario = UsuarioGNRE(
        nome=nome_limpo,
        email=email_normalizado(email),
        senha_hash=HASHEADOR.hash(senha),
        ativo=True,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Este e-mail já está cadastrado.") from exc
    db.refresh(usuario)
    return usuario


def autenticar(
    db: Session,
    *,
    email: str,
    senha: str,
) -> UsuarioGNRE | None:
    """Valida credenciais; bloqueia temporariamente após cinco erros."""
    usuario = db.scalar(
        select(UsuarioGNRE).where(
            UsuarioGNRE.email == email_normalizado(email)
        )
    )
    if usuario is None or not usuario.ativo:
        return None

    agora = agora_utc()
    if usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
        return None

    try:
        HASHEADOR.verify(usuario.senha_hash, senha)
    except (VerificationError, InvalidHashError):
        usuario.erros_login = (usuario.erros_login or 0) + 1
        if usuario.erros_login >= 5:
            usuario.bloqueado_ate = agora + timedelta(minutes=15)
            usuario.erros_login = 0
        db.commit()
        return None

    usuario.erros_login = 0
    usuario.bloqueado_ate = None
    if HASHEADOR.check_needs_rehash(usuario.senha_hash):
        usuario.senha_hash = HASHEADOR.hash(senha)
    db.commit()
    return usuario


def criar_sessao(
    db: Session,
    usuario_id: int,
    *,
    lembrar: bool,
) -> tuple[str, int]:
    """Retorna (token aleatório, duração em segundos) para cookie HttpOnly."""
    duracao = (
        SEGUNDOS_SESSAO_LEMBRAR if lembrar else SEGUNDOS_SESSAO_NORMAL
    )
    token = secrets.token_urlsafe(48)
    db.add(
        SessaoGNRE(
            usuario_id=usuario_id,
            token_hash=hash_token(token),
            expira_em=agora_utc() + timedelta(seconds=duracao),
        )
    )
    db.commit()
    return token, duracao


def usuario_da_sessao(db: Session, token: str | None) -> UsuarioGNRE | None:
    if not token:
        return None
    sessao = db.scalar(
        select(SessaoGNRE).where(
            SessaoGNRE.token_hash == hash_token(token)
        )
    )
    if sessao is None or sessao.expira_em <= agora_utc():
        return None
    usuario = db.get(UsuarioGNRE, sessao.usuario_id)
    return usuario if usuario is not None and usuario.ativo else None


def encerrar_sessao(db: Session, token: str | None) -> None:
    if token:
        db.execute(
            delete(SessaoGNRE).where(
                SessaoGNRE.token_hash == hash_token(token)
            )
        )
        db.commit()


def criar_recuperacao(db: Session, usuario: UsuarioGNRE) -> str | None:
    """Gera link de 20 min e evita novo envio em menos de 2 min."""
    agora = agora_utc()
    ultimo = db.scalar(
        select(RecuperacaoSenhaGNRE)
        .where(RecuperacaoSenhaGNRE.usuario_id == usuario.id)
        .order_by(RecuperacaoSenhaGNRE.id.desc())
        .limit(1)
    )
    if ultimo and (agora - ultimo.criado_em).total_seconds() < 120:
        return None

    token = secrets.token_urlsafe(40)
    db.add(
        RecuperacaoSenhaGNRE(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            expira_em=agora + timedelta(minutes=20),
        )
    )
    db.commit()
    return token


def redefinir_senha(
    db: Session,
    *,
    token: str,
    nova_senha: str,
) -> bool:
    """Troca a senha com token único e invalida sessões e links antigos."""
    validar_senha(nova_senha)
    agora = agora_utc()
    resumo = db.scalar(
        select(RecuperacaoSenhaGNRE).where(
            RecuperacaoSenhaGNRE.token_hash == hash_token(token)
        )
    )
    if (
        resumo is None
        or resumo.usado_em is not None
        or resumo.expira_em <= agora
    ):
        return False

    usuario = db.get(UsuarioGNRE, resumo.usuario_id)
    if usuario is None or not usuario.ativo:
        return False

    novo_hash = HASHEADOR.hash(nova_senha)
    # Atualização condicional: um mesmo link não pode ser usado duas vezes.
    confirmado = db.execute(
        update(RecuperacaoSenhaGNRE)
        .where(
            RecuperacaoSenhaGNRE.id == resumo.id,
            RecuperacaoSenhaGNRE.usado_em.is_(None),
            RecuperacaoSenhaGNRE.expira_em > agora,
        )
        .values(usado_em=agora)
    )
    if confirmado.rowcount != 1:
        db.rollback()
        return False

    usuario.senha_hash = novo_hash
    usuario.erros_login = 0
    usuario.bloqueado_ate = None

    db.execute(
        update(RecuperacaoSenhaGNRE)
        .where(
            RecuperacaoSenhaGNRE.usuario_id == usuario.id,
            RecuperacaoSenhaGNRE.usado_em.is_(None),
        )
        .values(usado_em=agora)
    )
    db.execute(
        delete(SessaoGNRE).where(SessaoGNRE.usuario_id == usuario.id)
    )
    db.commit()
    return True
