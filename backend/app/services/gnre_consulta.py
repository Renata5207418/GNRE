import base64
import binascii
import re
from dataclasses import dataclass
from urllib.parse import urlparse
import requests
from lxml import etree
from sqlalchemy.orm import Session
from app.config import settings
from app.services.certificado_service import arquivos_pem_temporarios
from app.services.gnre_xml import validar_xml


GNRE_NS = "http://www.gnre.pe.gov.br"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_ACTION_CONSULTA = "http://www.gnre.pe.gov.br/webservice/GnreResultadoLote/consultar"
XSD_CONSULTA = "lote_gnre_consulta_v1.00.xsd"

LIMITE_PDF_BYTES = 25 * 1024 * 1024
LIMITE_RESPOSTA_BYTES = 40 * 1024 * 1024


class ErroConsultaGNRE(Exception):
    """
    Erro técnico ou resposta inválida
    durante uma consulta GNRE.
    """
    pass


@dataclass(frozen=True)
class ResultadoConsultaGNRE:
    """
    Resultado estruturado de uma consulta.

    Situacoes possíveis:
        pdf_disponivel
        rejeitada
        sem_pdf
    """
    numero_recibo: str
    situacao: str
    mensagem: str
    pdf_base64: str | None = None
    erros: tuple[str, ...] = ()


def _parse_xml(conteudo: bytes) -> etree._Element:
    """
    Analisa um XML sem permitir resolução
    de entidades externas ou acesso à rede.
    """
    try:
        parser = etree.XMLParser(
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            huge_tree=False,
            remove_blank_text=False,
        )

        return etree.fromstring(
            conteudo,
            parser=parser,
        )

    except (
        etree.XMLSyntaxError,
        ValueError,
    ) as exc:

        raise ErroConsultaGNRE("A resposta recebida não contém XML válido.") from exc


def gerar_xml_consulta(numero_recibo: str, ambiente: str = "1") -> bytes:
    """
    Gera o XML TConsLote_GNRE.

    Preserva os campos e a ordem utilizados
    pelo antigo sistema Django.

    O recibo deve conter exatamente
    14 dígitos, conforme o XSD original.
    """
    recibo = str(numero_recibo or "").strip()
    ambiente = str(ambiente or "").strip()

    if not re.fullmatch(
        r"[0-9]{14}",
        recibo,
    ):
        raise ValueError("O número do recibo GNRE deve conter exatamente 14 dígitos.")

    if ambiente not in {"1", "2"}:
        raise ValueError("Ambiente GNRE inválido: esperado '1' ou '2'.")

    raiz = etree.Element(
        f"{{{GNRE_NS}}}TConsLote_GNRE",
        nsmap={
            None: GNRE_NS,
        },
    )

    etree.SubElement(raiz, f"{{{GNRE_NS}}}ambiente").text = ambiente
    etree.SubElement(raiz, f"{{{GNRE_NS}}}numeroRecibo").text = recibo
    etree.SubElement(raiz, f"{{{GNRE_NS}}}incluirPDFGuias").text = "S"

    return etree.tostring(
        raiz,
        encoding="UTF-8",
        xml_declaration=False,
    )


def montar_envelope_consulta(xml_consulta: bytes) -> bytes:
    """
    Monta o envelope SOAP 1.1
    para GnreResultadoLote.
    """
    consulta = _parse_xml(xml_consulta)

    if consulta.tag != f"{{{GNRE_NS}}}TConsLote_GNRE":
        raise ValueError("XML de consulta não é um TConsLote_GNRE.")

    namespace_servico = "http://www.gnre.pe.gov.br/webservice/GnreResultadoLote"

    # ----------------------------------
    # Envelope principal
    # ----------------------------------
    envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap={
            "soapenv": SOAP_NS,
            "gnre": namespace_servico,
        },
    )

    # ----------------------------------
    # Cabeçalho SOAP
    # ----------------------------------
    header = etree.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    cabecalho = etree.SubElement(header, f"{{{namespace_servico}}}gnreCabecMsg")
    etree.SubElement(cabecalho, "versaoDados").text = "2.00"

    # ----------------------------------
    # Corpo SOAP
    # ----------------------------------
    body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    dados = etree.SubElement(body, f"{{{namespace_servico}}}gnreDadosMsg")
    dados.append(consulta)

    # ----------------------------------
    # Serialização
    # ----------------------------------
    return etree.tostring(
        envelope,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    )


