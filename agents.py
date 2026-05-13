"""
agents.py — The five specialized AI agents of the Autonomous AI Engineer.

Each agent is a focused LangChain chain (prompt → LLM → parser). They are
called as pure functions by the LangGraph pipeline nodes in pipeline.py —
keeping orchestration (pipeline.py) cleanly separated from agent logic (here).

Agents:
  1. PlannerAgent   — breaks a task into ordered steps
  2. CoderAgent     — writes Python code for a given step
  3. ExecutorAgent  — runs code via the run_python_code tool
  4. DebuggerAgent  — fixes code given execution errors
  5. CriticAgent    — (optional) reviews finished code for quality
"""

import json
import re
import time
from typing import Tuple

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from groq import APIStatusError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

from config import MODEL_NAME, LLM_TEMPERATURE
from tools import run_python_code
from logger import log_step, log_error, log_success

load_dotenv()

# ── Shared LLM instance ───────────────────────────────────────────────────────
# Single ChatGroq instance; all agents share it — no wasted connections.
_llm = ChatGroq(model=MODEL_NAME, temperature=LLM_TEMPERATURE)

# ── Rate-limit retry wrapper ──────────────────────────────────────────────────
# Groq free tier: 8000 TPM. Large prompts can hit this in a single call.
# This wrapper catches 413 rate-limit errors and retries after a backoff.
def _is_rate_limit(exc: BaseException) -> bool:
    return isinstance(exc, APIStatusError) and exc.status_code == 413

