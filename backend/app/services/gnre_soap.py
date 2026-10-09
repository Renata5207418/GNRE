from dataclasses import dataclass
from urllib.parse import urlparse
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from lxml import etree
from signxml import XMLSigner, XMLVerifier, methods
from sqlalchemy.orm import Session
from app.config import settings
from app.services.certificado_service import arquivos_pem_temporarios, obter_material_pem


GNRE_NS = "http://www.gnre.pe.gov.br"
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
SOAP_ACTION_ENVIO = "http://www.gnre.pe.gov.br/webservice/GnreLoteRecepcao/processar"


class ErroGNRESOAP(Exception):
    pass


class EnvioGNREIndeterminado(ErroGNRESOAP):
    """
    A requisição pode ter chegado ao servidor.
    Nunca reenviar automaticamente uma guia
    com resultado de transporte indeterminado.
    """
    pass


@dataclass(frozen=True)
class RespostaTransporteGNRE:
    status_http: int
    conteudo: bytes


def _xml_seguro(conteudo: bytes) -> etree._Element:
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


def _tdados(raiz: etree._Element) -> etree._Element:
    encontrado = raiz.find(f".//{{{GNRE_NS}}}TDadosGNRE")

    if encontrado is None:
        raise ErroGNRESOAP("TDadosGNRE não encontrado no XML.")
    return encontrado


def verificar_assinatura_xml(xml_assinado: bytes, certificado_pem: bytes) -> None:
    """
    Verifica criptograficamente a assinatura
    usando o certificado fornecido.

    Não substitui validação de confiança
    da cadeia ICP-Brasil.
    """
    raiz = _xml_seguro(xml_assinado)
    dados = _tdados(raiz)
    assinatura = dados.find(f".//{{{DS_NS}}}Signature")

    if assinatura is None:
        raise ErroGNRESOAP("O XML não contém assinatura digital.")

    try:
        XMLVerifier().verify(dados, x509_cert=certificado_pem)

    except Exception as exc:
        raise ErroGNRESOAP("Falha na verificação local da assinatura digital.") from exc


def assinar_xml_gnre(db: Session, codigo_dominio: str | int, xml_nao_assinado: bytes) -> bytes:
    """
    Assina o elemento TDadosGNRE.

    Utiliza o certificado A1 vinculado
    ao código Domínio.

    Retorna o XML completo assinado.
    """
    # ---------------------------------------
    # Obter material do certificado
    # ---------------------------------------
    material = obter_material_pem(db, codigo_dominio)
    raiz = _xml_seguro(xml_nao_assinado)
    dados = _tdados(raiz)

    if dados.find(f".//{{{DS_NS}}}Signature") is not None:
        raise ErroGNRESOAP("O XML já possui assinatura digital.")

    # ---------------------------------------
    # Identificar tipo de chave
    # ---------------------------------------
    chave = serialization.load_pem_private_key(material.chave_privada_pem, password=None)

    if isinstance(chave, rsa.RSAPrivateKey):
        algoritmo = "rsa-sha256"

    elif isinstance(chave, ec.EllipticCurvePrivateKey):
        algoritmo = "ecdsa-sha256"

    else:
        raise ErroGNRESOAP("Tipo de chave privada não suportado.")

    # ---------------------------------------
    # Criar assinatura
    # ---------------------------------------
    assinador = XMLSigner(
        method=methods.enveloped,
        signature_algorithm=algoritmo,
        digest_algorithm="sha256",
        c14n_algorithm=(
            "http://www.w3.org/2001/10/"
            "xml-exc-c14n#"
        ),
    )

    dados_assinados = assinador.sign(
        dados,
        key=material.chave_privada_pem,
        cert=material.certificado_pem,
    )

    # ---------------------------------------
    # Substituir o elemento original
    # pelo elemento realmente assinado
    # ---------------------------------------
    pai = dados.getparent()

    if pai is None:
        raise ErroGNRESOAP("Estrutura TLote_GNRE inválida.")

    pai.replace(dados, dados_assinados)
    xml_final = etree.tostring(
        raiz,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    )

    # ---------------------------------------
    # Verificação antes de disponibilizar
    # o XML para transporte
    # ---------------------------------------
    verificar_assinatura_xml(xml_final, material.certificado_pem)
    return xml_final


