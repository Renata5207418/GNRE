from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Sistema GNRE"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"

    DATABASE_PATH: str = "data/db.sqlite3"
    MEDIA_ROOT: str = "media"

    AUTH_COOKIE_SECURE: bool = False

    M365_TENANT_ID: str | None = None
    M365_CLIENT_ID: str | None = None
    M365_CLIENT_SECRET: str | None = None
    M365_SENDER_EMAIL: str | None = None

    FRONTEND_PUBLIC_URL: str = "http://127.0.0.1:5173"

    CORS_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5175,"
        "http://127.0.0.1:5175"
    )

    GNRE_WEBSERVICE_URL: str = (
        "https://www.gnre.pe.gov.br/"
        "gnreWS/services/GnreLoteRecepcao"
    )

    CERTIFICATE_ENCRYPTION_KEY: str | None = None
    GNRE_ENVIOS_HABILITADOS: bool = False
    GNRE_ADMIN_API_KEY: str | None = None

    GNRE_RESULTADO_WEBSERVICE_URL: str = (
        "https://www.gnre.pe.gov.br/"
        "gnreWS/services/GnreResultadoLote"
    )

    @property
    def database_file(self) -> Path:
        caminho = Path(self.DATABASE_PATH).expanduser()

        if caminho.is_absolute():
            return caminho.resolve()

        return (BASE_DIR / caminho).resolve()

    @property
    def media_dir(self) -> Path:
        caminho = Path(self.MEDIA_ROOT).expanduser()

        if caminho.is_absolute():
            return caminho.resolve()

        return (BASE_DIR / caminho).resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origem.strip()
            for origem in self.CORS_ORIGINS.split(",")
            if origem.strip()
        ]


settings = Settings()