def _invoke_with_retry(chain, inputs: dict, label: str = "llm"):
    """Invoke a LangChain chain with automatic retry on Groq 413 rate-limit errors."""
    for attempt in range(1, 6):
        try:
            return chain.invoke(inputs)
        except APIStatusError as e:
            if e.status_code == 413 and attempt < 6:
                wait = 15 * attempt  # 15s, 30s, 45s, 60s, 75s
                log_step(label, f"Rate limit hit (413). Waiting {wait}s before retry {attempt}/5...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"{label}: exceeded rate-limit retries")


# ─────────────────────────────────────────────────────────────────────────────
# 1. PLANNER AGENT
# ─────────────────────────────────────────────────────────────────────────────

_planner_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior software architect and project planner.
Your job is to break a coding task into a clear, ordered sequence of concrete implementation steps.

Rules:
- Return ONLY a valid JSON array of strings — no markdown, no explanation, no code fences.
- Each step must be a single, actionable task (e.g. "Define a FastAPI app with a /health endpoint").
- Steps must be ordered so each one builds on the previous.
- Aim for 3 to 6 steps. Never return fewer than 2 or more than 8.
- Steps must be specific enough that a junior developer can write code for each one independently.
- NEVER include steps like "install packages", "run the server", or "start the application".
- Steps should define and demonstrate functionality using print() — not launch servers.

Example output:
["Define a FastAPI app skeleton with a /health endpoint that prints its route", "Define a Pydantic request model for text input", "Implement a basic keyword-based sentiment function and print example results"]
""",
    ),
    (
        "human",
        "Task: {task}\n\nReturn the JSON array of steps:",
    ),
])

_planner_chain = _planner_prompt | _llm | StrOutputParser()


def run_planner(task: str) -> list[str]:
    """
    Call the Planner agent to decompose `task` into an ordered list of steps.

    Returns:
        A list of step strings. Falls back to a single-step list on parse failure.
    """
    log_step("planner", f"Planning task: {task[:80]}")
    raw = _invoke_with_retry(_planner_chain, {"task": task}, "planner")

    # Strip markdown code fences if the model wraps output anyway
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        steps = json.loads(cleaned)
        if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
            log_success("planner", f"Produced {len(steps)} steps")
            return steps
    except json.JSONDecodeError:
        pass

    # Graceful fallback — single-step plan so the pipeline can still continue
    log_error("planner", f"Could not parse JSON plan. Raw output: {raw[:200]}")
    return [f"Implement the full task: {task}"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. CODER AGENT
# ─────────────────────────────────────────────────────────────────────────────

_coder_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert Python engineer. Write clean, production-quality Python code.

CRITICAL RULES — violating any one of these will cause execution failure:
1. Return ONLY raw Python code — no markdown, no code fences (no ```python), no explanation.
2. The code must be immediately executable with `python -c "<code>"`.
3. NEVER call uvicorn.run(), app.run(), or any BLOCKING server startup command.
   The app is launched externally after all steps are assembled. Just define the
   functions/classes and end with a print() confirmation.
4. IMPORTANT — step code runs in a lightweight pipeline environment. These libraries
   are NOT installed and will cause ModuleNotFoundError if you import them:
     nltk, textblob, spacy, transformers, torch, tensorflow, sklearn,
     scipy, numpy, pandas, cv2, PIL, openai, anthropic, huggingface_hub,
     sentence_transformers, keras, gensim.
   The ONLY available third-party packages are:
     fastapi, uvicorn, pydantic, requests, aiohttp, langchain, langchain_core,
     langchain_groq, langgraph, rich, orjson, tenacity, beautifulsoup4, bs4,
     tiktoken, python-dotenv, and all Python stdlib modules.
5. For ANY NLP task (sentiment, tokenization, keywords, etc.) use pure Python:
   - Sentiment  → keyword lists (POSITIVE/NEGATIVE word lists)
   - Tokenize   → text.split() or re.findall(r'\\w+', text)
   - Keywords   → sort words by frequency using collections.Counter
   - Similarity → character overlap or Jaccard similarity with sets
6. For ANY math / calculator / expression evaluation task:
   - NEVER call float(expression_string) — it only works on plain numbers like "3.14".
   - For evaluating expressions like "10 + 5 * 2" or "sqrt(16)", use eval() with a
     safe math namespace:
       import math
       _MATH_NS = {{k: getattr(math, k) for k in dir(math) if not k.startswith('_')}}
       _MATH_NS['abs'] = abs
       result = eval(expression, {{"__builtins__": {{}}}}, _MATH_NS)
   - This handles: +, -, *, /, **, sqrt, sin, cos, log, pi, e, floor, ceil, etc.
7. Always end with a print() statement confirming the step completed.
8. Keep the code focused on the single step — do not implement other steps.

EXAMPLE — safe math expression evaluator:
  import math
  _NS = {{k: getattr(math, k) for k in dir(math) if not k.startswith('_')}}
  _NS['abs'] = abs
  def evaluate(expr: str) -> float:
      return eval(expr, {{"__builtins__": {{}}}}, _NS)
  print(evaluate("sqrt(16) + 10 * 2"))   # → 24.0

EXAMPLE — keyword extraction with NO external libraries:
  import re
  from collections import Counter
  STOPWORDS = {{'the','a','an','is','in','of','and','to','for','it','this','with'}}
  def extract_keywords(text: str, top_n: int = 5) -> list:
      words = re.findall(r'\\b[a-z]{{3,}}\\b', text.lower())
      freq = Counter(w for w in words if w not in STOPWORDS)
      return [w for w, _ in freq.most_common(top_n)]
  print(extract_keywords("machine learning is transforming the world of AI"))
""",
    ),
    (
        "human",
        """Overall Task: {task}

Current Step to Implement:
{step}

Write pure Python code for this step only. NO blocking server startup. Use only stdlib + the approved packages. End with print():""",
    ),
])

_coder_chain = _coder_prompt | _llm | StrOutputParser()


