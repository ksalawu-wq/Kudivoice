"""
config.py — Central configuration for KudiVoice AI.

SECURITY NOTE (cybersecurity-grad rationale):
  * All secrets (API keys) are loaded from a local .env file via python-dotenv
    and are NEVER hardcoded in source. This keeps credentials out of version
    control (see .gitignore) and out of the code we hand to judges/graders.
  * The rest of the app only ever sees booleans about *whether* a key exists
    (see `secrets_status()`) — the raw key value is never returned, printed,
    or logged anywhere.
  * A single configuration choke-point means there is exactly one module that
    touches os.environ, which keeps the secret-handling surface easy to audit.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root exactly once, at import time.
# override=False => a real OS environment variable wins over the .env file,
# which is the safer default for CI / container deployments.
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


# ---------------------------------------------------------------------------
# Secrets — read from the environment ONLY. Never assign literals here.
# ---------------------------------------------------------------------------
# NOTE: these may be None. We deliberately DO NOT raise at import time so the
# demo still boots offline; nvidia_extractor falls back to a hardcoded, schema
# -valid transaction when no key/network is available (see DEMO RESILIENCE).
NVIDIA_API_KEY: str | None = os.getenv("NVIDIA_API_KEY")
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")


# ---------------------------------------------------------------------------
# Model / endpoint configuration (non-secret — safe to keep in source).
# ---------------------------------------------------------------------------
NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL: str = "meta/llama-3.3-70b-instruct"

GROQ_BASE_URL: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL: str = "llama-3.3-70b-versatile"

# Low temperature => stable, near-deterministic JSON extraction.
LLM_TEMPERATURE: float = 0.1
LLM_MAX_TOKENS: int = 1024
LLM_TIMEOUT_SECONDS: int = 30


# ---------------------------------------------------------------------------
# Local storage & display.
# ---------------------------------------------------------------------------
DB_PATH: str = str(_PROJECT_ROOT / "kudivoice.db")

CURRENCY: str = "NGN"
CURRENCY_SYMBOL: str = "₦"  # ₦ (escaped so the file stays ASCII-safe on Windows)


def has_nvidia_key() -> bool:
    """True if a NVIDIA NIM key is configured. Never returns the key itself."""
    return bool(NVIDIA_API_KEY)


def has_groq_key() -> bool:
    """True if a Groq fallback key is configured. Never returns the key itself."""
    return bool(GROQ_API_KEY)


def secrets_status() -> dict[str, bool]:
    """
    Log/UI-safe summary of which providers are configured.
    Returns booleans ONLY — never the secret values (prevents key leakage).
    """
    return {"nvidia": has_nvidia_key(), "groq": has_groq_key()}
