# backend/app/core/config.py
from functools import lru_cache
from typing import List
from urllib.parse import urlparse, urlunparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PGCC"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = False

    # --- Base de donnees (obligatoire des la Phase 1) ---
    DATABASE_URL: str = Field(default="")

    # --- JWT ---
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_SECRET: str = Field(default="")
    JWT_PRIVATE_KEY_PATH: str = Field(default="")
    JWT_PUBLIC_KEY_PATH: str = Field(default="")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PRE_AUTH_TOKEN_EXPIRE_MINUTES: int = 5
    CHANGE_PASSWORD_TOKEN_EXPIRE_MINUTES: int = 10

    # --- MFA ---
    MFA_ISSUER_NAME: str = "CTF PGCC"
    MFA_VALID_WINDOW: int = 1

    # --- Protection anti brute-force ---
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- IA (feature flags, actives en Phase 6) ---
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "none"  # none | ollama
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3:latest"
    OLLAMA_FALLBACK_MODEL: str = "phi3:latest"
    OLLAMA_TIMEOUT_SECONDS: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_security(self):
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL est obligatoire (voir .env).")

        if self.JWT_ALGORITHM == "HS256" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET est obligatoire avec HS256.")

        if self.JWT_ALGORITHM == "RS256":
            if not self.JWT_PRIVATE_KEY_PATH:
                raise ValueError("JWT_PRIVATE_KEY_PATH obligatoire avec RS256.")
            if not self.JWT_PUBLIC_KEY_PATH:
                raise ValueError("JWT_PUBLIC_KEY_PATH obligatoire avec RS256.")

        if not (0 <= self.MFA_VALID_WINDOW <= 2):
            raise ValueError("MFA_VALID_WINDOW doit etre entre 0 et 2.")

        if self.AI_ENABLED and self.AI_PROVIDER == "none":
            raise ValueError("AI_ENABLED=true mais AI_PROVIDER=none.")
        if self.AI_ENABLED and self.AI_PROVIDER == "ollama" and not self.OLLAMA_BASE_URL:
            raise ValueError("AI_PROVIDER=ollama necessite OLLAMA_BASE_URL.")

        return self

    def masked_database_url(self) -> str:
        try:
            p = urlparse(self.DATABASE_URL)
            if not p.hostname:
                return "invalid_database_url"
            user = p.username or ""
            host = p.hostname
            port = f":{p.port}" if p.port else ""
            netloc = f"{user}:********@{host}{port}" if user else f"{host}{port}"
            return urlunparse(p._replace(netloc=netloc))
        except Exception:
            return "invalid_database_url"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

print(
    f"✅ CONFIG PGCC CHARGÉE | ENV={settings.ENVIRONMENT} | "
    f"DB={settings.masked_database_url()} | JWT={settings.JWT_ALGORITHM} | "
    f"IA={'activée (' + settings.AI_PROVIDER + ')' if settings.AI_ENABLED else 'désactivée'}"
)