def run_coder(task: str, step: str) -> str:
    """
    Call the Coder agent to generate Python code for a single `step`.

    Returns:
        A string of executable Python code.
    """
    log_step("coder", f"Writing code for: {step[:80]}")
    code = _invoke_with_retry(_coder_chain, {"task": task, "step": step}, "coder")

    # Strip any accidental markdown fences the model may still add
    code = re.sub(r"^```(?:python)?\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code.strip())

    log_success("coder", f"Generated {len(code.splitlines())} lines of code")
    return code.strip()


# ─────────────────────────────────────────────────────────────────────────────
# 3. EXECUTOR AGENT
# ─────────────────────────────────────────────────────────────────────────────

def run_executor(code: str) -> Tuple[str, str, bool]:
    """
    Execute code in a subprocess. Returns (stdout, stderr, success).
    """
    log_step("executor", "Executing generated code...")

    raw_output: str = run_python_code.invoke({"code": code})

    status_line = ""
    stdout_section = ""
    stderr_section = ""

    lines = raw_output.splitlines()
    current_section = None

    for line in lines:
        if line.startswith("STATUS:"):
            status_line = line.split(":", 1)[1].strip()
        elif line.startswith("STDOUT:"):
            current_section = "stdout"
        elif line.startswith("STDERR:"):
            current_section = "stderr"
        elif current_section == "stdout":
            stdout_section += line + "\n"
        elif current_section == "stderr":
            stderr_section += line + "\n"

    success = (status_line == "success")

    if success:
        log_success("executor", "Code executed successfully")
    else:
        err = stderr_section.strip()
        # Surface import errors clearly for the debugger
        if "ModuleNotFoundError" in err:
            mod_line = next((l for l in err.splitlines() if "ModuleNotFoundError" in l), err)
            log_error("executor", f"Execution failed. Error: {mod_line[:150]}")
        else:
            log_error("executor", f"Execution failed. Error: {err[:200]}")

    return stdout_section.strip(), stderr_section.strip(), success


# ─────────────────────────────────────────────────────────────────────────────
# 4. DEBUGGER AGENT
# ─────────────────────────────────────────────────────────────────────────────

_debugger_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert Python debugger. You receive broken code and its error output,
and you return a corrected, working version of the code.

CRITICAL RULES:
- Return ONLY the fixed Python code — no markdown, no code fences, no explanation.
- Preserve the original intent of the code; only fix what is broken.
- The fixed code must be immediately executable with `python -c "<code>"`.
- NEVER call uvicorn.run(), app.run(), or any blocking server startup command.
- If the error is ModuleNotFoundError: the library is not installed in the step
  execution environment. Replace it with a pure-Python equivalent:
    * Sentiment (nltk/textblob) → keyword list approach
    * Vectors (numpy/torch)    → plain Python list/dict
    * HTTP (requests error)    → check import or mock data
- If the error is ValueError: could not convert string to float: '<expression>'
  the code is calling float() on a math expression string. Fix by using eval()
  with a safe math namespace instead:
    import math
    _MATH_NS = {{k: getattr(math, k) for k in dir(math) if not k.startswith('_')}}
    _MATH_NS['abs'] = abs
    result = eval(expression, {{"__builtins__": {{}}}}, _MATH_NS)
  This handles sqrt(), sin(), cos(), log(), pi, **, +, -, *, / etc.
- Always ensure the fixed code ends with a print() statement confirming success.
""",
    ),
    (
        "human",
        """Original code that failed:
{code}

Error output:
{error}

Return the fixed Python code (NO blocking server startup, end with print()):""",
    ),
])


_debugger_chain = _debugger_prompt | _llm | StrOutputParser()


def run_debugger(code: str, error: str) -> str:
    """
    Call the Debugger agent to fix `code` given its `error` output.

    Returns:
        A corrected string of executable Python code.
    """
    log_step("debugger", f"Debugging error: {error[:100]}")
    fixed = _invoke_with_retry(_debugger_chain, {"code": code, "error": error}, "debugger")

    # Strip any accidental markdown fences
    fixed = re.sub(r"^```(?:python)?\n?", "", fixed.strip())
    fixed = re.sub(r"\n?```$", "", fixed.strip())

    log_success("debugger", f"Fixed code produced ({len(fixed.splitlines())} lines)")
    return fixed.strip()


# ─────────────────────────────────────────────────────────────────────────────
# 5. CRITIC AGENT  (optional — enabled via config.ENABLE_CRITIC)
# ─────────────────────────────────────────────────────────────────────────────

_critic_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior Python code reviewer focused on production quality.
Review the code and return an improved version along with a brief review summary.

Output format (strictly):
REVIEW:
<3-5 bullet points on issues / improvements>

IMPROVED_CODE:
<the full improved Python code, no fences>
""",
    ),
    (
        "human",
        """Task context: {task}

Code to review:
{code}

Return your review and improved code:""",
    ),
])

