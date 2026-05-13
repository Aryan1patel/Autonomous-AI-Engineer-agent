"""
tools.py — Agent tools for the Autonomous AI Engineer.

These are the executable capabilities injected into LangGraph nodes:
  - run_python_code  : executes code in a sandboxed subprocess
  - write_file       : saves generated code to the `generated/` directory
  - read_file        : reads back a previously saved file
  - log_output       : appends a message to the running session log
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from langchain.tools import tool

from config import GENERATED_DIR, EXEC_TIMEOUT
from logger import log_step, log_error, log_success


# ── Tool 1: Run Python Code ──────────────────────────────────────────────────

@tool
def run_python_code(code: str) -> str:
    """
    Execute a Python code string in an isolated subprocess and return the result.

    The code runs with a hard timeout (default 30s). Both stdout and stderr are
    captured and returned as a single formatted string so the Executor / Debugger
    agents can reason about the output.

    Returns a string in the format:
        STATUS: success | error
        STDOUT: <captured output>
        STDERR: <error message if any>
    """
    log_step("executor", "Running code in subprocess...")

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],   # -c runs a string as Python code
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT,
        )

        stdout = result.stdout.strip() or "(no output)"
        stderr = result.stderr.strip()

        if result.returncode == 0:
            log_success("executor", f"Execution succeeded. Output: {stdout[:80]}")
            return (
                f"STATUS: success\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr or '(none)'}"
            )
        else:
            log_error("executor", f"Execution failed. Error: {stderr[:120]}")
            return (
                f"STATUS: error\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

    except subprocess.TimeoutExpired:
        msg = f"Execution timed out after {EXEC_TIMEOUT}s"
        log_error("executor", msg)
        return f"STATUS: error\nSTDOUT: (none)\nSTDERR: {msg}"

    except Exception as exc:
        log_error("executor", str(exc))
        return f"STATUS: error\nSTDOUT: (none)\nSTDERR: {exc}"


# ── Tool 2: Write File ────────────────────────────────────────────────────────

@tool
def write_file(filename: str, content: str) -> str:
    """
    Write content to a file inside the `generated/` directory.

    Automatically creates subdirectories if needed. Returns the absolute
    path of the written file so the agent can confirm the save location.

    Args:
        filename : Relative filename, e.g. "sentiment_api.py" or "utils/helpers.py"
        content  : The text content to write (typically Python source code)

    Returns:
        A confirmation string with the full path, e.g. "FILE_SAVED: /path/generated/sentiment_api.py"
    """
    target: Path = GENERATED_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)  # create subdirs if needed
    target.write_text(content, encoding="utf-8")

    log_success("file_writer", f"Saved → {target}")
    return f"FILE_SAVED: {target.resolve()}"


# ── Tool 3: Read File ─────────────────────────────────────────────────────────

@tool
def read_file(filename: str) -> str:
    """
    Read and return the content of a file from the `generated/` directory.

    Args:
        filename : Relative filename, e.g. "sentiment_api.py"

    Returns:
        File content as string, or an error message if the file is not found.
    """
    target: Path = GENERATED_DIR / filename

    if not target.exists():
        msg = f"FILE_NOT_FOUND: {target.resolve()}"
        log_error("file_reader", msg)
        return msg

    content = target.read_text(encoding="utf-8")
    log_step("file_reader", f"Read {len(content)} chars from {target.name}")
    return f"FILE_CONTENT ({filename}):\n{content}"


# ── Tool 4: Log Output ────────────────────────────────────────────────────────

@tool
def log_output(message: str) -> str:
    """
    Append a log entry with an ISO timestamp to the session log.

    Agents call this to record reasoning steps, decisions, or status updates
    that should appear in the final API response under `logs`.

    Returns the formatted log entry string.
    """
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    log_step("log", message)
    return entry
