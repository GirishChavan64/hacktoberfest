import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
# override=True: values in .env win over stray OS/shell environment variables
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

class Config:
    """Application configuration."""
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip()

    # Comma-separated list of models players may choose from.
    # The player may only pick from this list; LLM_MODEL is the default.
    _llm_models_raw = os.getenv(
        "LLM_MODELS",
        "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b"
    )
    LLM_MODELS: list = [m.strip() for m in _llm_models_raw.split(",") if m.strip()]

    # Deterministic mock LLM flag (default True if unset or '1')
    mock_env = os.getenv("MOCK_LLM", "1").strip().lower()
    MOCK_LLM = mock_env in ("1", "true", "yes")

    # Flask debug mode: off unless FLASK_DEBUG=1 (never enable in production)
    DEBUG = os.getenv("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes")

    PORT = int(os.getenv("PORT", "5000"))
    HOST = os.getenv("HOST", "0.0.0.0")

    CASES_DIR = BASE_DIR / "cases"
    STATIC_DIR = BASE_DIR / "static"
    TEMPLATES_DIR = BASE_DIR / "templates"


def describe_mode() -> str:
    """One-line, secret-free summary of how the game will run (printed at startup)."""
    if Config.MOCK_LLM:
        why = "MOCK_LLM=1" if ENV_FILE.exists() else "no .env file found next to app.py, defaulting to MOCK"
        return f"MODE: MOCK (canned replies, no real AI) - {why}"
    key = "set" if Config.LLM_API_KEY else "MISSING"
    return f"MODE: LIVE - model={Config.LLM_MODEL} base_url={Config.LLM_BASE_URL} api_key={key}"