_critic_chain = _critic_prompt | _llm | StrOutputParser()


def run_critic(task: str, code: str) -> Tuple[str, str]:
    """
    Call the Critic agent to review and improve `code`.

    Returns:
        (review_text, improved_code) tuple.
    """
    log_step("critic", "Reviewing code quality...")
    raw = _invoke_with_retry(_critic_chain, {"task": task, "code": code}, "critic")

    # Parse the structured two-section output
    review = ""
    improved_code = code  # fallback: keep original if parse fails

    if "IMPROVED_CODE:" in raw:
        parts = raw.split("IMPROVED_CODE:", 1)
        review_part = parts[0].replace("REVIEW:", "").strip()
        code_part = parts[1].strip()

        # Strip any markdown fences from improved code
        code_part = re.sub(r"^```(?:python)?\n?", "", code_part)
        code_part = re.sub(r"\n?```$", "", code_part).strip()

        review = review_part
        improved_code = code_part
    else:
        review = raw.strip()

    log_success("critic", "Code review complete")
    return review, improved_code


# ─────────────────────────────────────────────────────────────────────────────
# 6. ASSEMBLER AGENT
# ─────────────────────────────────────────────────────────────────────────────

_assembler_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert Python API developer specializing in merging code into complete applications.

You will receive multiple Python code snippets generated for different steps of a task.
Your job: merge them into ONE single, complete, immediately runnable FastAPI application.

