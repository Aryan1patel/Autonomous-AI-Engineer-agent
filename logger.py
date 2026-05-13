"""
logger.py — Structured logging for the Autonomous AI Engineer.

Wraps Python's standard `logging` module with:
  - Rich console handler (colored, timestamped output)
  - Helper functions used by all agents and pipeline nodes
"""

import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.logging import RichHandler
from config import LOG_LEVEL

# ── Console singleton (shared across the app) ────────────────────────────────
console = Console()

# ── Configure root logger with Rich ─────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
    ],
)

# Module-level logger — import and use this everywhere
logger = logging.getLogger("autonomous_engineer")


# ── Convenience helpers ──────────────────────────────────────────────────────

def log_step(step_name: str, message: str) -> str:
    """
    Log a pipeline step event and return a formatted log string
    that can be appended to AgentState.logs.
    """
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{step_name.upper()}] {message}"
    logger.info(f"[bold cyan]{step_name}[/bold cyan] — {message}")
    return entry


def log_error(step_name: str, error: str) -> str:
    """Log an error event and return the formatted log string."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{step_name.upper()}] ERROR: {error}"
    logger.error(f"[bold red]{step_name}[/bold red] — {error}")
    return entry


def log_success(step_name: str, message: str) -> str:
    """Log a success event and return the formatted log string."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{step_name.upper()}] ✓ {message}"
    logger.info(f"[bold green]{step_name}[/bold green] — ✓ {message}")
    return entry
