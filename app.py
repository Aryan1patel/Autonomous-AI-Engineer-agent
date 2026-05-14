"""
app.py — FastAPI backend for the Autonomous AI Engineer.

Endpoints:
  POST /execute-task          → run the full pipeline (blocking, returns final JSON)
  GET  /stream-task/{task_id} → SSE stream of live pipeline events
  POST /submit-task           → enqueue a task, returns a task_id immediately
  GET  /task/{task_id}        → poll status/result of a submitted task
  POST /generate-payload      → generate a test payload for the assembled app
  POST /run-api-test          → boot the assembled app and POST a test payload
  GET  /health                → liveness probe
  GET  /files/{filename}      → download a file from the generated/ directory
  GET  /files                 → list all files in the generated/ directory

Run with:
  uvicorn app:app --reload --port 8000
"""

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
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
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# In production set ALLOWED_ORIGINS=https://your-app.vercel.app (comma-separated for multiple)
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY TASK STORE  (good enough for a single-process deployment)
# ─────────────────────────────────────────────────────────────────────────────

# task_id → { status, result, events: queue.Queue }
_tasks: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Natural language description of the coding task to execute.",
        examples=["Build a sentiment analysis API using FastAPI"],
    )
    enable_critic: Optional[bool] = Field(
        default=False,
        description="Enable the optional Critic agent for code quality review.",
    )


class TaskResponse(BaseModel):
    status: str
    task: str
    plan: list[str]
    generated_files: list[str]
    outputs: list[str]
    errors: list[str]
    logs: list[str]


class SubmitResponse(BaseModel):
    task_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    generated_dir: str
    files_on_disk: int


class FileListResponse(BaseModel):
    files: list[str]
    count: int


class GeneratePayloadRequest(BaseModel):
    task: str
    endpoint: str = "/predict"
    openapi_schema: dict = {}


class ApiTestRequest(BaseModel):
    task: str
    app_path: str          # absolute path to the assembled app.py
    payload: Optional[dict] = None   # if None, auto-generate


class ApiTestResponse(BaseModel):
    success: bool
    endpoint: Optional[str] = None
    payload: Optional[dict] = None
    status_code: Optional[int] = None
    response: Optional[dict] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# SSE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _stream_task_events(task_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE lines from a task's event queue.
    Runs until the task produces a 'done' or 'error' event.
    """
    task = _tasks.get(task_id)
    if task is None:
        yield _sse_event({"type": "error", "message": "Task not found"})
        return

    event_queue: queue.Queue = task["events"]

    while True:
        try:
            # Non-blocking get with a short sleep to stay async-friendly
            event = event_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.1)
            continue

        yield _sse_event(event)

        if event.get("type") in ("done", "error"):
            break


def _run_pipeline_in_thread(task_id: str, task_text: str, enable_critic: bool):
    """
    Run the blocking pipeline in a background thread and push SSE events
    into the task's queue as the pipeline progresses.
    """
    task = _tasks[task_id]
    event_queue: queue.Queue = task["events"]

    def push(event: dict):
        event_queue.put(event)

    try:
        push({"type": "status", "stage": "planner", "message": "Planner agent starting…"})

        if enable_critic:
            os.environ["ENABLE_CRITIC"] = "true"

        result = run_pipeline(task_text)

        # Push log lines as individual events
        for log_line in result.get("logs", []):
            push({"type": "log", "message": log_line})

        # Push plan
        if result.get("plan"):
            push({"type": "plan", "steps": result["plan"]})

        # Push file list
        if result.get("generated_files"):
            push({"type": "files", "files": result["generated_files"]})

        # Push final status
        task["status"] = result["status"]
        task["result"] = result
        push({
            "type": "done",
            "status": result["status"],
            "task": result["task"],
            "plan": result.get("plan", []),
            "generated_files": result.get("generated_files", []),
            "outputs": result.get("outputs", []),
            "errors": result.get("errors", []),
            "logs": result.get("logs", []),
        })

    except Exception as exc:
        task["status"] = "failed"
        push({
            "type": "error",
            "message": f"Pipeline crashed: {exc}",
        })


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/submit-task", response_model=SubmitResponse, tags=["Pipeline"])
async def submit_task(request: TaskRequest) -> SubmitResponse:
    """
    Enqueue a pipeline task and return a task_id immediately.
    Poll GET /task/{task_id} or stream GET /stream-task/{task_id} for results.
    """
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "running",
        "result": None,
        "events": queue.Queue(),
    }

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(task_id, request.task, request.enable_critic or False),
        daemon=True,
    )
    thread.start()

    log_step("api", f"Task {task_id} submitted: {request.task[:60]}")
    return SubmitResponse(task_id=task_id, message="Task queued and running.")


@app.get("/stream-task/{task_id}", tags=["Pipeline"])
async def stream_task(task_id: str):
    """
    Server-Sent Events stream for a running task.
    Connect immediately after POST /submit-task and receive live progress events.
    """
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        _stream_task_events(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/task/{task_id}", tags=["Pipeline"])
async def get_task(task_id: str):
    """Poll the status and result of a submitted task."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task["result"],
    }


