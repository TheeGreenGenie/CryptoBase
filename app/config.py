import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_db_url(url: str) -> str:
    """Convert a relative sqlite:/// URL to an absolute path anchored at BASE_DIR."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    rel = url[len(prefix) :]
    path = Path(rel)
    if not path.is_absolute():
        path = BASE_DIR / path
    return f"sqlite:///{path}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _resolve_db_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'defi_mvp.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Allow background threads to wait up to 20 s for a write lock instead of failing immediately
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 20}}

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    CHAIN_ID = int(os.getenv("CHAIN_ID", "31337"))
    CHAIN_NAME = os.getenv("CHAIN_NAME", "Anvil")
    RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
    BLOCK_EXPLORER_URL = os.getenv("BLOCK_EXPLORER_URL", "")

    LENDING_POOL_ADDRESS = os.getenv("LENDING_POOL_ADDRESS", "")
    COLLATERAL_TOKEN_ADDRESS = os.getenv("COLLATERAL_TOKEN_ADDRESS", "")
    WBTC_TOKEN_ADDRESS = os.getenv("WBTC_TOKEN_ADDRESS", "")
    DEBT_TOKEN_ADDRESS = os.getenv("DEBT_TOKEN_ADDRESS", "")
    PRICE_ORACLE_ADDRESS = os.getenv("PRICE_ORACLE_ADDRESS", "")

    UNISWAP_ROUTER_ADDRESS = os.getenv("UNISWAP_ROUTER_ADDRESS", "")

    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
    BASESCAN_API_KEY = os.getenv("BASESCAN_API_KEY", "")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GROK_API_KEY = os.getenv("GROK_API_KEY", "")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:11434/v1")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5:7b")

    MAIL_PROVIDER = os.getenv("MAIL_PROVIDER", "none")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", "")

    API_RATE_LIMIT = os.getenv("API_RATE_LIMIT", "60/minute")
    FAUCET_PRIVATE_KEY = os.getenv("FAUCET_PRIVATE_KEY", "")
    FAUCET_AMOUNT = int(os.getenv("FAUCET_AMOUNT", "10000"))
    WTF_CSRF_ENABLED = True

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Midnight Privacy Layer
    MIDNIGHT_RPC_URL = os.getenv("MIDNIGHT_RPC_URL", "")
    MIDNIGHT_CONTRACT_ADDRESS = os.getenv("MIDNIGHT_CONTRACT_ADDRESS", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    if env == "testing":
        return TestingConfig
    return DevelopmentConfig
