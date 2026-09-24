# 🤖 Autonomous AI Engineer — Multi-Agent Research & Code Generation System

> A **LangGraph-powered multi-agent system** that takes a natural language coding task and autonomously plans, generates, executes, debugs, and delivers a working FastAPI application — all without human intervention.

---

## 📌 Table of Contents

- [Project Overview](#-project-overview)
- [System Architecture](#-system-architecture)
- [Agent Roles](#-agent-roles)
- [Tech Stack](#-tech-stack)
- [Pipeline Flow](#-pipeline-flow)
- [Project Structure](#-project-structure)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Setup & Installation](#-setup--installation)
- [Running the System](#-running-the-system)
- [Key Design Decisions](#-key-design-decisions)
- [Interview Q&A Prep](#-interview-qa-prep)

---

## 🧠 Project Overview

This project implements a **fully autonomous AI engineer** — give it a task like _"Build a sentiment analysis API"_ and it will:

1. **Plan** a set of ordered implementation steps
2. **Write** Python code for each step
3. **Execute** the code in a sandboxed subprocess
4. **Debug** any errors automatically (up to 3 retries)
5. **Assemble** all step files into one complete, runnable FastAPI app
6. **Test** the assembled API end-to-end (health check + POST endpoint)

The system also ships a second mode: a **Research Pipeline** (Streamlit UI) that can search the web, scrape URLs, write structured research reports, and self-review them.

---

## 🏗 System Architecture

```
                          ┌─────────────────────────────┐
                          │      FastAPI Backend          │
                          │   POST /execute-task          │
                          └────────────┬────────────────-┘
                                       │
                          ┌────────────▼────────────────-┐
                          │     LangGraph Pipeline        │
                          │     (Stateful Graph)          │
                          └────────────┬────────────────-┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │                                                  │
    ┌─────────▼──────┐   ┌──────────┐   ┌──────────────────┐   │
    │   Planner      │──▶│  Coder   │──▶│    Executor      │   │
    │ (LLM chain)    │   │ (LLM)    │   │  (subprocess)    │   │
    └────────────────┘   └──────────┘   └────────┬─────────┘   │
                                                  │             │
                                          success │  error      │
                                                  │      ┌──────▼──────┐
                                         ┌────────▼┐     │  Debugger   │
                                         │  File   │     │  (LLM)      │
                                         │ Writer  │     └──────┬──────┘
                                         └────────┬┘           │
                                                  │    retry ──┘
                                        all done  │
                                         ┌────────▼──────────┐
                                         │    Assembler       │
                                         │  (LLM merge)       │
                                         └────────┬──────────┘
                                                  │
                                         ┌────────▼──────────┐
                                         │   API Tester       │
                                         │  /health + POST    │
                                         └────────┬──────────┘
                                                  │  error
                                         ┌────────▼──────────┐
                                         │  API Debugger      │
                                         └───────────────────┘
```

### State Machine

The pipeline is a **directed graph with conditional edges** — implemented using `langgraph.StateGraph`. Every node reads from and writes to a central `AgentState` (TypedDict), making the data flow explicit and inspectable.

```
Status transitions:
  running  → step_success → (next step or assembler)
  running  → step_error   → debugger → executor (retry)
  success  → END
  api_error → api_debugger → api_test (retry)
  failed    → END
```

---

## 🕵️ Agent Roles

| Agent | File | Responsibility |
|-------|------|----------------|
| **Planner** | `agents.py` | Decomposes user task → ordered JSON array of steps |
| **Coder** | `agents.py` | Writes executable Python for one step (strict rules: no servers, no unavailable libs) |
| **Executor** | `agents.py` + `tools.py` | Runs code in a sandboxed `subprocess`, captures stdout/stderr |
| **Debugger** | `agents.py` | Receives broken code + error → returns fixed code |
| **Critic** | `agents.py` | *(Optional)* Reviews final step code for quality, returns improved version |
| **Assembler** | `agents.py` | Merges all step files into one complete FastAPI app, applies deterministic patches |
| **Test Generator** | `agents.py` | Builds realistic test payloads from the OpenAPI schema (no LLM, no rate limits) |

### Research System Agents (Bonus)
| Agent | Responsibility |
|-------|----------------|
| **Search Agent** | Uses Tavily API to search the web for a research topic |
| **Reader Agent** | Scrapes the most relevant URL for deeper content |
| **Writer Chain** | Synthesizes search + scraped content into a structured report |
| **Critic Chain** | Reviews the report and provides improvement feedback |

---

## 🛠 Tech Stack

| Category | Technology | Why |
|----------|-----------|-----|
| **LLM Provider** | [Groq](https://groq.com) (`llama-3.1-8b-instant`) | Ultra-fast inference, free tier friendly |
| **LLM Framework** | [LangChain](https://python.langchain.com/) | Prompt templates, output parsers, tool wrappers |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Stateful directed graph; conditional edges for retry logic |
| **API Backend** | [FastAPI](https://fastapi.tiangolo.com/) | Async, auto-docs (Swagger/ReDoc), Pydantic validation |
| **Data Validation** | [Pydantic v2](https://docs.pydantic.dev/latest/) | Schema enforcement for request/response models |
| **Web Search** | [Tavily API](https://tavily.com/) | AI-optimized search results for research pipeline |
| **Research UI** | [Streamlit](https://streamlit.io/) | Rapid multi-page UI for the research system |
| **Logging** | [Rich](https://github.com/Textualize/rich) | Color-coded, timestamped console output |
| **HTTP** | requests, httpx, aiohttp | Sync/async HTTP for API testing and web scraping |
| **Sandboxed Execution** | Python `subprocess` | Isolated code execution with timeout and stdout/stderr capture |

---

## 🔄 Pipeline Flow

### Coding Pipeline (Detailed)

```
User Task (string)
       │
       ▼
┌─────────────────────────────────────────────┐
│ PLANNER — LLM generates a JSON array:       │
│ ["Step 1: ...", "Step 2: ...", "Step 3:..."]│
└────────────────────┬────────────────────────┘
                     │  (loops per step)
                     ▼
┌─────────────────────────────────────────────┐
│ CODER — LLM writes Python for this step     │
│ Rules: no blocking servers, no unavailable  │
│ libraries, must end with print()            │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│ EXECUTOR — subprocess.run(python -c <code>) │
│ Returns: STATUS + STDOUT + STDERR           │
└─────────┬───────────────┬───────────────────┘
          │ success       │ error
          ▼               ▼
  ┌───────────────┐  ┌────────────────────────┐
  │ FILE WRITER   │  │ DEBUGGER (up to 3x)    │
  │ Saves step_N  │  │ LLM fixes the code     │
  │ .py to disk   │  │ → back to EXECUTOR     │
  └───────┬───────┘  └────────────────────────┘
          │
          │  (all steps done)
          ▼
┌─────────────────────────────────────────────┐
│ ASSEMBLER — LLM merges step files into      │
│ one complete generated/app.py               │
│ + deterministic post-assembly patches       │
└────────────────────┬────────────────────────┘
                     ▼
┌─────────────────────────────────────────────┐
│ API TESTER — starts uvicorn on port 9000    │
│ 1. Polls GET /health (max 20s)              │
│ 2. Reads /openapi.json → finds POST route   │
│ 3. Generates payload from schema            │
│ 4. Calls POST endpoint, validates 200 OK    │
│ 5. Shuts down server                        │
└─────────────────────────────────────────────┘
```

### Research Pipeline

```
Topic (string)
     │
     ▼
Search Agent  → Tavily web search → raw search results
     │
     ▼
Reader Agent  → picks top URL → scrapes full content (BeautifulSoup)
     │
     ▼
Writer Chain  → synthesizes report from search + scraped content
     │
     ▼
Critic Chain  → reviews & provides feedback on the report
     │
     ▼
Final Report (dict: report + feedback)
```

---

## 📁 Project Structure

```
Multi-agent-research-system-main/
│
├── app.py                  # FastAPI backend (POST /execute-task, GET /health, /files)
├── pipeline.py             # LangGraph orchestrator — builds & runs the agent graph
├── agents.py               # All 7 agents as pure functions (Planner, Coder, Executor,
│                           #   Debugger, Critic, Assembler, TestPayloadGenerator)
├── state.py                # AgentState TypedDict — central shared state schema
├── tools.py                # LangChain @tools: run_python_code, write_file, read_file, log_output
├── config.py               # Centralized config: MODEL_NAME, MAX_RETRIES, EXEC_TIMEOUT, etc.
├── logger.py               # Rich-powered structured logger with log_step/log_error/log_success
│
├── search_agents.py        # Research system: Search, Reader, Writer, Critic agents
├── search_pipeline.py      # Research pipeline orchestrator (4-step sequential)
├── search_tools.py         # Tavily search + BeautifulSoup URL scraper tools
├── search_app.py           # Streamlit UI for the research system
│
├── engineer_app.py         # Extended Streamlit UI for the coding pipeline
├── run_pipeline_worker.py  # Background worker for async pipeline execution
│
├── requirements.txt        # All dependencies (pinned versions)
├── .env                    # API keys (GROQ_API_KEY, TAVILY_API_KEY)
└── generated/              # Output directory — step files + assembled app.py
```

---

## ⚙️ Configuration

All tunable parameters live in `config.py` — no magic numbers scattered in code.

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `llama-3.1-8b-instant` | Groq model (override via env var) |
| `LLM_TEMPERATURE` | `0.0` | Deterministic code generation |
| `MAX_RETRIES` | `3` | Max step-level debug retries |
| `ENABLE_CRITIC` | `false` | Toggle optional Critic agent |
| `EXEC_TIMEOUT` | `30` | Subprocess execution timeout (seconds) |
| `TEST_PORT` | `9000` | Port for API integration testing |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

Override any value via environment variable:
```bash
MODEL_NAME=llama-3.3-70b-versatile MAX_RETRIES=5 uvicorn app:app --port 8000
```

---

## 📡 API Reference

### `POST /execute-task`
Run the full autonomous coding pipeline.

**Request body:**
```json
{
  "task": "Build a sentiment analysis API using FastAPI",
  "enable_critic": false
}
```

**Response:**
```json
{
  "status": "success",
  "task": "Build a sentiment analysis API using FastAPI",
  "plan": ["Define FastAPI app skeleton", "Implement sentiment logic", "Add POST endpoint"],
  "generated_files": ["/path/generated/step_1_define_a_fastapi.py", "..."],
  "outputs": ["Step 1 complete", "Step 2 complete"],
  "errors": [],
  "logs": ["[12:00:01] [PLANNER] Plan created with 3 steps", "..."]
}
```

### `GET /health`
Liveness probe — returns 200 if the service is up.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "generated_dir": "/abs/path/generated",
  "files_on_disk": 5
}
```

### `GET /files`
List all generated `.py` files.

### `GET /files/{filename}`
Download a specific generated file.

> Full interactive docs available at **`http://localhost:8000/docs`** (Swagger UI)

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- `GROQ_API_KEY` — free at [console.groq.com](https://console.groq.com)
- `TAVILY_API_KEY` — free at [tavily.com](https://tavily.com) (for research mode)

### 1. Clone and enter the project
```bash
git clone <repo-url>
cd Multi-agent-research-system-main
```

### 2. Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API keys
Create a `.env` file:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx
```

---

## ▶️ Running the System

### Coding Pipeline — FastAPI Backend
```bash
uvicorn app:app --reload --port 8000
```
- Swagger UI → http://localhost:8000/docs
- Health check → http://localhost:8000/health

### Research System — Streamlit UI
```bash
streamlit run search_app.py
```

### CLI Quick Test (no server needed)
```bash
python pipeline.py
# Prompts: Enter your coding task:
```

---

## 🧩 Key Design Decisions

### 1. Separation of Concerns
- **`agents.py`** — pure agent functions (no graph awareness)
- **`pipeline.py`** — graph topology and node wiring only
- **`tools.py`** — executable capabilities (LangChain `@tool`)
- **`state.py`** — single TypedDict, single source of truth

This makes each layer independently testable and replaceable.

### 2. Stateful Graph with TypedDict
`AgentState` is a flat `TypedDict` passed through every node. Nodes return **partial dicts** — LangGraph merges them into the state. This avoids mutation bugs and makes state transitions explicit.

### 3. Deterministic Post-Assembly Patching
After every LLM assembly call, `_patch_app_code()` programmatically fixes known LLM failure modes:
- Injects `/health` endpoint if missing
- Removes `text = preprocess_text(text)` inside POST handlers (causes sentence-splitting to fail)
- Replaces naive `text.split('. ')` with regex-based sentence splitting

This is **much more reliable** than prompt engineering alone.

### 4. Schema-Driven Test Payload Generation (No LLM)
Instead of asking the LLM to generate test inputs (slow, rate-limited), the system reads the live `/openapi.json` from the running app, extracts field names, resolves `$ref` + `anyOf` patterns, and maps them to realistic values from a pre-built dictionary. Fast and deterministic.

### 5. Prompt Engineering for Code Safety
The Coder and Debugger prompts explicitly list:
- **Forbidden libraries** (numpy, torch, nltk, etc.) — the pipeline environment doesn't have them
- **Forbidden patterns** — `uvicorn.run()`, blocking servers
- **Required replacements** — pure-Python NLP, `eval()` with safe math namespace for expressions
- **Required ending** — every snippet must end with `print()`

### 6. Security: Path Traversal Prevention
The file download endpoint strips directory components from user-supplied filenames:
```python
safe_name = Path(filename).name  # prevents ../../etc/passwd attacks
```

---


## 📊 Example Output

```
🤖 Enter your coding task: Build a text summarization API

[12:00:01] [PLANNER] Plan created with 3 steps
[12:00:02] [CODER]   Code generated for step 1 (18 lines)
[12:00:03] [EXECUTOR] ✓ Step 1 executed successfully
[12:00:03] [FILE_WRITER] ✓ Step 1 complete → saved as step_1_define_a_fastapi.py
[12:00:04] [CODER]   Code generated for step 2 (22 lines)
[12:00:05] [EXECUTOR] ✓ Step 2 executed successfully
[12:00:07] [ASSEMBLER] ✓ Assembly complete (68 lines)
[12:00:08] [API_TESTER] ✓ Server is up on port 9000
[12:00:09] [API_TESTER] ✓ API test PASSED — /summarize returned: {"summary": "AI is transforming..."}

STATUS: success
FILES:  [generated/step_1_*.py, generated/step_2_*.py, generated/app.py]
```

---

## 🔑 Environment Variables Reference

```env
# Required
GROQ_API_KEY=gsk_...          # LLM API key (Groq)
TAVILY_API_KEY=tvly-...        # Web search (research mode only)

# Optional overrides
MODEL_NAME=llama-3.1-8b-instant
MAX_RETRIES=3
ENABLE_CRITIC=false
EXEC_TIMEOUT=30
TEST_PORT=9000
LOG_LEVEL=INFO
```

---