CRITICAL RULES:
1. Return ONLY raw Python code — no markdown, no code fences (```), no explanations.
2. Deduplicate ALL imports — each import line must appear only once.
3. Deduplicate ALL class and function definitions — keep the most complete version.
4. The final app MUST contain:
   a) A FastAPI instance called `app`
   b) GET /health  → returns {{"status": "ok"}}
   c) A POST endpoint named after the task (e.g. /summarize, /predict, /calculate)
      that accepts a Pydantic model and returns a meaningful result dict.
5. NEVER call uvicorn.run() — the app is started externally.
6. The merged code must run cleanly with: uvicorn app:app --port 9000
7. Handle edge cases: strip any if __name__ == "__main__": blocks from step code.
8. End with: print("App assembled and ready — FastAPI running")

DATA-FLOW RULES — critical for correctness:
- Think carefully about the ORDER in which helper functions are called.
- NEVER pass text through a punctuation-stripping or lowercasing function BEFORE
  you perform sentence splitting. Sentence splitters rely on ". " or "!" or "?"
  boundaries — if you strip punctuation first, splitting breaks completely.
- Correct order for NLP tasks:
    1. Split into sentences (on raw, original text)
    2. Extract keywords (on cleaned/lowercased copy)
    3. Rank / filter sentences using those keywords
    4. Return the top N sentences in their original order
- For math/expression tasks: validate input → compute → return result.
- For classification tasks: extract features → classify → return label + confidence.
""",
    ),
    (
        "human",
        """Task: {task}

Code snippets from all generated steps:

{code_snippets}

Merge into ONE complete FastAPI app. Pay special attention to the DATA FLOW order between helper functions. Return only Python code:""",
    ),
])

_assembler_chain = _assembler_prompt | _llm | StrOutputParser()


def _patch_app_code(code: str) -> str:
    """
    Programmatically fix common LLM assembly mistakes — runs after every
    assembler call so the saved app.py is always correct.

    Fixes applied:
      1. Inject GET /health if the LLM forgot to include it.
      2. Remove "text = preprocess_text(text)" lines from POST endpoint bodies
         (stripping punctuation before sentence splitting removes boundaries).
      3. Replace text.split('. ') / text_no_punct.split('. ') with proper
         regex-based sentence splitting on .!? boundaries.
    """
    # ── 1. Ensure /health endpoint exists ─────────────────────────────────
    if '"/health"' not in code and "'/health'" not in code:
        health_snippet = (
            '\n@app.get("/health")\n'
            'async def health():\n'
            '    return {"status": "ok"}\n'
        )
        # Insert before first POST endpoint; fall back to before trailing print
        if '@app.post' in code:
            idx = code.index('@app.post')
        elif 'print(' in code:
            idx = code.rindex('print(')
        else:
            idx = len(code)
        code = code[:idx] + health_snippet + '\n' + code[idx:]

    # ── 2. Remove in-endpoint "text = preprocess_text(text)" assignments ──
    # This bad pattern strips all punctuation before sentence splitting,
    # making split('. ') find zero boundaries and returning the full text.
    lines = code.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Match assignments like: text = preprocess_text(text)
        #                          text = preprocess_text(request.text)
        if (
            stripped.startswith('text = preprocess_text(')
            or stripped.startswith('text = _preprocess_text(')
            or stripped.startswith('text_no_punct = preprocess_text(')
            or stripped.startswith('text_no_punct = _preprocess_text(')
        ):
            # Replace with a comment explaining why it's skipped
            indent = line[:len(line) - len(line.lstrip())]
            cleaned.append(
                f"{indent}# preprocessing kept inside helpers — raw text used for sentence splitting"
            )
        else:
            cleaned.append(line)
    code = '\n'.join(cleaned)

    # ── 3. Fix sentence splitting: replace naive period split with regex ───
    bad_splits = [
        "text.split('. ')",
        "text_no_punct.split('. ')",
        "text.split(\". \")",
        "text_no_punct.split(\". \")",
    ]
    good_split = "__import__('re').split(r'(?<=[.!?])\\s+', text)"
    for bad in bad_splits:
        code = code.replace(bad, good_split)

    return code


def run_assembler(task: str, code_snippets: str) -> str:
    """
    Call the Assembler agent to merge all step code snippets into one
    complete, runnable FastAPI application, then apply post-assembly patches.
    """
    log_step("assembler", "Merging all step code into one FastAPI app...")
    raw = _invoke_with_retry(_assembler_chain, {"task": task, "code_snippets": code_snippets}, "assembler")
    raw = re.sub(r"^```(?:python)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip()).strip()

    # Apply deterministic fixes regardless of what the LLM produced
    raw = _patch_app_code(raw)

    log_success("assembler", f"Assembly complete ({len(raw.splitlines())} lines)")
    return raw



# ─────────────────────────────────────────────────────────────────────────────
# 7. TEST CASE GENERATOR  (deterministic — no LLM, no rate limits)
# ─────────────────────────────────────────────────────────────────────────────