def _texto(elemento: etree._Element, nome: str) -> str:
    """
    Obtém o texto de um elemento filho,
    independentemente do namespace XML.
    """
    filho = elemento.find(f"{{*}}{nome}")
    if filho is None:
        return ""

    return (
        filho.text or ""
    ).strip()


def _documento_de_resposta(conteudo: bytes) -> etree._Element:
    """
    Analisa o retorno SOAP.

    Suporta resultado XML diretamente
    dentro do SOAP e resultado XML
    escapado como texto em return ou
    gnreResultMsg.
    """
    if len(conteudo) > LIMITE_RESPOSTA_BYTES:
        raise ErroConsultaGNRE("Resposta GNRE acima do limite de 40 MB.")

    raiz = _parse_xml(conteudo)

    # ----------------------------------
    # Verificar SOAP Fault
    # ----------------------------------
    fault = raiz.find(f".//{{{SOAP_NS}}}Fault")

    if fault is not None:
        detalhe = (
            _texto(fault, "faultstring")
            or "Falha SOAP sem descrição."
        )

        raise ErroConsultaGNRE(f"O webservice retornou uma falha SOAP: {detalhe[:350]}")

    # ----------------------------------
    # Suporte a XML retornado como texto
    # ----------------------------------
    if raiz.find(".//{*}pdfGuias") is None and raiz.find(".//{*}motivo") is None:
        for elemento in raiz.iter():
            if not isinstance(elemento.tag, str,):
                continue

            nome = etree.QName(elemento).localname

            if nome not in {"return", "gnreResultMsg"}:
                continue

            texto = (elemento.text or "").strip()

            if texto.startswith("<") and len(texto.encode("utf-8")) <= LIMITE_RESPOSTA_BYTES:
                interno = _parse_xml(texto.encode("utf-8"))
                return interno

    return raiz


