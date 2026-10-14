from __future__ import annotations
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from zipfile import BadZipFile
from lxml import etree
from openpyxl import load_workbook
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from app.models import GNREProcessamento
from app.services.gnre_consulta import (
    ErroConsultaGNRE,
    ResultadoConsultaGNRE,
    consultar_resultado_lote,
)
from app.services.gnre_soap import (
    EnvioGNREIndeterminado,
    ErroGNRESOAP,
    enviar_lote_gnre,
)
from app.services.gnre_xml import gerar_xml_gnre
from app.services.planilha_service import (
    COLUNAS_GNRE,
    _texto,
    _validar_linha,
)


STATUS_PROCESSADO = "Processado"
STATUS_ERRO_VALIDACAO = "Erro de Validação"
STATUS_ERRO_CONSULTA = "Erro na Consulta"

GNRE_NS = "http://www.gnre.pe.gov.br"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


class ErroWorkerGNRE(Exception):
    """Erro de orquestração do processamento da planilha GNRE."""


@dataclass(frozen=True)
class LinhaValidaGNRE:
    linha_excel: int
    codigo_dominio: str
    uf_favorecida: str
    inscricao_estadual: str
    receita: str
    mes: int
    ano: int
    data_vencimento: date
    valor_tipo_11: Decimal

    @property
    def chave_natural(self) -> tuple[Any, ...]:
        return (
            self.codigo_dominio,
            self.uf_favorecida,
            self.inscricao_estadual,
            self.receita,
            self.mes,
            self.ano,
            self.data_vencimento,
            self.valor_tipo_11,
        )

    def resumo(self) -> dict[str, Any]:
        return {
            "linha_excel": self.linha_excel,
            "codigo_dominio": self.codigo_dominio,
            "uf_favorecida": self.uf_favorecida,
            "inscricao_estadual": self.inscricao_estadual,
            "receita": self.receita,
            "mes": self.mes,
            "ano": self.ano,
            "data_vencimento": self.data_vencimento.isoformat(),
            "valor_tipo_11": f"{self.valor_tipo_11:.2f}",
        }


def _decimal_2(valor: Decimal | str | int | float) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _erro_texto(exc: Exception) -> str:
    mensagem = str(exc).strip()
    return mensagem[:2000] or exc.__class__.__name__


def _parse_data_iso(valor: str) -> date:
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ErroWorkerGNRE(
            f"Data de vencimento calculada inválida: {valor!r}."
        ) from exc


def _normalizar_erros(erros: tuple[str, ...] | list[str]) -> str:
    erros_limpos = [str(item).strip() for item in erros if str(item).strip()]
    if not erros_limpos:
        return "Retorno GNRE sem detalhes adicionais."
    return " | ".join(erros_limpos)[:2000]


def _abrir_planilha(conteudo: bytes):
    try:
        return load_workbook(
            BytesIO(conteudo),
            read_only=True,
            data_only=True,
        )
    except (BadZipFile, OSError, ValueError, TypeError, KeyError) as exc:
        raise ErroWorkerGNRE("O arquivo informado não é um Excel .xlsx válido.") from exc


