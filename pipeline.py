"""
pipeline.py — LangGraph orchestrator for the Autonomous AI Engineer.

Graph topology:
  START
    │
    ▼
  [planner]       → generates ordered plan from the user task
    │
    ▼
  [coder]         → writes Python code for the current step
    │
    ▼
  [executor]      → runs the code, captures stdout / stderr
    │
    ├── success ──▶ [file_writer] → save file → next step ──▶ loop back to coder
    │                                         └── all steps done ──▶ [assembler]
    └── error ───▶ [debugger] → fix code → back to executor
                        │
                        └── max retries hit ──▶ FAILED → END
    ▼
  [assembler]     → merges all step files into one complete generated/app.py
    │
    ▼
  [api_tester]    → starts app with uvicorn, tests /health + /predict, shuts down
    │
    ├── success ──▶ END  (status = "success")
    └── error ───▶ [api_debugger] → fix assembled app → retry api_tester
                        │
                        └── max API retries hit ──▶ FAILED → END
"""

import sys
import json
import time
import subprocess
import requests as req
from pathlib import Path

from langgraph.graph import StateGraph, END
from state import AgentState
from config import MAX_RETRIES, ENABLE_CRITIC, GENERATED_DIR, BASE_DIR
from logger import log_step, log_error, log_success
from agents import (
    run_planner, run_coder, run_executor,
    run_debugger, run_critic, run_assembler,
    generate_test_payload,
)

# Max retries for the API test + debug loop
API_MAX_RETRIES: int = 2
# Port used exclusively for testing the generated app (separate from port 8000)
TEST_PORT: int = 9000


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — free the test port before starting the server
# ─────────────────────────────────────────────────────────────────────────────

def _free_port(port: int) -> None:
    """Kill any process occupying `port` on macOS/Linux."""
    subprocess.run(
        f"lsof -ti :{port} | xargs kill -9 2>/dev/null || true",
        shell=True,
        check=False,
    )
    time.sleep(0.4)


# ─────────────────────────────────────────────────────────────────────────────
# STEP-GENERATION NODES  (unchanged logic from v1)
# ─────────────────────────────────────────────────────────────────────────────

def planner_node(state: AgentState) -> dict:
    """Decompose the user task into an ordered list of steps."""
    log_step("pipeline", f"▶ Planner starting for task: {state['task'][:60]}")
    plan = run_planner(state["task"])
    entry = log_step("planner", f"Plan created with {len(plan)} steps")
    return {
        "plan": plan,
        "current_step": 0,
        "retry_count": 0,
        "api_retry_count": 0,
        "status": "running",
        "errors": [],
        "outputs": [],
        "generated_files": [],
        "assembled_app": "",
        "assembled_app_path": "",
        "test_result": {},
        "api_error": "",
        "logs": state.get("logs", []) + [entry],
    }


def coder_node(state: AgentState) -> dict:
    """Generate Python code for the current plan step."""
    step_index = state["current_step"]
    step_text  = state["plan"][step_index]
    log_step("pipeline", f"▶ Coder — step {step_index + 1}/{len(state['plan'])}: {step_text[:60]}")
    code  = run_coder(state["task"], step_text)
    entry = log_step("coder", f"Code generated for step {step_index + 1} ({len(code.splitlines())} lines)")
    return {"code": code, "retry_count": 0, "logs": state["logs"] + [entry]}


def executor_node(state: AgentState) -> dict:
    """Run the current code in a sandboxed subprocess."""
    log_step("pipeline", "▶ Executor running code...")
    stdout, stderr, success = run_executor(state["code"])
    new_outputs = state["outputs"] + ([stdout] if stdout else [])
    new_errors  = state["errors"]  + ([stderr] if stderr and not success else [])
    if success:
        entry = log_success("executor", f"Step {state['current_step'] + 1} executed successfully")
        return {"outputs": new_outputs, "errors": new_errors, "status": "step_success", "logs": state["logs"] + [entry]}
    else:
        entry = log_error("executor", f"Execution failed (attempt {state['retry_count'] + 1}/{MAX_RETRIES})")
        return {"outputs": new_outputs, "errors": new_errors, "status": "step_error", "logs": state["logs"] + [entry]}


def debugger_node(state: AgentState) -> dict:
    """Fix the current step's code using the last error."""
    last_error  = state["errors"][-1] if state["errors"] else "Unknown error"
    new_retry   = state["retry_count"] + 1
    log_step("pipeline", f"▶ Debugger fixing step code (attempt {new_retry}/{MAX_RETRIES})...")
    fixed_code  = run_debugger(state["code"], last_error)
    entry       = log_step("debugger", f"Fixed code on attempt {new_retry}")
    return {"code": fixed_code, "retry_count": new_retry, "logs": state["logs"] + [entry]}


