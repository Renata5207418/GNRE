from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.config import BASE_DIR
from app.services.planilha_service import analisar_planilha


router = APIRouter(prefix="/planilhas", tags=["Planilhas"])

MAX_ARQUIVO_BYTES = 5 * 1024 * 1024
MODELO_EXCEL = BASE_DIR / "assets" / "Modelo_GNRE_Padrao.xlsx"


@router.get("/modelo")
def baixar_modelo():
    """Modelo padrão de Excel GNRE, para download pelo frontend."""
    if not MODELO_EXCEL.is_file():
        raise HTTPException(
            status_code=503,
            detail="Modelo GNRE não encontrado na pasta backend/assets.",
        )

    return FileResponse(
        path=MODELO_EXCEL,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        filename="Modelo_GNRE_Padrao.xlsx",
    )


@router.post("/validar")
async def validar_planilha(arquivo: UploadFile = File(...)):
    """
    Validação SOMENTE LEITURA.
    Não cria lotes, registros ou guias e não envia XML/SOAP.
    """
    nome = Path(arquivo.filename or "").name

    if not nome.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Envie somente arquivos Excel .xlsx.",
        )

    conteudo = await arquivo.read(MAX_ARQUIVO_BYTES + 1)
    await arquivo.close()

    if not conteudo:
        raise HTTPException(
            status_code=400,
            detail="Arquivo vazio.",
        )

    if len(conteudo) > MAX_ARQUIVO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="A planilha deve ter no máximo 5 MB.",
        )

    try:
        resultado = analisar_planilha(conteudo)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "arquivo": nome,
        **resultado,
    }