# Field name (lowercase) → realistic sample value.
# This covers the most common FastAPI field naming patterns.
_FIELD_VALUES: dict = {
    # ── Text / NLP ──────────────────────────────────────────────────────────
    "text":             "I absolutely love this new product!",
    "texts":            ["I love this!", "This is terrible."],
    "message":          "Hello, this is a test message",
    "content":          "Sample content for API testing",
    "query":            "What is machine learning?",
    "sentence":         "The quick brown fox jumps over the lazy dog",
    "document":         "This is a sample document for text processing.",
    "paragraph":        "Artificial intelligence is transforming industries worldwide.",
    "body":             "This is the body of the request for testing purposes.",
    "prompt":           "Write a short poem about mountains",
    "input_text":       "Sample input text for the API",
    "raw_text":         "This is raw text input for processing",

    # ── Task / Project management ────────────────────────────────────────────
    "title":            "Fix the login bug",
    "description":      "Users cannot log in with Google OAuth — needs immediate fix",
    "summary":          "Brief summary of the item",
    "name":             "Sample Name",
    "label":            "category-a",
    "tag":              "urgent",
    "priority":         "high",
    "status":           "pending",

    # ── Math / Calculator ────────────────────────────────────────────────────
    "expression":       "2 + 2 * 10",
    "formula":          "x^2 + 3*x - 5",
    "equation":         "3*x + 2 = 11",
    "operation":        "add",
    "operator":         "+",
    "num1":             10,
    "num2":             5,
    "number1":          10,
    "number2":          5,
    "operand1":         10,
    "operand2":         5,
    "operand_a":        10,
    "operand_b":        5,
    "a":                10,
    "b":                5,
    "x":                10,
    "y":                5,
    "n":                7,
    "k":                3,
    "base":             2,
    "exponent":         8,
    "dividend":         100,
    "divisor":          4,
    "numerator":        7,
    "denominator":      3,

    # ── Numbers / scalars ────────────────────────────────────────────────────
    "number":           42,
    "value":            42,
    "amount":           99.99,
    "price":            29.99,
    "score":            0.87,
    "rate":             0.05,
    "count":            5,
    "limit":            10,
    "page":             1,
    "size":             20,
    "id":               1,
    "age":              25,
    "year":             2024,
    "month":            4,
    "day":              15,
    "quantity":         3,

    # ── User / Auth ──────────────────────────────────────────────────────────
    "username":         "john_doe",
    "email":            "test@example.com",
    "password":         "TestPassword123!",
    "first_name":       "John",
    "last_name":        "Doe",
    "full_name":        "John Doe",
    "phone":            "+1-555-123-4567",
    "token":            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example",
    "api_key":          "test-api-key-abc123",

    # ── Location ─────────────────────────────────────────────────────────────
    "city":             "London",
    "country":          "United Kingdom",
    "country_code":     "GB",
    "address":          "221B Baker Street, London",
    "zip_code":         "NW1 6XE",
    "latitude":         51.5074,
    "longitude":        -0.1278,

    # ── Language / Translation ───────────────────────────────────────────────
    "language":         "English",
    "target_language":  "French",
    "source_language":  "English",
    "lang":             "en",
    "target_lang":      "fr",

    # ── Media / Files ────────────────────────────────────────────────────────
    "url":              "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg",
    "image_url":        "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg",
    "file_url":         "https://example.com/sample.pdf",
    "filename":         "sample_file.txt",

    # ── Code / Programming ───────────────────────────────────────────────────
    "code":             "def hello():\n    return 'Hello World'",
    "snippet":          "print('Hello World')",
    "program":          "x = 5\nprint(x * 2)",

    # ── Generic ──────────────────────────────────────────────────────────────
    "input":            "sample input",
    "data":             "sample data",
    "payload":          "sample payload",
    "question":         "What is the capital of France?",
    "answer":           "Paris",
    "keyword":          "machine learning",
    "category":         "technology",
    "type":             "standard",
    "mode":             "fast",
    "format":           "json",
}


def _infer_type(info: dict) -> str:
    """
    Extract the actual type string from a field schema dict,
    handling FastAPI's anyOf pattern used for Optional fields.

    e.g. {"anyOf": [{"type": "number"}, {"type": "null"}]} => "number"
    """
    if "type" in info:
        return info["type"]
    # FastAPI Optional[X] pattern
    for sub in info.get("anyOf", []):
        t = sub.get("type")
        if t and t != "null":
            return t
    return "string"