def _linhas_validas_da_planilha(conteudo: bytes) -> tuple[list[LinhaValidaGNRE], list[dict[str, Any]]]:
    """
    Lê a planilha GNRE e retorna:
      - lista de linhas válidas e normalizadas para emissão;
      - lista de linhas com erro/ignorada para relatório.

    Mantém a mesma regra de leitura do planilha_service.py
    para evitar divergências entre a tela de validação e o worker.
    """
    pasta = _abrir_planilha(conteudo)

    try:
        aba = pasta["GNRE"] if "GNRE" in pasta.sheetnames else pasta.active
        linhas = aba.iter_rows(values_only=True)
        cabecalhos = next(linhas, None)

        if cabecalhos is None:
            raise ErroWorkerGNRE("A planilha não possui cabeçalho.")

        colunas = [_texto(c).removeprefix("\ufeff") for c in cabecalhos]

        ausentes = [c for c in COLUNAS_GNRE if c not in colunas]
        if ausentes:
            raise ErroWorkerGNRE(
                "Colunas obrigatórias ausentes: " + ", ".join(ausentes)
            )

        indices = {coluna: colunas.index(coluna) for coluna in COLUNAS_GNRE}

        validas: list[LinhaValidaGNRE] = []
        inconsistencias: list[dict[str, Any]] = []

        for numero_excel, linha in enumerate(linhas, start=2):
            valores = {
                nome: linha[indice] if indice < len(linha) else None
                for nome, indice in indices.items()
            }

            if all(_texto(valor) == "" for valor in valores.values()):
                continue

            resultado = _validar_linha(numero_excel, valores)
            status = resultado["status"]

            if status != "valida":
                inconsistencias.append(
                    {
                        "linha_excel": numero_excel,
                        "status": status,
                        "acao": "ignorada" if status == "ignorada" else "erro_validacao_planilha",
                        "mensagem": " | ".join(
                            resultado["avisos"] if status == "ignorada" else resultado["erros"]
                        )[:2000],
                    }
                )
                continue

            dados = resultado["dados"]
            validas.append(
                LinhaValidaGNRE(
                    linha_excel=numero_excel,
                    codigo_dominio=dados["codigo_dominio"],
                    uf_favorecida=dados["uf_favorecida"],
                    inscricao_estadual=dados["inscricao_estadual"],
                    receita=dados["receita"],
                    mes=int(dados["mes"]),
                    ano=int(dados["ano"]),
                    data_vencimento=_parse_data_iso(dados["data_vencimento_calculada"]),
                    valor_tipo_11=_decimal_2(dados["valor_tipo_11"]),
                )
            )

        return validas, inconsistencias
    finally:
        pasta.close()


def _buscar_registro_existente(db: Session, linha: LinhaValidaGNRE) -> GNREProcessamento | None:
    consulta = (
        select(GNREProcessamento)
        .where(
            and_(
                GNREProcessamento.codigo_dominio == linha.codigo_dominio,
                GNREProcessamento.uf_favorecida == linha.uf_favorecida,
                GNREProcessamento.inscricao_estadual == linha.inscricao_estadual,
                GNREProcessamento.receita == linha.receita,
                GNREProcessamento.mes == linha.mes,
                GNREProcessamento.ano == linha.ano,
                GNREProcessamento.data_vencimento == linha.data_vencimento,
                GNREProcessamento.valor_tipo_11 == linha.valor_tipo_11,
            )
        )
        .order_by(GNREProcessamento.id.desc())
        .limit(1)
    )
    return db.scalar(consulta)


def _criar_registro_base(linha: LinhaValidaGNRE) -> GNREProcessamento:
    return GNREProcessamento(
        codigo_dominio=linha.codigo_dominio,
        numero_recibo=None,
        status=STATUS_ERRO_CONSULTA,
        erro_mensagem=None,
        pdf_base64=None,
        data_envio=datetime.now(),
        uf_favorecida=linha.uf_favorecida,
        inscricao_estadual=linha.inscricao_estadual,
        receita=linha.receita,
        mes=linha.mes,
        ano=linha.ano,
        data_vencimento=linha.data_vencimento,
        valor_tipo_11=linha.valor_tipo_11,
    )


def _salvar(db: Session, registro: GNREProcessamento) -> GNREProcessamento:
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def _atualizar_registro(
    db: Session,
    registro: GNREProcessamento,
    *,
    status: str,
    mensagem: str | None,
    numero_recibo: str | None = None,
    pdf_base64: str | None = None,
) -> GNREProcessamento:
    registro.status = status
    registro.erro_mensagem = mensagem[:2000] if mensagem else None
    if numero_recibo is not None:
        registro.numero_recibo = numero_recibo
    if pdf_base64 is not None:
        registro.pdf_base64 = pdf_base64
    registro.data_envio = datetime.now()
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def _registrar_erro_validacao(
    db: Session,
    linha: LinhaValidaGNRE,
    mensagem: str,
) -> GNREProcessamento:
    registro = _criar_registro_base(linha)
    registro.status = STATUS_ERRO_VALIDACAO
    registro.erro_mensagem = mensagem[:2000]
    return _salvar(db, registro)


