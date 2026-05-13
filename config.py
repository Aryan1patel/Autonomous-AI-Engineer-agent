"""
config.py — Centralized configuration for the Autonomous AI Engineer.

All tuneable constants live here. No magic numbers scattered across the codebase.
"""

import os
from pathlib import Path

# ── Directory / Paths ────────────────────────────────────────────────────────

# Root of the project (parent of this file)
BASE_DIR: Path = Path(__file__).parent

# All AI-generated files are written here (auto-created if missing)
GENERATED_DIR: Path = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

# ── LLM / Model ─────────────────────────────────────────────────────────────

# Groq model — free/developer plan.
# llama-3.1-8b-instant and llama-3.3-70b-versatile are now Enterprise-only.
# openai/gpt-oss-20b has only 8K TPM on the free tier — too small for this pipeline.
# openai/gpt-oss-120b has 250K TPM on the free tier and handles larger prompts fine.
MODEL_NAME: str = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")

# LLM temperature — 0 = deterministic, great for code generation
LLM_TEMPERATURE: float = 0.0

# ── Pipeline Behaviour ───────────────────────────────────────────────────────

# Max number of debug+retry attempts per step before marking it failed
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

# Enable the optional Critic agent (improves code quality, costs extra LLM call)
ENABLE_CRITIC: bool = os.getenv("ENABLE_CRITIC", "false").lower() == "true"

# ── Code Execution ───────────────────────────────────────────────────────────

# Hard timeout (seconds) for each subprocess code execution run
EXEC_TIMEOUT: int = int(os.getenv("EXEC_TIMEOUT", "30"))

# ── API Testing ─────────────────────────────────────────────────────────────

# Port used by the assembled app during the manual API test
TEST_PORT: int = int(os.getenv("TEST_PORT", "9000"))

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
