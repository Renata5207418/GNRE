import base64
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.certificado_models import CertificadoDigital, VinculoCertificado, agora_utc
from app.config import settings
from app.database import engine


TAMANHO_MAXIMO_PFX = 5 * 1024 * 1024


@dataclass(frozen=True)
class MaterialPEM:
    chave_privada_pem: bytes
    certificado_pem: bytes
    cadeia_pem: bytes

    @property
    def certificado_com_cadeia_pem(self) -> bytes:
        return self.certificado_pem + self.cadeia_pem


def criar_tabelas_certificados() -> None:
    """
    Cria SOMENTE as duas tabelas novas.
    Nunca modifica tabelas Django.
    """
    CertificadoDigital.__table__.create(bind=engine, checkfirst=True)
    VinculoCertificado.__table__.create(bind=engine, checkfirst=True)


def _fernet() -> Fernet:
    """
    Inicializa a criptografia utilizando
    a chave protegida nas configurações.
    """
    chave = settings.CERTIFICATE_ENCRYPTION_KEY

    if not chave:
        raise RuntimeError("CERTIFICATE_ENCRYPTION_KEY não configurada no backend/.env.")

    try:
        return Fernet(chave.encode("ascii"))

    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("CERTIFICATE_ENCRYPTION_KEY inválida.") from exc


def _usuario(usuario: str) -> str:
    valor = str(usuario or "").strip()
    if not valor:
        raise ValueError("Usuário responsável não informado.")
    return valor


def _codigo_dominio(codigo_dominio: str | int) -> str:
    codigo = str(codigo_dominio or "").strip()

    if not codigo:
        raise ValueError("Código Domínio obrigatório.")
    return codigo


def _verificar_validade(certificado: CertificadoDigital) -> None:
    """
    Impede a utilização de certificados
    desativados, vencidos ou ainda não válidos.
    """
    if not certificado.ativo:
        raise ValueError("Certificado desativado.")

    agora = agora_utc()

    if agora < certificado.valido_de:
        raise ValueError("Certificado ainda não está válido.")

    if agora >= certificado.valido_ate:
        raise ValueError("Certificado vencido. Cadastre o certificado renovado.")


def _resumo(certificado: CertificadoDigital) -> dict:
    """
    Retorna somente dados públicos e administrativos.

    Nunca devolver o material criptografado
    nas respostas da API.
    """
    agora = agora_utc()

    return {
        "id": certificado.id,
        "nome": certificado.nome,
        "titular": certificado.titular,
        "emissor": certificado.emissor,
        "fingerprint_sha256": certificado.fingerprint_sha256,
        "valido_de": certificado.valido_de.isoformat(),
        "valido_ate": certificado.valido_ate.isoformat(),
        "ativo": certificado.ativo,
        "situacao": (
            "desativado" if not certificado.ativo
            else "ainda_nao_valido"
            if agora < certificado.valido_de
            else "vencido"
            if agora >= certificado.valido_ate
            else "valido"
        ),
        "cadastrado_por": certificado.cadastrado_por,
        "cadastrado_em": certificado.cadastrado_em.isoformat(),
    }