def _parse_xml_seguro(conteudo: bytes) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
        remove_blank_text=False,
    )
    return etree.fromstring(conteudo, parser=parser)


def _extrair_numero_recibo(resposta_xml: bytes) -> str:
    """
    Extrai o número do recibo a partir do XML de retorno do envio.

    O serviço GNRE pode devolver o resultado de formas ligeiramente diferentes,
    então procuramos primeiro por tags usuais e, como fallback, por qualquer
    sequência de 14 dígitos em elementos cujo nome lembre recibo.
    """
    try:
        raiz = _parse_xml_seguro(resposta_xml)
    except Exception as exc:
        raise ErroWorkerGNRE("A resposta do envio não contém XML válido.") from exc

    fault = raiz.find(f".//{{{SOAP_NS}}}Fault")
    if fault is not None:
        texto_fault = " ".join(
            (item.text or "").strip()
            for item in fault.iter()
            if isinstance(item.tag, str) and (item.text or "").strip()
        )
        raise ErroWorkerGNRE(
            (texto_fault or "O webservice retornou uma falha SOAP.")[:2000]
        )

    candidatos: list[str] = []
    nomes_preferidos = {
        "numerorecibo",
        "recibo",
        "numero_recibo",
    }

    for elemento in raiz.iter():
        if not isinstance(elemento.tag, str):
            continue

        local = etree.QName(elemento).localname.lower()
        texto = (elemento.text or "").strip()
        if not texto:
            continue

        if local in nomes_preferidos:
            candidatos.append(texto)
        elif "recibo" in local:
            candidatos.append(texto)

    for texto in candidatos:
        match = re.search(r"\b(\d{14})\b", texto)
        if match:
            return match.group(1)

    xml_completo = etree.tostring(raiz, encoding="unicode", pretty_print=False)
    match = re.search(r"\b(\d{14})\b", xml_completo)
    if match:
        return match.group(1)

    raise ErroWorkerGNRE(
        "O envio retornou XML, porém não foi possível localizar o número do recibo. "
        "Não reenviar automaticamente esta guia."
    )


def _resultado_consulta_para_status(resultado: ResultadoConsultaGNRE) -> tuple[str, str, str | None]:
    if resultado.situacao == "pdf_disponivel":
        return STATUS_PROCESSADO, resultado.mensagem, resultado.pdf_base64

    if resultado.situacao == "rejeitada":
        return (
            STATUS_ERRO_VALIDACAO,
            _normalizar_erros(resultado.erros),
            None,
        )

    return STATUS_ERRO_CONSULTA, resultado.mensagem, None


def _consultar_recibo_e_atualizar(
    db: Session,
    registro: GNREProcessamento,
    *,
    ambiente: str,
) -> dict[str, Any]:
    try:
        resultado = consultar_resultado_lote(
            db,
            codigo_dominio=registro.codigo_dominio,
            numero_recibo=str(registro.numero_recibo or ""),
            ambiente=ambiente,
        )
    except ErroConsultaGNRE as exc:
        atualizado = _atualizar_registro(
            db,
            registro,
            status=STATUS_ERRO_CONSULTA,
            mensagem=_erro_texto(exc),
        )
        return {
            "status": atualizado.status,
            "acao": "consulta_falhou",
            "mensagem": atualizado.erro_mensagem,
            "guia_id": atualizado.id,
            "numero_recibo": atualizado.numero_recibo,
        }

    status, mensagem, pdf_base64 = _resultado_consulta_para_status(resultado)
    atualizado = _atualizar_registro(
        db,
        registro,
        status=status,
        mensagem=mensagem,
        pdf_base64=pdf_base64,
    )

    return {
        "status": atualizado.status,
        "acao": "consulta_realizada",
        "mensagem": mensagem,
        "guia_id": atualizado.id,
        "numero_recibo": atualizado.numero_recibo,
        "tem_pdf": bool(atualizado.pdf_base64),
    }



