from __future__ import annotations
import base64
import binascii
import re
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import GNREProcessamento

MAX_IDS_ZIP = 200
MAX_BYTES_ZIP = 250 * 1024 * 1024


class PDFInvalido(ValueError):
    """Base64 ausente, incorreto ou conteúdo diferente de PDF."""


class LimiteZIPExcedido(ValueError):
    """O conjunto de documentos ultrapassou o limite configurado."""


def decodificar_pdf(pdf_base64: str | None) -> bytes:
    """Decodifica PDF legado com validação de Base64 e assinatura do arquivo."""
    if not pdf_base64 or not pdf_base64.strip():
        raise PDFInvalido("Esta guia não possui PDF armazenado.")

    # Alguns documentos legados podem conter quebras de linha no Base64.
    conteudo = "".join(pdf_base64.split())
    try:
        dados = base64.b64decode(conteudo, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PDFInvalido("O PDF armazenado possui Base64 inválido.") from exc

    if not dados.startswith(b"%PDF-"):
        raise PDFInvalido("O documento armazenado não é um PDF válido.")

    return dados


def nome_pdf_seguro(nome_original: str) -> str:
    """Impede caminhos e caracteres perigosos em downloads e arquivos ZIP."""
    apenas_nome = Path(nome_original.replace("\\", "/")).name
    sem_caracteres = re.sub(r"[^a-zA-Z0-9._-]", "_", apenas_nome)
    sem_caracteres = sem_caracteres.strip("._")
    if not sem_caracteres.lower().endswith(".pdf"):
        sem_caracteres += ".pdf"
    return sem_caracteres[:180] or "guia.pdf"


def obter_guia_com_pdf(db: Session, guia_id: int) -> GNREProcessamento | None:
    return db.scalar(
        select(GNREProcessamento)
        .where(GNREProcessamento.id == guia_id)
    )


def iterar_arquivo(
    arquivo: BinaryIO,
    tamanho_bloco: int = 1024 * 256,
) -> Iterator[bytes]:
    """Fecha o arquivo temporário inclusive após a transmissão."""
    try:
        while bloco := arquivo.read(tamanho_bloco):
            yield bloco
    finally:
        arquivo.close()


def montar_zip_guias(
    db: Session,
    ids: list[int],
) -> tuple[BinaryIO, int, int]:
    """Monta ZIP em arquivo temporário, pulando PDFs ausentes/corrompidos.

    Retorna (arquivo_aberto_posicionado_no_inicio, total_incluidos, ignorados).
    """
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ValueError("Selecione ao menos uma guia.")
    if len(ids) > MAX_IDS_ZIP:
        raise LimiteZIPExcedido(
            f"Selecione no máximo {MAX_IDS_ZIP} guias por download."
        )
    if any(item <= 0 for item in ids):
        raise ValueError("IDs de guias devem ser números inteiros positivos.")

    arquivo = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024, mode="w+b")
    nomes: dict[str, int] = {}
    nomes_usados: set[str] = set()
    ignoradas: list[str] = []
    incluidos = 0
    bytes_totais = 0

    try:
        with zipfile.ZipFile(arquivo, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_out:
            for inicio in range(0, len(ids), 25):
                bloco_ids = ids[inicio:inicio + 25]
                registros = db.execute(
                    select(
                        GNREProcessamento.id,
                        GNREProcessamento.codigo_dominio,
                        GNREProcessamento.uf_favorecida,
                        GNREProcessamento.mes,
                        GNREProcessamento.ano,
                        GNREProcessamento.pdf_base64,
                    )
                    .where(GNREProcessamento.id.in_(bloco_ids))
                ).all()
                encontrados = {r.id: r for r in registros}
                for guia_id in bloco_ids:
                    guia = encontrados.get(guia_id)
                    if guia is None:
                        ignoradas.append(f"ID {guia_id}: guia não encontrada")
                        continue
                    try:
                        pdf_bytes = decodificar_pdf(guia.pdf_base64)
                    except PDFInvalido as exc:
                        ignoradas.append(f"ID {guia_id}: {exc}")
                        continue

                    bytes_totais += len(pdf_bytes)
                    if bytes_totais > MAX_BYTES_ZIP:
                        raise LimiteZIPExcedido(
                            "Os PDFs selecionados somam mais de 250 MB. "
                            "Divida o download em lotes menores."
                        )

                    nome = nome_pdf_seguro(
                        f"{guia.codigo_dominio}_DIF{guia.uf_favorecida}_"
                        f"{guia.mes}{guia.ano}.pdf"
                    )
                    original = nome
                    vezes = nomes.get(original, 1)
                    while nome in nomes_usados:
                        raiz, extensao = original.rsplit(".", 1)
                        vezes += 1
                        nome = f"{raiz}_{vezes}.{extensao}"
                    nomes[original] = vezes
                    nomes_usados.add(nome)

                    zip_out.writestr(f"gnre_guias/{nome}", pdf_bytes)
                    incluidos += 1

            if ignoradas:
                zip_out.writestr(
                    "RELATORIO_DE_GUIAS_IGNORADAS.txt",
                    "Algumas guias não puderam ser incluídas:\n\n"
                    + "\n".join(ignoradas),
                )

        if incluidos == 0:
            arquivo.close()
            raise PDFInvalido(
                "Nenhuma das guias selecionadas possui PDF válido."
            )

        arquivo.seek(0)
        return arquivo, incluidos, len(ignoradas)

    except Exception:
        arquivo.close()
        raise