def cadastrar_certificado(
    db: Session,
    *,
    nome_arquivo: str,
    conteudo_pfx: bytes,
    senha: str,
    nome_exibicao: str,
    usuario: str,
) -> dict:
    """
    Abre, valida e cadastra um certificado A1.

    A senha não é armazenada no banco.

    Apenas a chave privada e os certificados
    extraídos são armazenados, criptografados.

    Esta função deverá ser chamada futuramente
    por uma rota administrativa autenticada.
    """
    usuario = _usuario(usuario)
    nome = str(nome_exibicao or "").strip()

    if not nome:
        raise ValueError(
            "Informe um nome para identificar o certificado."
        )

    if Path(nome_arquivo).suffix.lower() not in {
        ".pfx",
        ".p12",
    }:
        raise ValueError(
            "Envie um arquivo .pfx ou .p12."
        )

    if (
        not conteudo_pfx
        or len(conteudo_pfx) > TAMANHO_MAXIMO_PFX
    ):
        raise ValueError("Arquivo vazio ou maior que 5 MB.")

    # Confere a configuração da criptografia
    # antes de realizar qualquer escrita.
    cifra = _fernet()

    # ---------------------------------------
    # Abertura do certificado A1
    # ---------------------------------------
    try:
        chave, certificado, cadeia = (
            pkcs12.load_key_and_certificates(
                conteudo_pfx,
                senha.encode("utf-8") if senha else None,
            )
        )

    except (ValueError, TypeError) as exc:
        raise ValueError("Senha incorreta ou arquivo PFX/P12 inválido.") from exc

    if chave is None or certificado is None:
        raise ValueError("O PFX/P12 precisa conter chave privada e certificado.")

    # ---------------------------------------
    # Conferência da chave privada
    # ---------------------------------------
    publica_chave = chave.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    publica_cert = certificado.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    if publica_chave != publica_cert:
        raise ValueError(
            "A chave privada não corresponde ao certificado."
        )

    # ---------------------------------------
    # Validade do certificado
    # ---------------------------------------
    valido_de = (certificado.not_valid_before_utc.replace(tzinfo=None))
    valido_ate = (certificado.not_valid_after_utc.replace(tzinfo=None))
    agora = agora_utc()

    if not (valido_de <= agora < valido_ate):
        raise ValueError("Certificado fora do período de validade.")

    # ---------------------------------------
    # Identificação e duplicidades
    # ---------------------------------------
    fingerprint = certificado.fingerprint(hashes.SHA256()).hex()
    existente = db.scalar(
        select(CertificadoDigital).where(
            CertificadoDigital.fingerprint_sha256
            == fingerprint
        )
    )

    if existente:
        raise ValueError(f"Certificado já cadastrado com ID {existente.id}.")

    # ---------------------------------------
    # Conversão para PEM em memória
    # ---------------------------------------
    chave_pem = chave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    certificado_pem = certificado.public_bytes(serialization.Encoding.PEM)
    cadeia_pem = b"".join(
        item.public_bytes(
            serialization.Encoding.PEM
        )
        for item in (cadeia or [])
    )

    # ---------------------------------------
    # Preparação do material criptografado
    # ---------------------------------------
    pacote = {
        "chave": base64.b64encode(chave_pem).decode("ascii"),
        "certificado": base64.b64encode(certificado_pem).decode("ascii"),
        "cadeia": base64.b64encode(cadeia_pem).decode("ascii"),
    }

    conteudo_protegido = cifra.encrypt(json.dumps(pacote).encode("utf-8"))

    # ---------------------------------------
    # Gravação no SQLite
    # ---------------------------------------
    registro = CertificadoDigital(
        nome=nome,
        titular=certificado.subject.rfc4514_string(),
        emissor=certificado.issuer.rfc4514_string(),
        fingerprint_sha256=fingerprint,
        valido_de=valido_de,
        valido_ate=valido_ate,
        material_criptografado=conteudo_protegido,
        cadastrado_por=usuario,
    )

    db.add(registro)
    db.commit()
    db.refresh(registro)

    return _resumo(registro)


def listar_certificados(db: Session) -> list[dict]:
    """
    Lista certificados cadastrados
    sem retornar chaves privadas.
    """
    certificados = db.scalars(
        select(CertificadoDigital).order_by(
            CertificadoDigital.id.desc()
        )
    ).all()

    return [
        _resumo(cert)
        for cert in certificados
    ]


