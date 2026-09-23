from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação, carregada de variáveis de ambiente / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Controle Orçamentário"
    environment: str = "development"

    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    database_url: str = "postgresql+psycopg://orcamento:orcamento@localhost:5432/orcamento"

    # Regra de negócio: fração mínima da receita líquida destinada a investimentos.
    min_investment_rate: float = 0.10

    # Seed do administrador inicial
    admin_email: str = "admin@orcamento.com.br"
    admin_password: str = "admin123"
    admin_name: str = "Administrador"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
