# backend/app/core/config.py
import base64
import hashlib
from functools import lru_cache
from typing import List
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet
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

    # --- Database ---
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
    MFA_ENCRYPTION_KEYS: str = ""

    # --- Brute-force protection ---
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- AI ---
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "none"  # none | ollama
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3:latest"
    OLLAMA_FALLBACK_MODEL: str = "phi3:latest"
    OLLAMA_TIMEOUT_SECONDS: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def mfa_encryption_keys(self) -> List[str]:
        configured = [key.strip() for key in self.MFA_ENCRYPTION_KEYS.split(",") if key.strip()]
        if configured:
            return configured
        if self.ENVIRONMENT.lower() == "development" and self.JWT_SECRET:
            # Deterministic development-only key. Production must use a managed secret.
            digest = hashlib.sha256(("pgcc-dev-mfa:" + self.JWT_SECRET).encode("utf-8")).digest()
            return [base64.urlsafe_b64encode(digest).decode("ascii")]
        return []

    @model_validator(mode="after")
    def validate_security(self):
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL est obligatoire (voir .env).")

        if self.JWT_ALGORITHM not in {"HS256", "RS256"}:
            raise ValueError("JWT_ALGORITHM doit être HS256 ou RS256.")

        if self.JWT_ALGORITHM == "HS256" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET est obligatoire avec HS256.")

        if self.JWT_ALGORITHM == "HS256" and len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET doit contenir au moins 32 caractères.")

        if self.ENVIRONMENT.lower() == "production":
            if self.DEBUG:
                raise ValueError("DEBUG doit être désactivé en production.")
            if "*" in self.cors_origins_list:
                raise ValueError("CORS wildcard interdit en production.")
            if self.JWT_ALGORITHM == "HS256" and self.JWT_SECRET.startswith("CHANGE_ME"):
                raise ValueError("JWT_SECRET placeholder interdit en production.")
            if not self.mfa_encryption_keys:
                raise ValueError("MFA_ENCRYPTION_KEYS est obligatoire hors développement.")
            try:
                for key in self.mfa_encryption_keys:
                    Fernet(key.encode("ascii"))
            except Exception as exc:
                raise ValueError("MFA_ENCRYPTION_KEYS doit contenir des clés Fernet valides.") from exc

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

# Avoid logging configuration values during module import. Import-time output can
# leak database host/user details into container logs and complicate test runs.