def _emitir_nova_guia(db: Session, linha: LinhaValidaGNRE, *, ambiente: str, confirmacao_explicita: bool) -> dict[str, Any]:
    try:
        xml = gerar_xml_gnre(linha)
    except Exception as exc:
        registro = _registrar_erro_validacao(db, linha, _erro_texto(exc))
        return {
            **linha.resumo(),
            "status": registro.status,
            "acao": "erro_xml",
            "mensagem": registro.erro_mensagem,
            "guia_id": registro.id,
        }

    # Registra a tentativa ANTES de acessar o webservice.
    # Se o processo encerrar durante o envio, haverá um
    # registro sem recibo que impede reenvio automático.
    registro = _criar_registro_base(linha)
    registro.status = STATUS_ERRO_CONSULTA
    registro.erro_mensagem = (
        "Tentativa de emissão registrada antes da transmissão. "
        "Se o processamento for interrompido, verificar a "
        "situação da guia antes de reenviar."
    )
    registro = _salvar(db, registro)

    try:
        resposta = enviar_lote_gnre(
            db,
            codigo_dominio=linha.codigo_dominio,
            xml_nao_assinado=xml,
            confirmacao_explicita=confirmacao_explicita,
        )

    except EnvioGNREIndeterminado as exc:
        registro = _atualizar_registro(
            db,
            registro,
            status=STATUS_ERRO_CONSULTA,
            mensagem=(
                "Envio com resultado indeterminado. "
                "Não reenviar automaticamente. "
                f"Detalhes: {_erro_texto(exc)}"
            ),
        )

        return {
            **linha.resumo(),
            "status": registro.status,
            "acao": "envio_indeterminado",
            "mensagem": registro.erro_mensagem,
            "guia_id": registro.id,
        }

    except ErroGNRESOAP as exc:
        registro = _atualizar_registro(
            db,
            registro,
            status=STATUS_ERRO_VALIDACAO,
            mensagem=_erro_texto(exc),
        )

        return {
            **linha.resumo(),
            "status": registro.status,
            "acao": "envio_rejeitado_localmente",
            "mensagem": registro.erro_mensagem,
            "guia_id": registro.id,
        }

    except Exception as exc:
        registro = _atualizar_registro(
            db,
            registro,
            status=STATUS_ERRO_CONSULTA,
            mensagem=(
                "Falha inesperada durante a emissão. "
                "Resultado não confirmado. "
                "Não reenviar automaticamente. "
                f"Detalhes: {_erro_texto(exc)}"
            ),
        )

        return {
            **linha.resumo(),
            "status": registro.status,
            "acao": "envio_indeterminado",
            "mensagem": registro.erro_mensagem,
            "guia_id": registro.id,
        }

    try:
        numero_recibo = _extrair_numero_recibo(resposta.conteudo)

    except Exception as exc:
        registro = _atualizar_registro(
            db,
            registro,
            status=STATUS_ERRO_CONSULTA,
            mensagem=(
                "Envio concluído, porém o recibo não pôde "
                "ser identificado na resposta. "
                "Não reenviar automaticamente. "
                f"Detalhes: {_erro_texto(exc)}"
            ),
        )

        return {
            **linha.resumo(),
            "status": registro.status,
            "acao": "recibo_nao_identificado",
            "mensagem": registro.erro_mensagem,
            "guia_id": registro.id,
        }

    registro = _atualizar_registro(
        db,
        registro,
        status=STATUS_ERRO_CONSULTA,
        mensagem="Recibo obtido. Consultando resultado GNRE.",
        numero_recibo=numero_recibo,
    )
    time.sleep(30)

    retorno_consulta = _consultar_recibo_e_atualizar(
        db,
        registro,
        ambiente=ambiente,
    )

    return {
        **linha.resumo(),
        **retorno_consulta,
        "acao": "emitida_e_consultada",
    }



