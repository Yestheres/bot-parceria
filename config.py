from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


# ---------- Discord ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN não configurado. "
        "Configure nas variáveis de ambiente da Shard Cloud."
    )


# ---------- Postgres ----------
_raw_db_url = os.getenv("DATABASE_URL")
if not _raw_db_url:
    raise RuntimeError(
        "DATABASE_URL não configurada. "
        "Copie a connection string do painel da Shard Cloud."
    )


def _normalize_db_url(url: str) -> str:
    """asyncpg só aceita postgresql:// e sslmode=..."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if "ssl=true" in url and "sslmode" not in url:
        url = url.replace("ssl=true", "sslmode=require")
    if "ssl=false" in url and "sslmode" not in url:
        url = url.replace("ssl=false", "sslmode=disable")
    return url


DATABASE_URL = _normalize_db_url(_raw_db_url)


# ---------- Constantes do bot ----------
BOT_NAME = "Parceria"

WIZARD_TIMEOUT_SECONDS = 15 * 60
MAX_SERVER_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 2000
MAX_IMAGE_URL_LENGTH = 500

EMBED_COLORS: dict[str, int] = {
    "azul": 0x5865F2,
    "roxo": 0x9B59B6,
    "verde": 0x57F287,
    "amarelo": 0xFEE75C,
    "vermelho": 0xED4245,
    "rosa": 0xEB459E,
    "cinza": 0x99AAB5,
}
DEFAULT_COLOR = "azul"


# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("parceria")
