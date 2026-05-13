# Autonomous AI Engineer — Coding Pipeline

## What It Does

You give it a plain English task like _"Build a sentiment analysis API"_ and it autonomously writes, runs, debugs, and assembles a fully working FastAPI application — no human intervention needed.

It uses **LangGraph** to orchestrate a team of AI agents, each with a single responsibility. The agents communicate through a shared state dictionary and the pipeline retries on errors automatically.

---

## How to Run

```bash
# Option 1 — Streamlit UI (recommended, visual)
streamlit run engineer_app.py

# Option 2 — FastAPI backend (Swagger UI)
uvicorn app:app --reload --port 8000
# Then open → http://localhost:8000/docs
```

---

## Files Involved

| File | Role |
|------|------|
| `engineer_app.py` | Streamlit UI — submit tasks, watch live logs |
| `app.py` | FastAPI backend — `POST /execute-task` endpoint |
| `pipeline.py` | LangGraph graph — wires all agents together, defines routing |
| `agents.py` | All agent logic — Planner, Coder, Debugger, Critic, Assembler |
| `tools.py` | `run_python_code` tool — subprocess execution |
| `state.py` | `AgentState` TypedDict — shared state schema |
| `config.py` | Central config — model name, retries, timeouts |
| `logger.py` | Rich-powered structured logger |
| `generated/` | Output folder — step files + final `app.py` |

---

## Agents

| Agent | What It Does |
|-------|-------------|
| **Planner** | Breaks your task into 3–6 ordered steps (returns a JSON array) |
| **Coder** | Writes Python code for one step at a time |
| **Executor** | Runs the code in a real `subprocess`, captures stdout/stderr |
| **Debugger** | Gets broken code + error → returns fixed code (up to 3 retries) |
| **Critic** | *(Optional)* Reviews code quality, returns improved version |
| **Assembler** | Merges all step files into one complete `generated/app.py` |
| **API Tester** | Starts the assembled app, hits `/health` and the POST endpoint |
| **API Debugger** | Fixes `app.py` if the API test fails, retries the test |

---

## Workflow

```
You submit: "Build a sentiment analysis API"
                    │
                    ▼
            ┌───────────────┐
            │   PLANNER     │  LLM breaks task into steps:
            │               │  ["Define FastAPI skeleton",
            └───────┬───────┘   "Add Pydantic model",
                    │           "Implement sentiment logic"]
                    │
          ┌─────────▼──────────────────────────┐
          │   Loop for each step               │
          │                                    │
          │   ┌──────────┐                     │
          │   │  CODER   │  LLM writes Python  │
          │   └────┬─────┘  code for this step │
          │        │                           │
          │   ┌────▼──────┐                    │
          │   │ EXECUTOR  │  subprocess.run()  │
          │   └────┬──────┘                    │
          │        │                           │
          │   success?                         │
          │   ├─ YES → FILE WRITER             │
          │   │        saves step_N.py         │
          │   │        move to next step ──────┘
          │   │
          │   └─ NO  → DEBUGGER (up to 3x)
          │            LLM fixes the code
          │            → back to EXECUTOR
          │
          │   (all steps done or max retries hit)
          │
          ▼
    ┌─────────────┐
    │  ASSEMBLER  │  LLM merges all step files into
    │             │  one complete generated/app.py
    └──────┬──────┘  + deterministic patches applied
           │
           ▼
    ┌─────────────┐
    │ API TESTER  │  1. Starts uvicorn on port 9000
    │             │  2. Polls GET /health (max 20s)
    └──────┬──────┘  3. Reads /openapi.json → finds POST route
           │         4. Builds test payload from schema
           │         5. POSTs payload → expects 200 OK
           │         6. Shuts down server
           │
      success?
      ├─ YES → STATUS: success ✓
      └─ NO  → API DEBUGGER → patches app.py → retries test
```

---

## State Machine

Every node reads from and writes to a central `AgentState` (TypedDict). Nodes return only the fields they changed — LangGraph merges the partial updates.

```
running → step_success → (next step or assembler)
running → step_error   → debugger → executor (retry)
success → END
api_error → api_debugger → api_test (retry)
failed  → END
```

---

## Key Design Decisions

**Why LangGraph instead of a for-loop?**
A for-loop can't express branching. The retry logic (executor → debugger → executor) is a conditional edge in the graph — explicit, visualizable, and easy to extend without touching other nodes.

**Why subprocess for code execution?**
Each step's code runs in an isolated `subprocess`, not `exec()`. A buggy step can't crash the pipeline, and there's a hard timeout (`EXEC_TIMEOUT=30s`).

**Why deterministic patching after assembly?**
Even at temperature 0, LLMs occasionally forget a `/health` endpoint or make data-flow mistakes. `_patch_app_code()` applies regex-based fixes after every assembly call — faster and more reliable than prompt engineering alone.

**Why no LLM for test payload generation?**
The API Tester reads `/openapi.json` live from the running app and maps field names to realistic values from a 60+ entry dictionary. No LLM call = no rate limits, no latency, no hallucinated payloads.

---

## Output

On success you get:
- `generated/step_1_xxx.py` … `step_N_xxx.py` — individual step files
- `generated/app.py` — the assembled, runnable FastAPI app
- `generated/requirements.txt` — dependencies for the generated app
- A test result confirming the API responded with 200 OK
