from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base, engine


# ==========================================
# DATA/HORA UTC
# ==========================================
def agora_utc() -> datetime:
    """
    Retorna o horário UTC sem timezone
    para armazenamento consistente no SQLite.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ==========================================
# USUÁRIOS GNRE
# ==========================================
class UsuarioGNRE(Base):
    """
    Usuários cadastrados no sistema.

    Todos possuem as mesmas permissões.
    Não existe distinção entre administrador
    e usuário comum.
    """
    __tablename__ = "gnre_usuarios"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    nome: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        index=True,
        nullable=False,
    )

    # Armazena somente o hash Argon2.
    # A senha original nunca é salva.

    senha_hash: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Contador de tentativas incorretas
    # utilizado pelo auth_service.py.

    erros_login: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Bloqueio temporário após
    # várias tentativas incorretas.

    bloqueado_ate: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )


# ==========================================
# SESSÕES DOS USUÁRIOS
# ==========================================
class SessaoGNRE(Base):
    """
    Sessões de usuários autenticados.

    Guarda somente o hash SHA-256 do token.

    O token original é enviado ao navegador
    por um cookie HttpOnly.
    """
    __tablename__ = "gnre_sessoes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("gnre_usuarios.id"),
        index=True,
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    expira_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )


# ==========================================
# RECUPERAÇÃO DE SENHA
# ==========================================
class RecuperacaoSenhaGNRE(Base):
    """
    Tokens temporários de recuperação.

    O token original é enviado por e-mail.

    No SQLite fica armazenado apenas
    o hash SHA-256 do token.

    Cada link pode ser utilizado uma vez.
    """
    __tablename__ = "gnre_recuperacoes_senha"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    usuario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("gnre_usuarios.id"),
        index=True,
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    expira_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    usado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=agora_utc,
    )


# ==========================================
# CRIAÇÃO DAS TABELAS
# ==========================================
def criar_tabelas_auth() -> None:
    """
    Cria apenas as tabelas de autenticação.

    checkfirst=True evita tentar recriar
    uma tabela que já existe.

    Não altera as tabelas antigas.
    """
    tabelas = (
        UsuarioGNRE.__table__,
        SessaoGNRE.__table__,
        RecuperacaoSenhaGNRE.__table__,
    )

    for tabela in tabelas:
        tabela.create(
            bind=engine,
            checkfirst=True,
        )
