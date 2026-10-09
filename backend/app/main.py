from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db, validar_banco_original
from app.models import GNREProcessamento
from app.auth_models import criar_tabelas_auth
from app.services.certificado_service import criar_tabelas_certificados
from app.routes import (
    arquivos,
    auth,
    certificados,
    dashboard,
    guias,
    planilhas,
)
from app.routes.auth import usuario_atual, verificar_origem


@asynccontextmanager
async def lifespan(app: FastAPI):
    validar_banco_original()

    # Apenas tabelas novas.
    # Nunca altera a tabela histórica de guias.
    criar_tabelas_auth()
    criar_tabelas_certificados()

    print("=" * 50)
    print("GNRE - Backend iniciado")
    print(f"Ambiente: {settings.ENVIRONMENT}")
    print(f"Banco: {settings.database_file}")
    print("=" * 50)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API do Sistema GNRE",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
    expose_headers=[
        "Content-Disposition",
        "X-Guias-Incluidas",
        "X-Guias-Ignoradas",
        "X-Total-Exportado",
    ],
)


# Rotas públicas de autenticação.
# Login e cadastro não exigem sessão prévia.

app.include_router(
    auth.router,
    prefix="/api",
    dependencies=[
        Depends(verificar_origem),
    ],
)


# As demais rotas exigem login.

protecao = [
    Depends(usuario_atual),
    Depends(verificar_origem),
]


for router in (
    arquivos.router,
    guias.router,
    planilhas.router,
    dashboard.router,
    certificados.router,
):
    app.include_router(
        router,
        prefix="/api",
        dependencies=protecao,
    )


@app.get("/")
def home():
    return {
        "sistema": settings.APP_NAME,
        "versao": settings.APP_VERSION,
        "status": "online",
        "documentacao": "/docs",
    }


@app.get(
    "/api/health",
    dependencies=[
        Depends(usuario_atual),
    ],
)
def verificar_saude(
    db: Session = Depends(get_db),
):
    total = db.scalar(
        select(
            func.count(GNREProcessamento.id)
        )
    ) or 0

    return {
        "status": "online",
        "banco": "conectado",
        "total_guias": total,
    }