def processar_planilha_gnre(
    db: Session,
    *,
    conteudo_planilha: bytes,
    ambiente: str = "1",
    confirmacao_explicita: bool = False,
    consultar_pendentes_existentes: bool = True,
) -> dict[str, Any]:
    """
    Orquestra o processamento completo da planilha GNRE.

    Fluxo:
      1. Lê e valida o Excel.
      2. Ignora linhas vazias, inválidas ou duplicadas na própria planilha.
      3. Procura registros já existentes no SQLite para impedir duplicidade.
      4. Se houver recibo anterior sem PDF, tenta consultar novamente.
      5. Se não existir registro e o envio estiver liberado, emite a guia.
      6. Consulta o recibo e salva o PDF quando disponível.

    Observações importantes:
      - Nunca reenviar automaticamente uma guia cujo envio anterior tenha sido
        indeterminado e que não possua recibo armazenado.
      - A confirmação explícita precisa ser verdadeira para permitir o envio real.
      - O worker grava um registro por tentativa/processamento no SQLite histórico.
    """
    linhas_validas, inconsistencias = _linhas_validas_da_planilha(conteudo_planilha)

    itens: list[dict[str, Any]] = []
    itens.extend(inconsistencias)

    chaves_vistas: set[tuple[Any, ...]] = set()

    for linha in linhas_validas:
        if linha.chave_natural in chaves_vistas:
            itens.append(
                {
                    **linha.resumo(),
                    "status": "ignorada",
                    "acao": "duplicada_na_planilha",
                    "mensagem": "Linha duplicada dentro da própria planilha. Apenas a primeira ocorrência foi considerada.",
                }
            )
            continue

        chaves_vistas.add(linha.chave_natural)
        existente = _buscar_registro_existente(db, linha)

        if existente is not None:
            if existente.pdf_base64:
                itens.append(
                    {
                        **linha.resumo(),
                        "status": existente.status,
                        "acao": "ja_processada",
                        "mensagem": "Já existe guia com PDF armazenado para esta combinação de dados. Nenhuma nova emissão foi realizada.",
                        "guia_id": existente.id,
                        "numero_recibo": existente.numero_recibo,
                        "tem_pdf": True,
                    }
                )
                continue

            if existente.numero_recibo and consultar_pendentes_existentes:
                retorno = _consultar_recibo_e_atualizar(
                    db,
                    existente,
                    ambiente=ambiente,
                )
                itens.append(
                    {
                        **linha.resumo(),
                        **retorno,
                        "acao": "recibo_existente_reconsultado",
                    }
                )
                continue

            if existente.status == STATUS_ERRO_CONSULTA and not existente.numero_recibo:
                itens.append(
                    {
                        **linha.resumo(),
                        "status": existente.status,
                        "acao": "revisao_manual_necessaria",
                        "mensagem": (
                            "Já existe registro anterior sem recibo e com resultado indeterminado ou inconclusivo. "
                            "Por segurança, o worker não reenviou automaticamente esta guia."
                        ),
                        "guia_id": existente.id,
                    }
                )
                continue

        itens.append(
            _emitir_nova_guia(
                db,
                linha,
                ambiente=ambiente,
                confirmacao_explicita=confirmacao_explicita,
            )
        )

    total = len(itens)
    processadas = sum(1 for item in itens if item.get("status") == STATUS_PROCESSADO)
    erro_validacao = sum(1 for item in itens if item.get("status") == STATUS_ERRO_VALIDACAO)
    erro_consulta = sum(1 for item in itens if item.get("status") == STATUS_ERRO_CONSULTA)
    ignoradas = sum(
        1
        for item in itens
        if item.get("status") == "ignorada"
        or item.get("acao") in {"ja_processada", "duplicada_na_planilha", "revisao_manual_necessaria"}
    )

    return {
        "ambiente": ambiente,
        "confirmacao_explicita": confirmacao_explicita,
        "total_resultados": total,
        "processadas": processadas,
        "erro_validacao": erro_validacao,
        "erro_consulta": erro_consulta,
        "ignoradas": ignoradas,
        "itens": itens,
    }
