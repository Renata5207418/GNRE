from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def agora_utc() -> datetime:
    """
    Datetime UTC sem timezone, compatível
    com o armazenamento SQLite.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CertificadoDigital(Base):
    __tablename__ = "gnre_certificados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    titular: Mapped[str] = mapped_column(String(300), nullable=False)
    emissor: Mapped[str] = mapped_column(String(300), nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    valido_de: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valido_ate: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    material_criptografado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cadastrado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    cadastrado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora_utc)
    vinculos: Mapped[list["VinculoCertificado"]] = relationship(back_populates="certificado")


class VinculoCertificado(Base):
    __tablename__ = "gnre_certificado_vinculos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_dominio: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    certificado_id: Mapped[int] = mapped_column(ForeignKey("gnre_certificados.id"), nullable=False)
    vinculado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    vinculado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=agora_utc)
    certificado: Mapped[CertificadoDigital] = relationship(back_populates="vinculos")
