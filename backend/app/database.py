from collections.abc import Generator
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import settings


class Base(DeclarativeBase):
    pass


DATABASE_URL = URL.create(
    drivername="sqlite+pysqlite",
    database=str(settings.database_file),
)


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    pool_pre_ping=True,
    echo=False,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def validar_banco_original() -> None:
    """
    Confere se o SQLite original existe e possui
    a tabela e as colunas necessárias.

    Não cria nem altera tabelas.
    """
    caminho = settings.database_file

    if not caminho.is_file():
        raise RuntimeError(
            "Banco SQLite não encontrado: "
            f"{caminho}. "
            "Copie o db.sqlite3 original para "
            "backend/data/db.sqlite3."
        )

    from app.models import GNREProcessamento

    nome_tabela = GNREProcessamento.__tablename__
    inspector = inspect(engine)
    tabelas = inspector.get_table_names()

    if nome_tabela not in tabelas:
        raise RuntimeError(
            f"Tabela '{nome_tabela}' não encontrada. "
            f"Tabelas existentes: {tabelas}"
        )

    colunas_existentes = {
        coluna["name"]
        for coluna in inspector.get_columns(nome_tabela)
    }

    colunas_necessarias = {
        coluna.name
        for coluna in GNREProcessamento.__table__.columns
    }

    faltando = colunas_necessarias - colunas_existentes

    if faltando:
        raise RuntimeError(
            "O banco original não possui as colunas "
            f"necessárias: {sorted(faltando)}"
        )
