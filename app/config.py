"""Environment-backed application settings."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load simple KEY=value entries without overriding the process environment."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").lower()
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io").rstrip("/")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "oncall-memory")
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "hindsight").lower()
APP_API_KEY = os.getenv("APP_API_KEY", "")
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_BACKEND = os.getenv("LLM_BACKEND", "groq").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
DATA_DIR = ROOT / "data"


def validate_settings() -> None:
    """Fail at startup for incomplete or unsafe provider configuration."""
    if APP_ENV not in {"development", "production"}:
        raise ValueError("APP_ENV must be 'development' or 'production'.")
    if MEMORY_BACKEND not in {"hindsight", "local"}:
        raise ValueError("MEMORY_BACKEND must be 'hindsight' or the explicit offline mode 'local'.")
    if LLM_BACKEND not in {"groq", "mock"}:
        raise ValueError("LLM_BACKEND must be 'groq' or the explicit offline mode 'mock'.")
    if APP_ENV == "production" and (MEMORY_BACKEND != "hindsight" or LLM_BACKEND != "groq"):
        raise ValueError("Production requires MEMORY_BACKEND=hindsight and LLM_BACKEND=groq.")
    if APP_ENV == "production" and len(APP_API_KEY) < 32:
        raise ValueError("APP_API_KEY must be set to a random value of at least 32 characters in production.")
    if APP_ENV == "production" and not os.getenv("ALLOWED_HOSTS"):
        raise ValueError("Set ALLOWED_HOSTS explicitly in production (comma-separated hostnames).")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ValueError("ALLOWED_HOSTS must contain explicit hostnames; wildcard hosts are not allowed.")
    if MEMORY_BACKEND == "hindsight":
        if not HINDSIGHT_BASE_URL.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("HINDSIGHT_BASE_URL must use HTTPS except for local development servers.")
        if not HINDSIGHT_BANK_ID.strip():
            raise ValueError("HINDSIGHT_BANK_ID cannot be empty.")
        if APP_ENV == "production" and not HINDSIGHT_API_KEY:
            raise ValueError("HINDSIGHT_API_KEY is required in production.")
    if LLM_BACKEND == "groq" and not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is required when LLM_BACKEND=groq.")
    if LLM_TIMEOUT_SECONDS <= 0:
        raise ValueError("LLM_TIMEOUT_SECONDS must be positive.")
