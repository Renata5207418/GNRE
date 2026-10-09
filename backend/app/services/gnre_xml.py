import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Protocol
from lxml import etree


logger = logging.getLogger(__name__)

NAMESPACE_GNRE = "http://www.gnre.pe.gov.br"
VERSAO_GNRE = "2.00"


class GuiaParaXML(Protocol):
    """
    Define os campos necessários para montar uma GNRE.
    Compatível com objetos GNREProcessamento
    do SQLAlchemy.
    """
    uf_favorecida: str
    inscricao_estadual: str | None
    receita: str
    mes: int
    ano: int
    data_vencimento: date
    valor_tipo_11: Decimal


def gerar_xml_gnre(guia: GuiaParaXML) -> bytes:
    """
    Monta o XML TLote_GNRE versão 2.00.
    Preserva a estrutura fiscal existente no utils.py
    do antigo sistema Django.

    A função não:
        - Salva registros no banco
        - Assina o XML
        - Envia requisições SOAP
        - Emite guias

    Retorna:
        bytes contendo o XML gerado.
    """

    uf = str(guia.uf_favorecida or "").strip().upper()
    ie = str(guia.inscricao_estadual or "").strip()
    receita = str(guia.receita or "").strip()

    # --------------------------------------
    # Validação dos dados básicos
    # --------------------------------------
    if len(uf) != 2:
        raise ValueError("UF favorecida deve possuir duas letras.")

    if not ie:
        raise ValueError("Inscrição estadual (IE) não informada.")

    if not receita:
        raise ValueError("Código da receita não informado.")

    mes = int(guia.mes)
    ano = int(guia.ano)

    if not 1 <= mes <= 12:
        raise ValueError(f"Mês de referência inválido: {mes}.")
    vencimento = guia.data_vencimento

    if not isinstance(vencimento, (date, datetime)):
        raise ValueError("data_vencimento deve ser um date ou datetime.")

    # --------------------------------------
    # Tratamento do valor da GNRE
    # --------------------------------------
    try:
        valor = Decimal(str(guia.valor_tipo_11))

        if not valor.is_finite() or valor <= 0:
            raise ValueError("Valor Tipo 11 deve ser maior que zero.")

        valor_formatado = str(
            valor.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )

    except InvalidOperation as exc:
        raise ValueError("Valor Tipo 11 inválido.") from exc

    # --------------------------------------
    # Estrutura principal do lote GNRE
    # --------------------------------------
    root = etree.Element(
        "TLote_GNRE",
        nsmap={
            None: NAMESPACE_GNRE
        },
        versao=VERSAO_GNRE,
    )

    guias = etree.SubElement(root,"guias")
    dados = etree.SubElement(guias,"TDadosGNRE", versao=VERSAO_GNRE)
    etree.SubElement(dados,  "ufFavorecida").text = uf
    etree.SubElement(dados,"tipoGnre").text = "0"

    # --------------------------------------
    # Identificação do contribuinte
    # --------------------------------------
    emitente = etree.SubElement(dados,"contribuinteEmitente")
    identificacao = etree.SubElement(emitente,"identificacao")
    etree.SubElement(identificacao,"IE").text = ie

    # --------------------------------------
    # Itens GNRE
    # --------------------------------------
    itens = etree.SubElement(dados,"itensGNRE")
    item = etree.SubElement(itens,"item")
    etree.SubElement(item,"receita").text = receita

    # --------------------------------------
    # Regras específicas por UF
    # --------------------------------------
    if uf == "MT":
        etree.SubElement(item,"detalhamentoReceita").text = "000056"

    if uf == "TO":
        etree.SubElement(item,"produto").text = "44"

    # --------------------------------------
    # Período de referência
    # --------------------------------------
    referencia = etree.SubElement(item,"referencia")
    etree.SubElement(referencia,"periodo").text = "0"
    etree.SubElement(referencia,"mes").text = str(mes).zfill(2)
    etree.SubElement(referencia,"ano").text = str(ano)
    vencimento_iso = vencimento.strftime("%Y-%m-%d")
    etree.SubElement(item, "dataVencimento").text = vencimento_iso
    etree.SubElement(item,"valor", tipo="11").text = valor_formatado
    etree.SubElement(dados,"valorGNRE").text = valor_formatado

    # --------------------------------------
    # Regra específica RN
    # --------------------------------------
    if uf == "RN":
        etree.SubElement(item,"convenio").text = "EC87"

    etree.SubElement(dados,"dataPagamento").text = vencimento_iso

    # --------------------------------------
    # Serialização do XML
    # --------------------------------------
    xml_bytes = etree.tostring(
        root,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )

    return xml_bytes


def validar_xml(xml_string: bytes | str, xsd_path: str | Path) -> bool:
    """
    Valida um XML contra um arquivo XSD.

    Reaproveita o comportamento da função validar_xml
    do antigo utils.py, sem depender do Django.

    Retorna:
        True: XML válido para o XSD informado
        False: XML inválido ou erro na validação
    """
    try:
        schema_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(schema_doc)

        if isinstance(xml_string, str):
            xml_bytes = xml_string.encode("utf-8")
        else:
            xml_bytes = xml_string

        xml_doc = etree.fromstring(xml_bytes)
        schema.assertValid(xml_doc)
        return True

    except (
        OSError,
        etree.LxmlError,
        ValueError,
    ) as exc:

        logger.warning(
            "Falha na validação XML/XSD: %s",
            exc,
        )

        return False