def vincular_certificado(
    db: Session,
    *,
    codigo_dominio: str | int,
    certificado_id: int,
    usuario: str,
) -> dict:
    """
    Vincula um código Domínio ao certificado.

    Se o domínio já possuir vínculo, atualiza
    para o novo certificado.

    Não presume autorização fiscal apenas
    porque o CNPJ do certificado coincide.
    """
    codigo = _codigo_dominio(codigo_dominio)
    usuario = _usuario(usuario)
    certificado = db.get(CertificadoDigital, certificado_id)

    if certificado is None:
        raise ValueError("Certificado não encontrado.")

    _verificar_validade(certificado)

    vinculo = db.scalar(
        select(VinculoCertificado).where(
            VinculoCertificado.codigo_dominio == codigo
        )
    )

    if vinculo is None:
        vinculo = VinculoCertificado(
            codigo_dominio=codigo,
            certificado_id=certificado_id,
            vinculado_por=usuario,
        )

        db.add(vinculo)

    else:
        vinculo.certificado_id = certificado_id
        vinculo.vinculado_por = usuario
        vinculo.vinculado_em = agora_utc()

    db.commit()

    return {
        "codigo_dominio": codigo,
        "certificado_id": certificado_id,
    }


def listar_vinculos(db: Session) -> list[dict]:
    """
    Lista os vínculos entre códigos Domínio
    e certificados digitais.
    """
    vinculos = db.scalars(
        select(VinculoCertificado).order_by(
            VinculoCertificado.codigo_dominio
        )
    ).all()

    return [
        {
            "codigo_dominio": v.codigo_dominio,
            "certificado_id": v.certificado_id,
            "vinculado_por": v.vinculado_por,
            "vinculado_em": v.vinculado_em.isoformat(),
        }
        for v in vinculos
    ]


def obter_material_pem(db: Session, codigo_dominio: str | int) -> MaterialPEM:
    """
    Obtém o certificado vinculado a um domínio.

    Descriptografa somente no servidor,
    para utilização em memória.

    Utilizado futuramente por:
        - gnre_soap.py
        - assinatura XML
        - gnre_consulta.py
    """
    codigo = _codigo_dominio(codigo_dominio)
    vinculo = db.scalar(select(VinculoCertificado).where(VinculoCertificado.codigo_dominio == codigo))

    if vinculo is None:
        raise ValueError(f"Domínio {codigo} não possui certificado vinculado." )

    certificado = db.get(CertificadoDigital, vinculo.certificado_id)

    if certificado is None:
        raise ValueError("Certificado vinculado não foi encontrado.")

    _verificar_validade(certificado)

    try:
        conteudo = _fernet().decrypt(
            certificado.material_criptografado
        )
        pacote = json.loads(conteudo)
        material = MaterialPEM(
            chave_privada_pem=base64.b64decode(pacote["chave"], validate=True),
            certificado_pem=base64.b64decode(pacote["certificado"], validate=True),
            cadeia_pem=base64.b64decode(pacote["cadeia"], validate=True),
        )

    except (
        InvalidToken,
        ValueError,
        KeyError,
        TypeError,
        UnicodeError,
    ) as exc:

        raise RuntimeError("Não foi possível abrir o certificado. Confira a chave de criptografia.") from exc
    return material


@contextmanager
def arquivos_pem_temporarios(db: Session, codigo_dominio: str | int) -> Iterator[tuple[str, str]]:
    """
    Fornece caminhos temporários para autenticação
    TLS mútua usando requests.

    Exemplo futuro:
        with arquivos_pem_temporarios(db, dominio) as (cert, key):
            requests.post(url, cert=(cert, key))

    Os arquivos são apagados após o bloco with.
    """
    material = obter_material_pem(db, codigo_dominio)
    with tempfile.TemporaryDirectory(prefix="gnre-a1-") as pasta:
        cert_path = Path(pasta) / "certificado.pem"
        key_path = Path(pasta) / "chave.pem"
        cert_path.write_bytes(material.certificado_com_cadeia_pem)
        key_path.write_bytes(material.chave_privada_pem)
        os.chmod(cert_path, 0o600)
        os.chmod(key_path, 0o600)

        try:
            yield str(cert_path), str(key_path)

        finally:
            pass


def desativar_certificado(db: Session, certificado_id: int) -> dict:
    """
    Desativa um certificado sem apagá-lo.

    Impede sua utilização nas próximas emissões.
    """
    cert = db.get(CertificadoDigital, certificado_id)
    if cert is None:
        raise ValueError(
            "Certificado não encontrado."
        )

    cert.ativo = False
    db.commit()
    return _resumo(cert)