def interpretar_resposta_consulta(numero_recibo: str, resposta_xml: bytes,) -> ResultadoConsultaGNRE:
    """
    Interpreta a resposta GNRE.

    A função não acessa o banco,
    não cria arquivos e não emite guias.
    """
    raiz = _documento_de_resposta(resposta_xml)

    # ----------------------------------
    # Identificar motivos de rejeição
    # ----------------------------------
    motivos = []

    for motivo in raiz.findall( ".//{*}motivo"):
        codigo = _texto(motivo, "codigo")
        descricao = _texto(motivo, "descricao")
        campo = _texto(motivo, "campo")
        detalhes = " - ".join(
            parte
            for parte in (
                codigo,
                descricao,
            )
            if parte
        )

        if campo:
            detalhes += f" (Campo: {campo})"

        motivos.append(
            (
                detalhes
                or "Rejeição GNRE sem descrição."
            )[:600]
        )

        if len(motivos) >= 100:
            break

    if motivos:
        return ResultadoConsultaGNRE(
            numero_recibo=str(numero_recibo),
            situacao="rejeitada",
            mensagem=(
                "O retorno GNRE contém "
                "motivos de rejeição."
            ),
            erros=tuple(motivos),
        )

    # ----------------------------------
    # Localizar PDF Base64
    # ----------------------------------
    pdf_elemento = raiz.find(".//{*}pdfGuias")

    pdf_texto = (
        pdf_elemento.text or ""
        if pdf_elemento is not None
        else ""
    )

    if not pdf_texto.strip():
        return ResultadoConsultaGNRE(
            numero_recibo=str(numero_recibo),
            situacao="sem_pdf",
            mensagem=(
                "A consulta respondeu sem PDF "
                "e sem motivos de rejeição. "
                "Isso não confirma que a guia "
                "foi emitida. Consulte "
                "novamente mais tarde."
            ),
        )

    # ----------------------------------
    # Normalizar Base64
    # ----------------------------------
    pdf_limpo = re.sub(
        r"\s+",
        "",
        pdf_texto,
    )

    tamanho_maximo_base64 = (
        ((LIMITE_PDF_BYTES + 2) // 3) * 4
    )

    if len(pdf_limpo) > tamanho_maximo_base64:
        raise ErroConsultaGNRE(
            "PDF retornado excede "
            "o limite de 25 MB."
        )

    # ----------------------------------
    # Validar Base64 e assinatura PDF
    # ----------------------------------
    try:
        pdf_bytes = base64.b64decode(
            pdf_limpo,
            validate=True,
        )

    except (
        ValueError,
        binascii.Error,
    ) as exc:

        raise ErroConsultaGNRE("PDF da consulta possui Base64 inválido.") from exc

    if len(pdf_bytes) > LIMITE_PDF_BYTES or not pdf_bytes.startswith(b"%PDF-"):
        raise ErroConsultaGNRE("Conteúdo retornado não é um PDF válido ou ultrapassa 25 MB.")

    # ----------------------------------
    # Resultado
    # ----------------------------------
    return ResultadoConsultaGNRE(
        numero_recibo=str(numero_recibo),
        situacao="pdf_disponivel",
        mensagem=(
            "PDF recebido e "
            "validado preliminarmente."
        ),
        pdf_base64=pdf_limpo,
    )


def consultar_resultado_lote(
    db: Session,
    *,
    codigo_dominio: str | int,
    numero_recibo: str,
    ambiente: str = "1",
) -> ResultadoConsultaGNRE:
    """
    Consulta um recibo GNRE existente.

    Utiliza o certificado digital vinculado
    ao código Domínio.

    Não emite uma nova guia.
    Não altera registros no SQLite.
    Não realiza retentativas automáticas.
    """
    # ----------------------------------
    # URL do webservice
    # ----------------------------------
    url = settings.GNRE_RESULTADO_WEBSERVICE_URL
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        raise ErroConsultaGNRE("URL de consulta GNRE deve usar HTTPS.")

    # ----------------------------------
    # Gerar XML de consulta
    # ----------------------------------
    xml = gerar_xml_consulta(numero_recibo, ambiente)

    # ----------------------------------
    # Validar XML contra XSD original
    # ----------------------------------
    xsd = (settings.media_dir / XSD_CONSULTA)

    if not xsd.is_file():
        raise ErroConsultaGNRE(
            f"XSD de consulta ausente: {xsd}. "
            "Copie o XSD do projeto Django "
            "original para backend/media/."
        )

    if not validar_xml(xml, xsd):
        raise ErroConsultaGNRE("XML de consulta reprovado na validação XSD.")

    # ----------------------------------
    # Montar SOAP
    # ----------------------------------
    envelope = montar_envelope_consulta(xml)

    headers = {
        "Content-Type": (
            "text/xml; charset=utf-8"
        ),
        "SOAPAction": (
            f'"{SOAP_ACTION_CONSULTA}"'
        ),
    }

    # ----------------------------------
    # Consulta HTTPS autenticada
    # ----------------------------------
    try:
        with arquivos_pem_temporarios(
            db,
            codigo_dominio,
        ) as (cert, chave):

            resposta = requests.post(
                url,
                data=envelope,
                headers=headers,
                cert=(cert, chave),
                verify=True,
                timeout=(15, 60),
                allow_redirects=False,
            )

    except requests.RequestException as exc:
        raise ErroConsultaGNRE(
            "Falha de comunicação durante "
            "a consulta GNRE. "
            "A consulta pode ser tentada "
            "novamente, mas não reenvie "
            "a guia."
        ) from exc

    # ----------------------------------
    # Conferir HTTP
    # ----------------------------------
    if resposta.status_code != 200:
        raise ErroConsultaGNRE(
            "Consulta GNRE retornou "
            f"HTTP {resposta.status_code}. "
            "Não reenvie a emissão "
            "por causa disso."
        )

    # ----------------------------------
    # Interpretar retorno
    # ----------------------------------
    return interpretar_resposta_consulta(
        numero_recibo,
        resposta.content,
    )
