"""
app.py — FastAPI backend for the Autonomous AI Engineer.

Endpoints:
  POST /execute-task        → run the full pipeline for a coding task
  GET  /health              → liveness probe
  GET  /files/{filename}    → download a file from the generated/ directory
  GET  /files               → list all files in the generated/ directory

Run with:
  uvicorn app:app --reload --port 8000
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import GENERATED_DIR
from pipeline import run_pipeline
from logger import log_step


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous AI Engineer",
    description=(
        "A LangGraph-powered multi-agent system that takes a natural language "
        "coding task and autonomously plans, generates, executes, debugs, and "
        "delivers working Python code."
    ),
    version="1.0.0",
    docs_url="/docs",      # Swagger UI at /docs
    redoc_url="/redoc",    # ReDoc at /redoc
)

# Allow all origins for development — restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    """Request body for POST /execute-task."""

    task: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural language description of the coding task to execute.",
        examples=["Build a sentiment analysis API using FastAPI"],
    )
    enable_critic: Optional[bool] = Field(
        default=False,
        description="Set to true to enable the optional Critic agent for code quality review.",
    )


class TaskResponse(BaseModel):
    """Response body returned by POST /execute-task."""

    status: str = Field(description="'success' or 'failed'")
    task: str = Field(description="The original task string")
    plan: list[str] = Field(description="Ordered list of steps produced by the Planner")
    generated_files: list[str] = Field(description="Paths of files saved to disk")
    outputs: list[str] = Field(description="Stdout captured from each execution")
    errors: list[str] = Field(description="Stderr messages collected across all retries")
    logs: list[str] = Field(description="Timestamped structured log of pipeline events")


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    version: str
    generated_dir: str
    files_on_disk: int


class FileListResponse(BaseModel):
    """Response body for GET /files."""

    files: list[str]
    count: int


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/execute-task",
    response_model=TaskResponse,
    summary="Run the autonomous coding pipeline",
    tags=["Pipeline"],
)
async def execute_task(request: TaskRequest) -> TaskResponse:
    """
    Accept a natural language coding task and run the full multi-agent pipeline:

    1. **Planner** — breaks the task into ordered steps
    2. **Coder** — writes Python code for each step
    3. **Executor** — runs each code snippet in a sandboxed subprocess
    4. **Debugger** — fixes errors and retries (up to MAX_RETRIES times)
    5. **File Writer** — saves successful code to `generated/`
    6. **Critic** *(optional)* — reviews final code for quality

    Returns generated files, execution logs, and a final status.
    """
    log_step("api", f"Received task: {request.task[:80]}")

    # Temporarily override ENABLE_CRITIC if the request overrides it
    if request.enable_critic is not None:
        os.environ["ENABLE_CRITIC"] = str(request.enable_critic).lower()

    try:
        result = run_pipeline(request.task)
    except Exception as exc:
        # Catch unexpected errors and return a 500 with detail
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline crashed unexpectedly: {str(exc)}",
        )

    return TaskResponse(
        status=result["status"],
        task=result["task"],
        plan=result["plan"],
        generated_files=result["generated_files"],
        outputs=result["outputs"],
        errors=result["errors"],
        logs=result["logs"],
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness / health check",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """
    Returns 200 with system info if the service is up and the generated/
    directory is accessible. Safe to use as a Kubernetes/Docker liveness probe.
    """
    files_on_disk = len(list(GENERATED_DIR.glob("*.py")))

    return HealthResponse(
        status="ok",
        version="1.0.0",
        generated_dir=str(GENERATED_DIR.resolve()),
        files_on_disk=files_on_disk,
    )


@app.get(
    "/files",
    response_model=FileListResponse,
    summary="List all generated files",
    tags=["Files"],
)
async def list_files() -> FileListResponse:
    """
    Returns a list of all Python files currently stored in the `generated/`
    directory (filenames only, not full paths).
    """
    files = sorted(p.name for p in GENERATED_DIR.glob("*.py"))
    return FileListResponse(files=files, count=len(files))


@app.get(
    "/files/{filename}",
    summary="Download a generated file",
    tags=["Files"],
)
async def download_file(filename: str) -> FileResponse:
    """
    Download a specific generated file by name.

    Args:
        filename: The filename (e.g., `step_1_sentiment_api.py`)

    Returns:
        The raw file as a downloadable attachment.

    Raises:
        404 if the file does not exist.
    """
    # Security: prevent path traversal attacks
    safe_name = Path(filename).name   # strips any directory components
    target = GENERATED_DIR / safe_name

    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{safe_name}' not found in generated/",
        )

    return FileResponse(
        path=str(target),
        filename=safe_name,
        media_type="text/plain",
    )


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP / SHUTDOWN EVENTS
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Ensure the generated/ directory exists on server start."""
    GENERATED_DIR.mkdir(exist_ok=True)
    log_step("api", f"Server started. Generated dir: {GENERATED_DIR.resolve()}")


# ─────────────────────────────────────────────────────────────────────────────
# DEV SERVER (direct run: python app.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)