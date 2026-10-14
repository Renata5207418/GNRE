import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks, Depends, Form
from fastapi.responses import FileResponse
from app.config import BASE_DIR, settings
from app.database import get_db
from app.routes.auth import usuario_atual, verificar_origem
from app.services.planilha_service import analisar_planilha
from app.workers.gnre_worker import processar_planilha_gnre


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
        "hash_arquivo": hashlib.sha256(conteudo).hexdigest(),
        **resultado,
    }



# ============================================================
# EMISSÃO GNRE - CONTROLE DE LOTES
# ============================================================

log = logging.getLogger(__name__)

PASTA_LOTES = BASE_DIR / "data" / "gnre_jobs"
PASTA_LOTES.mkdir(parents=True, exist_ok=True)

ARQUIVO_BLOQUEIO = PASTA_LOTES / ".emissao.lock"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _caminho_status(lote_id: str) -> Path:
    return PASTA_LOTES / f"{lote_id}.json"


def _gravar_status(lote_id: str, dados: dict) -> None:
    """Grava o estado do lote de forma atômica no disco."""

    destino = _caminho_status(lote_id)

    temporario = PASTA_LOTES / (
        f".{lote_id}.{uuid.uuid4().hex}.tmp"
    )

    temporario.write_text(
        json.dumps(
            dados,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    os.replace(temporario, destino)


def _ler_status(lote_id: str) -> dict | None:
    try:
        uuid.UUID(lote_id)
    except ValueError:
        return None

    caminho = _caminho_status(lote_id)

    if not caminho.is_file():
        return None

    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception(
            "Não foi possível consultar o lote GNRE %s",
            lote_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Estado do lote temporariamente indisponível.",
        )


def _reservar_emissao(lote_id: str) -> bool:
    """
    Permite somente um lote ativo na instalação.

    O arquivo é criado atomicamente. Se a aplicação cair,
    o bloqueio permanece para revisão manual.
    """
    try:
        descritor = os.open(
            str(ARQUIVO_BLOQUEIO),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return False

    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(lote_id)

    return True


def _liberar_emissao(lote_id: str) -> None:
    """
    Libera a reserva somente se pertencer ao lote informado.
    """
    if not ARQUIVO_BLOQUEIO.exists():
        return

    conteudo = ARQUIVO_BLOQUEIO.read_text(
        encoding="utf-8"
    ).strip()

    if conteudo == lote_id:
        ARQUIVO_BLOQUEIO.unlink()


def _executar_lote(
    lote_id: str,
    usuario_id: int,
    nome_arquivo: str,
    conteudo: bytes,
) -> None:
    """
    Executa o worker GNRE em segundo plano.

    O gerador get_db() precisa permanecer aberto durante
    todo o processamento.
    """
    gerador_db = None
    concluido = False

    try:
        gerador_db = get_db()
        db = next(gerador_db)

        resultado = processar_planilha_gnre(
            db,
            conteudo_planilha=conteudo,
            ambiente="2",    # 1 - produção 2 - homologação
            confirmacao_explicita=True,
            consultar_pendentes_existentes=True,
        )

        exige_revisao = any(
            item.get("status") == "Erro na Consulta"
            or item.get("acao") in {
                "envio_indeterminado",
                "recibo_nao_identificado",
                "revisao_manual_necessaria",
            }
            for item in resultado.get("itens", [])
        )

        _gravar_status(
            lote_id,
            {
                "lote_id": lote_id,
                "usuario_id": usuario_id,
                "arquivo": nome_arquivo,
                "status": (
                    "erro_revisao"
                    if exige_revisao
                    else "concluido"
                ),
                "atualizado_em": _agora_iso(),
                "mensagem": (
                    "O lote contém guias com resultado inconclusivo. "
                    "Confira os registros e recibos antes de "
                    "autorizar uma nova emissão."
                    if exige_revisao
                    else "Processamento finalizado."
                ),
                "resultado": resultado,
            },
        )

        concluido = not exige_revisao

    except Exception:
        log.exception(
            "Falha durante o processamento do lote GNRE %s",
            lote_id,
        )

        try:
            _gravar_status(
                lote_id,
                {
                    "lote_id": lote_id,
                    "usuario_id": usuario_id,
                    "arquivo": nome_arquivo,
                    "status": "erro_revisao",
                    "atualizado_em": _agora_iso(),
                    "mensagem": (
                        "O processamento foi interrompido ou falhou. "
                        "O bloqueio de emissão foi mantido. "
                        "Verifique os recibos e os registros existentes "
                        "antes de autorizar outro lote."
                    ),
                },
            )
        except Exception:
            log.exception(
                "Não foi possível salvar o erro do lote %s",
                lote_id,
            )

    finally:
        if gerador_db is not None:
            gerador_db.close()

        if concluido:
            _liberar_emissao(lote_id)


@router.post("/confirmar", status_code=202)
async def confirmar_emissao_planilha(
    tarefas: BackgroundTasks,
    arquivo: UploadFile = File(...),
    hash_validado: str = Form(...),
    confirmacao_explicita: bool = Form(...),
    usuario=Depends(usuario_atual),
    _=Depends(verificar_origem),
):
    """
    Confirma a emissão das guias válidas da planilha.

    A transmissão real só é permitida quando:
    - usuário está autenticado;
    - a origem da requisição é autorizada;
    - o envio está habilitado no ambiente;
    - a confirmação é explícita;
    - o arquivo é o mesmo que foi validado;
    - não existem erros de validação na planilha;
    - não existe outro lote ativo.
    """
    if not confirmacao_explicita:
        raise HTTPException(
            status_code=400,
            detail="É necessário confirmar a emissão das guias.",
        )

    if not settings.GNRE_ENVIOS_HABILITADOS:
        raise HTTPException(
            status_code=503,
            detail=(
                "Emissões GNRE estão desabilitadas neste ambiente."
            ),
        )

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
            detail="A planilha está vazia.",
        )

    if len(conteudo) > MAX_ARQUIVO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="A planilha deve ter no máximo 5 MB.",
        )

    hash_atual = hashlib.sha256(conteudo).hexdigest()

    if hash_atual != hash_validado:
        raise HTTPException(
            status_code=409,
            detail=(
                "A planilha foi alterada após a validação. "
                "Valide novamente antes de emitir."
            ),
        )

    try:
        validacao = analisar_planilha(conteudo)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if (
        validacao.get("validas", 0) <= 0
        or validacao.get("com_erro", 0) > 0
        or not validacao.get("pronta_para_confirmacao")
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "A planilha não está pronta para emissão. "
                "Corrija os erros e valide novamente."
            ),
        )

    lote_id = str(uuid.uuid4())

    if not _reservar_emissao(lote_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "Já existe um lote GNRE em processamento "
                "ou aguardando revisão. Não foi iniciada "
                "uma nova emissão."
            ),
        )

    estado = {
        "lote_id": lote_id,
        "usuario_id": usuario.id,
        "arquivo": nome,
        "status": "processando",
        "atualizado_em": _agora_iso(),
        "mensagem": (
            "Lote recebido. O processamento foi iniciado."
        ),
    }

    try:
        _gravar_status(lote_id, estado)
    except Exception:
        _liberar_emissao(lote_id)
        raise HTTPException(
            status_code=503,
            detail="Não foi possível registrar o lote GNRE.",
        )

    tarefas.add_task(
        _executar_lote,
        lote_id,
        usuario.id,
        nome,
        conteudo,
    )

    return estado

@router.get("/lotes")
def listar_lotes_usuario(usuario=Depends(usuario_atual)):
    """Lista os últimos lotes do usuário autenticado."""
    lotes = []

    for caminho in PASTA_LOTES.glob("*.json"):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if str(dados.get("usuario_id")) != str(usuario.id):
            continue

        lotes.append(dados)

    lotes.sort(
        key=lambda item: item.get("atualizado_em", ""),
        reverse=True,
    )

    return {"lotes": lotes[:20]}



@router.get("/lotes/{lote_id}")
def consultar_status_emissao(lote_id: str, usuario=Depends(usuario_atual)):
    """Consulta o resultado do lote do usuário autenticado."""
    estado = _ler_status(lote_id)

    if (
        estado is None
        or str(estado.get("usuario_id")) != str(usuario.id)
    ):
        raise HTTPException(
            status_code=404,
            detail="Lote não encontrado.",
        )

    return estado
