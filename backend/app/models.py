from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GNREProcessamento(Base):
    __tablename__ = "sample_gnreprocessamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_dominio: Mapped[str] = mapped_column(String(100), nullable=False)
    numero_recibo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_envio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    uf_favorecida: Mapped[str] = mapped_column(String(2), nullable=False)
    inscricao_estadual: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receita: Mapped[str] = mapped_column(String(50), nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    valor_tipo_11: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    def get_pdf_name(self) -> str:
        return (
            f"{self.codigo_dominio}_"
            f"DIF{self.uf_favorecida}_"
            f"{self.mes}{self.ano}.pdf"
        )

    def __repr__(self) -> str:
        return (
            f"<GNREProcessamento("
            f"id={self.id}, "
            f"dominio={self.codigo_dominio}, "
            f"status={self.status}"
            f")>"
        )