# Task keyword → fallback payload — only used if schema has NO recognisable fields
_TASK_FALLBACKS: list = [
    (["sentiment", "emotion", "opinion"],                  {"text": "I absolutely love this product!"}),
    (["translate", "translation"],                         {"text": "Hello, how are you?", "target_language": "French"}),
    (["embed", "vector", "embedding", "encode"],           {"text": "The quick brown fox jumps over the lazy dog"}),
    (["todo", "task manager", "reminder", "checklist"],    {"title": "Fix login bug", "description": "OAuth users can't sign in"}),
    (["weather", "forecast", "temperature"],               {"city": "London"}),
    (["calculator", "math", "arithmetic", "compute"],      {"num1": 10, "num2": 5, "operator": "+"}),
    (["image", "caption", "vision", "photo"],              {"url": "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg"}),
    (["summarize", "summary", "abstract"],                 {"text": "Artificial intelligence is transforming every industry in the world."}),
    (["chat", "question", "answer", "qa"],                 {"question": "What is the capital of France?"}),
]


def _resolve_schema(schema: dict, components: dict) -> dict:
    """Resolve a $ref schema reference into a concrete schema dict."""
    if "$ref" in schema:
        ref_path = schema["$ref"]  # e.g. "#/components/schemas/SentimentRequest"
        parts = ref_path.lstrip("#/").split("/")
        resolved = components
        for part in parts:
            resolved = resolved.get(part, {})
        return resolved
    return schema


def generate_test_payload(task: str, endpoint: str, openapi_json: dict) -> dict:
    """
    Build a realistic test payload for the POST endpoint using the live
    OpenAPI schema — no LLM call, no rate limits, instant.

    Strategy (in priority order):
      1. Read actual field names from /openapi.json (resolves $ref + anyOf)
      2. Map each field name to a meaningful value via _FIELD_VALUES
      3. For unknown fields: infer from type (int→42, bool→True, etc.)
      4. Task-keyword fallback if schema has no useful fields
      5. Last resort: {"input": "sample input"}
    """
    log_step("test_gen", f"Building test payload for {endpoint} from schema...")

    try:
        components = openapi_json.get("components", {})
        path_data  = openapi_json.get("paths", {}).get(endpoint, {})
        post_data  = path_data.get("post", {})

        raw_schema = (
            post_data
            .get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )

        schema = _resolve_schema(raw_schema, components)
        props  = schema.get("properties", {})

        if props:
            payload = {}
            for field, info in props.items():
                key = field.lower()

                # 1. Exact name match
                if key in _FIELD_VALUES:
                    payload[field] = _FIELD_VALUES[key]
                    continue

                # 2. Partial / substring match (e.g. "input_text" matches "text")
                matched = None
                for pattern, val in _FIELD_VALUES.items():
                    if pattern in key or key in pattern:
                        matched = val
                        break
                if matched is not None:
                    payload[field] = matched
                    continue

                # 3. Type-based value (handles anyOf / Optional from FastAPI)
                ftype = _infer_type(info)
                if ftype in ("integer", "number"):
                    payload[field] = 42
                elif ftype == "boolean":
                    payload[field] = True
                elif ftype == "array":
                    payload[field] = []
                elif ftype == "object":
                    payload[field] = {}
                else:
                    payload[field] = f"sample {field}"

            if payload:
                log_success("test_gen", f"Schema-derived payload: {payload}")
                return payload

    except Exception as exc:
        log_error("test_gen", f"Schema parse error: {exc}")

    # ── Task-keyword fallback (schema was empty / unresolvable) ───────────
    task_lower = task.lower()
    for keywords, fallback in _TASK_FALLBACKS:
        if any(kw in task_lower for kw in keywords):
            log_success("test_gen", f"Task-inferred payload: {fallback}")
            return fallback

    default = {"input": "sample input"}
    log_step("test_gen", f"Using default payload: {default}")
    return default
