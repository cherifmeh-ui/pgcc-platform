# backend/app/core/config.py
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PGCC"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = False

    # Database (vide par défaut -> pas de secret en dur)
    DATABASE_URL: str = Field(default="")

    # JWT (vides par défaut -> la validation stricte arrive en Phase 1)
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_SECRET: str = Field(default="")
    JWT_PRIVATE_KEY_PATH: str = Field(default="")
    JWT_PUBLIC_KEY_PATH: str = Field(default="")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PRE_AUTH_TOKEN_EXPIRE_MINUTES: int = 5
    CHANGE_PASSWORD_TOKEN_EXPIRE_MINUTES: int = 10

    # MFA
    MFA_ISSUER_NAME: str = "CTF PGCC"
    MFA_VALID_WINDOW: int = 1

    # Login security
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # IA - feature flags (poses des la Phase 0, activés en Phase 6)
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "none"  # none | ollama
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3:latest"
    OLLAMA_FALLBACK_MODEL: str = "phi3:latest"
    OLLAMA_TIMEOUT_SECONDS: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

print(
    f"✅ CONFIG PGCC CHARGÉE | ENV={settings.ENVIRONMENT} | "
    f"DB={'configurée' if settings.DATABASE_URL else 'non configurée (Phase 0 OK)'} | "
    f"IA={'activée (' + settings.AI_PROVIDER + ')' if settings.AI_ENABLED else 'désactivée'}"
)