@app.post(
    "/execute-task",
    response_model=TaskResponse,
    summary="Run the autonomous coding pipeline (blocking)",
    tags=["Pipeline"],
)
async def execute_task(request: TaskRequest) -> TaskResponse:
    """
    Blocking endpoint — runs the full pipeline and returns final JSON.
    For real-time progress, use POST /submit-task + GET /stream-task/{id}.
    """
    log_step("api", f"Received task: {request.task[:80]}")
    if request.enable_critic is not None:
        os.environ["ENABLE_CRITIC"] = str(request.enable_critic).lower()

    try:
        result = run_pipeline(request.task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline crashed: {str(exc)}")

    return TaskResponse(
        status=result["status"],
        task=result["task"],
        plan=result["plan"],
        generated_files=result["generated_files"],
        outputs=result["outputs"],
        errors=result["errors"],
        logs=result["logs"],
    )


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    files_on_disk = len(list(GENERATED_DIR.glob("*.py")))
    return HealthResponse(
        status="ok",
        version="2.0.0",
        generated_dir=str(GENERATED_DIR.resolve()),
        files_on_disk=files_on_disk,
    )


@app.get("/files", response_model=FileListResponse, tags=["Files"])
async def list_files() -> FileListResponse:
    files = sorted(p.name for p in GENERATED_DIR.glob("*.py"))
    return FileListResponse(files=files, count=len(files))


@app.get("/files/{filename}", tags=["Files"])
async def download_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    target = GENERATED_DIR / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found")
    return FileResponse(path=str(target), filename=safe_name, media_type="text/plain")


@app.post("/generate-payload", tags=["Testing"])
async def generate_payload_endpoint(request: GeneratePayloadRequest) -> dict:
    """
    Generate a realistic test payload for the assembled app's POST endpoint.
    Uses the task description + OpenAPI schema to pick field values.
    """
    from agents import generate_test_payload
    payload = generate_test_payload(request.task, request.endpoint, request.openapi_schema)
    return {"payload": payload}


@app.post("/run-api-test", response_model=ApiTestResponse, tags=["Testing"])
async def run_api_test_endpoint(request: ApiTestRequest) -> ApiTestResponse:
    """
    Boot the assembled FastAPI app, discover its first POST endpoint,
    POST the provided (or auto-generated) payload, and return the result.
    Runs in a thread so it doesn't block the event loop.
    """
    from agents import generate_test_payload
    from config import TEST_PORT

    app_path = Path(request.app_path)
    if not app_path.exists():
        raise HTTPException(status_code=404, detail=f"App file not found: {request.app_path}")

    def _free_port(port: int):
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
            pids = result.stdout.strip().split()
            for pid in pids:
                subprocess.run(["kill", "-9", pid], capture_output=True)
            if pids:
                time.sleep(0.5)
        except Exception:
            pass

    def _run_test() -> dict:
        import requests as req
        _free_port(TEST_PORT)
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app:app",
                 f"--port={TEST_PORT}", "--log-level=error"],
                cwd=str(app_path.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Poll until server is ready (max 30s)
            ready = False
            crash_err = ""
            for _ in range(30):
                time.sleep(1)
                if proc.poll() is not None:
                    crash_err = proc.stderr.read().decode(errors="replace")[:600]
                    break
                try:
                    r = req.get(f"http://127.0.0.1:{TEST_PORT}/health", timeout=2)
                    if r.status_code < 500:
                        ready = True
                        break
                except req.exceptions.ConnectionError:
                    pass
                except Exception:
                    pass

            if not ready:
                err = crash_err if crash_err else "Timeout — server did not start in 30s"
                return {"success": False, "error": f"Server failed to start: {err}"}

            base = f"http://127.0.0.1:{TEST_PORT}"
            endpoint = "/predict"
            openapi: dict = {}
            try:
                openapi = req.get(f"{base}/openapi.json", timeout=5).json()
                for path, methods in openapi.get("paths", {}).items():
                    if "post" in methods and path not in ("/", "/health"):
                        endpoint = path
                        break
            except Exception:
                pass

            payload = request.payload if request.payload is not None else generate_test_payload(request.task, endpoint, openapi)

            response = req.post(f"{base}{endpoint}", json=payload, timeout=10)
            if response.status_code != 200:
                return {
                    "success": False,
                    "endpoint": endpoint,
                    "payload": payload,
                    "error": f"HTTP {response.status_code}: {response.text[:300]}",
                }
            return {
                "success": True,
                "endpoint": endpoint,
                "payload": payload,
                "status_code": response.status_code,
                "response": response.json(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()

    # Run the blocking test in a thread
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_test)
    return ApiTestResponse(**result)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    GENERATED_DIR.mkdir(exist_ok=True)
    log_step("api", f"Server v2 started. Generated dir: {GENERATED_DIR.resolve()}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)