def file_writer_node(state: AgentState) -> dict:
    """Save the successfully executed step code and advance to the next step."""
    step_index = state["current_step"]
    step_text  = state["plan"][step_index]

    # Build a safe filename from the step description
    safe_name = "_".join(step_text.lower().split()[:5])
    safe_name = "".join(c if c.isalnum() or c == "_" else "" for c in safe_name)
    filename  = f"step_{step_index + 1}_{safe_name}.py"

    filepath  = GENERATED_DIR / filename
    filepath.write_text(state["code"], encoding="utf-8")

    new_files = state["generated_files"] + [str(filepath.resolve())]
    next_step = step_index + 1
    all_done  = next_step >= len(state["plan"])

    entry = log_success("file_writer", f"Step {step_index + 1} complete → saved as {filename}")

    # Optional critic pass on the final step
    final_code = state["code"]
    extra_logs = []
    if all_done and ENABLE_CRITIC:
        review, improved = run_critic(state["task"], state["code"])
        final_code = improved
        extra_logs = [log_step("critic", f"Review: {review[:200]}")]
        filepath.write_text(improved, encoding="utf-8")

    return {
        "generated_files": new_files,
        "current_step": next_step,
        "retry_count": 0,
        # "running" → keep looping; "steps_done" → move to assembler
        "status": "steps_done" if all_done else "running",
        "code": final_code,
        "logs": state["logs"] + [entry] + extra_logs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLER NODE
# ─────────────────────────────────────────────────────────────────────────────

def assembler_node(state: AgentState) -> dict:
    """
    Read all generated step files, call the Assembler agent to merge them
    into one complete FastAPI app, and save to generated/app.py.
    """
    log_step("pipeline", "▶ Assembler merging all step files...")

    # Collect step file contents
    snippets = []
    for i, fpath in enumerate(state["generated_files"], 1):
        try:
            content = Path(fpath).read_text(encoding="utf-8")
            snippets.append(f"# === STEP {i} ===\n{content}")
        except Exception:
            pass

    combined    = "\n\n".join(snippets)
    assembled   = run_assembler(state["task"], combined)

    # Save the assembled app
    app_path = GENERATED_DIR / "app.py"
    app_path.write_text(assembled, encoding="utf-8")

    # Also write a minimal requirements.txt alongside the generated app
    req_path = GENERATED_DIR / "requirements.txt"
    req_path.write_text(
        "fastapi>=0.111.0\nuvicorn[standard]>=0.29.0\npydantic>=2.5.0\n",
        encoding="utf-8",
    )

    entry = log_success("assembler", f"Assembled app saved → {app_path.name} ({len(assembled.splitlines())} lines)")
    return {
        "assembled_app":      assembled,
        "assembled_app_path": str(app_path.resolve()),
        "status":             "success",
        "generated_files":    state["generated_files"] + [
            str(app_path.resolve()),
            str(req_path.resolve()),
        ],
        "api_retry_count": 0,
        "api_error": "",
        "logs": state["logs"] + [entry],
    }


# ─────────────────────────────────────────────────────────────────────────────
# API TEST NODE  (launch → health probe → /predict test → shutdown)
# ─────────────────────────────────────────────────────────────────────────────

def api_test_node(state: AgentState) -> dict:
    """
    Start the assembled FastAPI app on TEST_PORT, probe /health to confirm
    it's up, then discover and test the main POST endpoint.
    Falls back to /openapi.json to find the real endpoint name if /predict is 404.
    """
    log_step("pipeline", f"▶ API Tester — launching server on port {TEST_PORT}...")

    _free_port(TEST_PORT)

    proc = None
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "app:app",
                f"--port={TEST_PORT}",
                "--log-level=error",
            ],
            cwd=str(GENERATED_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # ── Poll /health until server is ready (max 20 s) ───────────────
        ready = False
        for _ in range(20):
            time.sleep(1)
            if proc.poll() is not None:
                break
            try:
                r = req.get(f"http://127.0.0.1:{TEST_PORT}/health", timeout=2)
                if r.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass

        if not ready:
            stderr_out = ""
            if proc.poll() is not None:
                stderr_out = proc.stderr.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Server failed to start within 20 s.\nstderr: {stderr_out}")

        log_success("api_tester", f"Server is up on port {TEST_PORT}")

        # ── Discover POST endpoint from OpenAPI schema ────────────────────
        base      = f"http://127.0.0.1:{TEST_PORT}"
        endpoint  = "/predict"
        openapi   = {}

        try:
            openapi = req.get(f"{base}/openapi.json", timeout=5).json()
            for path, methods in openapi.get("paths", {}).items():
                if "post" in methods and path not in ("/", "/health"):
                    endpoint = path
                    log_step("api_tester", f"Discovered POST endpoint: {endpoint}")
                    break
        except Exception:
            pass

        # ── Build test payload from schema (no LLM, no rate limits) ──────
        test_payload = generate_test_payload(state["task"], endpoint, openapi)

        response = req.post(f"{base}{endpoint}", json=test_payload, timeout=10)

        if response.status_code != 200:
            raise RuntimeError(
                f"{endpoint} returned HTTP {response.status_code}: {response.text[:400]}"
            )

        resp_json = response.json()
        test_result = {
            "success":     True,
            "status_code": response.status_code,
            "endpoint":    endpoint,
            "input":       test_payload,
            "response":    resp_json,
        }

        entry = log_success(
            "api_tester",
            f"API test PASSED — {endpoint} returned: {resp_json}",
        )
        return {
            "test_result": test_result,
            "status":      "success",
            "logs":        state["logs"] + [entry],
        }

    except Exception as exc:
        error_msg = str(exc)
        entry = log_error("api_tester", f"API test FAILED: {error_msg[:200]}")
        return {
            "test_result": {"success": False, "error": error_msg},
            "api_error":   error_msg,
            "status":      "api_error",
            "logs":        state["logs"] + [entry],
        }

    finally:
        # Always shut down the test server
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        _free_port(TEST_PORT)


# ─────────────────────────────────────────────────────────────────────────────
# API DEBUGGER NODE
# ─────────────────────────────────────────────────────────────────────────────

def api_debugger_node(state: AgentState) -> dict:
    """
    Fix the assembled app.py using the API error from the last test run.
    Increments api_retry_count and saves the fixed code back to generated/app.py.
    """
    new_retry  = state["api_retry_count"] + 1
    log_step("pipeline", f"▶ API Debugger fixing app.py (attempt {new_retry}/{API_MAX_RETRIES})...")

    fixed_code = run_debugger(state["assembled_app"], state["api_error"])

    # Persist the fixed version
    app_path = GENERATED_DIR / "app.py"
    app_path.write_text(fixed_code, encoding="utf-8")

    entry = log_step("api_debugger", f"Fixed app.py on attempt {new_retry}")
    return {
        "assembled_app":      fixed_code,
        "assembled_app_path": str(app_path.resolve()),
        "api_retry_count":    new_retry,
        "logs":               state["logs"] + [entry],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONDITIONAL EDGE ROUTERS
# ─────────────────────────────────────────────────────────────────────────────

def route_after_executor(state: AgentState) -> str:
    if state["status"] == "step_success":
        return "file_writer"
    if state["retry_count"] < MAX_RETRIES:
        return "debugger"
    log_error("pipeline", f"Max step retries ({MAX_RETRIES}) reached — FAILED.")
    return END


def route_after_file_writer(state: AgentState) -> str:
    """After saving a step file: loop back for next step, or move to assembler."""
    if state["status"] == "steps_done":
        return "assembler"
    return "coder"


def route_after_api_test(state: AgentState) -> str:
    """After API test: success → END, error with retries → api_debugger, exhausted → END."""
    if state["status"] == "success":
        return END
    if state["api_retry_count"] < API_MAX_RETRIES:
        return "api_debugger"
    log_error("pipeline", f"Max API retries ({API_MAX_RETRIES}) reached — FAILED.")
    return END


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_pipeline() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes (api_tester / api_debugger removed — triggered manually from UI)
    graph.add_node("planner",     planner_node)
    graph.add_node("coder",       coder_node)
    graph.add_node("executor",    executor_node)
    graph.add_node("debugger",    debugger_node)
    graph.add_node("file_writer", file_writer_node)
    graph.add_node("assembler",   assembler_node)

    # Entry point
    graph.set_entry_point("planner")

    # Fixed edges
    graph.add_edge("planner",  "coder")
    graph.add_edge("coder",    "executor")
    graph.add_edge("debugger", "executor")
    graph.add_edge("assembler", END)   # pipeline ends here; UI handles testing

    # Conditional edges
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {"file_writer": "file_writer", "debugger": "debugger", END: END},
    )
    graph.add_conditional_edges(
        "file_writer",
        route_after_file_writer,
        {"coder": "coder", "assembler": "assembler"},
    )

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(task: str) -> AgentState:
    """
    Execute the full pipeline for a coding task.

    Returns the final AgentState with:
        status           → "success" | "failed"
        generated_files  → all step files + generated/app.py + generated/requirements.txt
        test_result      → API test response dict
        logs             → full structured execution log
    """
    log_step("pipeline", f"Pipeline started: {task}")

    pipeline = build_pipeline()

    initial_state: AgentState = {
        "task":               task,
        "plan":               [],
        "current_step":       0,
        "code":               "",
        "errors":             [],
        "outputs":            [],
        "retry_count":        0,
        "status":             "running",
        "generated_files":    [],
        "assembled_app":      "",
        "assembled_app_path": "",
        "test_result":        {},
        "api_retry_count":    0,
        "api_error":          "",
        "logs":               [log_step("pipeline", f"Task received: {task}")],
    }

    final_state: AgentState = pipeline.invoke(initial_state)

    if final_state["status"] == "success":
        log_success("pipeline", f"Pipeline complete. Files: {final_state['generated_files']}")
    else:
        log_error("pipeline", "Pipeline ended with FAILED status")

    return final_state


# ── CLI quick-test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    task = input("\n🤖 Enter your coding task: ").strip()
    result = run_pipeline(task)
    print("\n" + "=" * 60)
    print(f"STATUS      : {result['status']}")
    print(f"PLAN        : {json.dumps(result['plan'], indent=2)}")
    print(f"FILES       : {result['generated_files']}")
    print(f"TEST RESULT : {result['test_result']}")
    print("=" * 60)