def montar_envelope_soap(xml_assinado: bytes) -> bytes:
    """
    Monta o envelope SOAP 1.1
    do serviço GnreLoteRecepcao.

    Mantém versaoDados 2.00.
    """
    raiz = _xml_seguro(xml_assinado)

    if raiz.tag != f"{{{GNRE_NS}}}TLote_GNRE":
        raise ErroGNRESOAP("XML enviado não é um TLote_GNRE.")

    namespace_servico = ("http://www.gnre.pe.gov.br/webservice/GnreLoteRecepcao")

    # ---------------------------------------
    # Envelope
    # ---------------------------------------
    envelope = etree.Element(
        f"{{{SOAP_NS}}}Envelope",
        nsmap={
            "soapenv": SOAP_NS,
            "gnre": namespace_servico,
        },
    )

    # ---------------------------------------
    # Cabeçalho
    # ---------------------------------------
    cabecalho = etree.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    cabecmsg = etree.SubElement(cabecalho, f"{{{namespace_servico}}}gnreCabecMsg")
    etree.SubElement(cabecmsg,"versaoDados").text = "2.00"

    # ---------------------------------------
    # Corpo
    # ---------------------------------------
    corpo = etree.SubElement(envelope,f"{{{SOAP_NS}}}Body")
    dadosmsg = etree.SubElement(corpo,f"{{{namespace_servico}}}gnreDadosMsg")
    dadosmsg.append(raiz)

    # ---------------------------------------
    # Retornar SOAP pronto
    # ---------------------------------------
    return etree.tostring(
        envelope,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=False,
    )


def enviar_lote_gnre(
    db: Session,
    *,
    codigo_dominio: str | int,
    xml_nao_assinado: bytes,
    confirmacao_explicita: bool = False,
) -> RespostaTransporteGNRE:
    """
    Assina e envia um lote GNRE.

    IMPORTANTE:
    - O envio real começa bloqueado.
    - Não faz retentativas automáticas.
    - Não interpreta recibos nem PDFs.
    - Não modifica o banco de guias.

    O worker futuro será responsável
    pela proteção contra duplicidades
    e persistência do processamento.
    """
    # ---------------------------------------
    # Bloqueio de segurança
    # ---------------------------------------
    if (
        not settings.GNRE_ENVIOS_HABILITADOS
        or not confirmacao_explicita
    ):

        raise ErroGNRESOAP(
            "Envio real bloqueado. "
            "Requer GNRE_ENVIOS_HABILITADOS=true "
            "e confirmação explícita."
        )

    # ---------------------------------------
    # Configuração da URL
    # ---------------------------------------
    url = settings.GNRE_WEBSERVICE_URL
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
    ):
        raise ErroGNRESOAP(
            "O webservice GNRE deve usar HTTPS."
        )

    # ---------------------------------------
    # Recuperar certificado
    # ---------------------------------------
    material = obter_material_pem(db, codigo_dominio)

    # ---------------------------------------
    # Assinar XML
    # ---------------------------------------
    xml_assinado = assinar_xml_gnre(
        db,
        codigo_dominio,
        xml_nao_assinado,
    )

    # ---------------------------------------
    # Montar envelope SOAP
    # ---------------------------------------
    envelope = montar_envelope_soap(xml_assinado)

    # ---------------------------------------
    # Conferir assinatura após inserção
    # no envelope SOAP
    # ---------------------------------------
    dados_envelope = _tdados(_xml_seguro(envelope))

    try:
        XMLVerifier().verify(
            dados_envelope,
            x509_cert=material.certificado_pem,
        )

    except Exception as exc:
        raise ErroGNRESOAP(
            "Assinatura inválida após "
            "o encapsulamento SOAP. "
            "Envio cancelado."
        ) from exc

    # ---------------------------------------
    # Headers SOAP 1.1
    # ---------------------------------------
    cabecalhos = {
        "Content-Type": (
            "text/xml; charset=utf-8"
        ),
        "SOAPAction": (
            f'"{SOAP_ACTION_ENVIO}"'
        ),
    }

    # ---------------------------------------
    # Envio HTTPS com certificado cliente
    # ---------------------------------------
    try:
        with arquivos_pem_temporarios(
            db,
            codigo_dominio,
        ) as (cert, chave):

            resposta = requests.post(
                url,
                data=envelope,
                headers=cabecalhos,
                cert=(cert, chave),
                timeout=(15, 60),
                verify=True,
                allow_redirects=False,
            )

    except requests.RequestException as exc:
        raise EnvioGNREIndeterminado(
            "Falha durante o envio GNRE. "
            "Não é possível determinar "
            "se a requisição chegou ao servidor. "
            "Não reenviar automaticamente."
        ) from exc

    # ---------------------------------------
    # Conferir resposta HTTP
    # ---------------------------------------
    if resposta.status_code != 200:
        raise EnvioGNREIndeterminado(
            f"Webservice retornou "
            f"HTTP {resposta.status_code}. "
            "Verifique o resultado antes "
            "de uma nova tentativa."
        )

    # ---------------------------------------
    # Validar estrutura XML da resposta
    # ---------------------------------------
    try:
        root = _xml_seguro(resposta.content)

    except etree.XMLSyntaxError as exc:
        raise EnvioGNREIndeterminado("Resposta do webservice não é XML válido. Não reenviar automaticamente.") from exc

    # ---------------------------------------
    # Identificar falha SOAP
    # ---------------------------------------
    fault = root.find(f".//{{{SOAP_NS}}}Fault")

    if fault is not None:
        raise EnvioGNREIndeterminado(
            "O serviço devolveu uma falha SOAP. "
            "Verifique a situação do lote "
            "antes de tentar novamente."
        )

    return RespostaTransporteGNRE(
        status_http=resposta.status_code,
        conteudo=resposta.content,
    )
