"""
state.py — Shared state schema for the Autonomous AI Engineer pipeline.
"""

from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict):
    """
    Central state passed through every node in the LangGraph pipeline.

    Step-generation fields (existing):
        task            : Original natural language task.
        plan            : Ordered steps from the Planner.
        current_step    : Index into `plan` currently being processed.
        code            : Python code for the current step.
        errors          : Accumulated step-level error messages.
        outputs         : Stdout from each successful step execution.
        retry_count     : Debug/retry attempts for the current step.
        status          : "running" | "success" | "failed" | "api_error"
        generated_files : Paths of step files written to generated/.
        logs            : Structured timestamped pipeline log.

    Assembly & testing fields (new):
        assembled_app       : Full merged app.py code string.
        assembled_app_path  : Absolute path to generated/app.py.
        test_result         : Dict with API test response data.
        api_retry_count     : Retry counter for the API test/debug loop.
        api_error           : Last API-level error string.
    """

    # ── Step generation ──────────────────────────────────────────────────
    task: str
    plan: List[str]
    current_step: int
    code: str
    errors: List[str]
    outputs: List[str]
    retry_count: int
    status: str
    generated_files: List[str]
    logs: List[str]

    # ── Assembly & API testing ───────────────────────────────────────────
    assembled_app: str
    assembled_app_path: str
    test_result: Dict[str, Any]
    api_retry_count: int
    api_error: str
