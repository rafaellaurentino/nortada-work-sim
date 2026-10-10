"""Configuração central. Tudo vem do arquivo .env (veja .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# IA (provedor gratuito). Dois formatos suportados:
#   AI_PROVIDER=gemini         -> API do Google AI Studio (tem camada gratuita)
#   AI_PROVIDER=openai_compat  -> qualquer API compatível com OpenAI (Groq, OpenRouter etc.)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gemini-2.0-flash")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")

TZ = os.getenv("TIMEZONE", "America/Sao_Paulo")

DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "state.db")))
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(ROOT / "docs")))
