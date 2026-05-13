"""
engineer_app.py — Streamlit UI for the Autonomous AI Engineer (v2).

Shows 7 pipeline steps including the Assembler and API Tester agents.
Displays: plan, per-file code tabs, test result JSON, execution log.
"""

import sys
import time
import json
import subprocess
import requests as req
import streamlit as st
from typing import Optional
from pathlib import Path
from pipeline import run_pipeline
from agents import generate_test_payload
from config import GENERATED_DIR, TEST_PORT

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Autonomous AI Engineer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&family=Inter:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #e2e8f0; }

.stApp {
    background: #080c14;
    background-image:
        radial-gradient(ellipse 70% 45% at 10% -5%,  rgba(99,102,241,0.13) 0%, transparent 55%),
        radial-gradient(ellipse 55% 35% at 90% 105%, rgba(16,185,129,0.08) 0%, transparent 50%);
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 3rem 4rem; max-width: 1280px; }

.hero { text-align: center; padding: 3rem 0 2rem; }
.hero-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; letter-spacing: 0.22em; text-transform: uppercase;
    color: #818cf8; border: 1px solid rgba(99,102,241,0.35);
    border-radius: 999px; padding: 0.3rem 0.9rem; margin-bottom: 1.2rem;
}
.hero h1 {
    font-family: 'Syne', sans-serif;
    font-size: clamp(2.6rem, 5.5vw, 4.6rem); font-weight: 800;
    line-height: 1.05; letter-spacing: -0.03em; color: #f1f5f9; margin: 0 0 0.9rem;
}
.hero h1 em { font-style: normal; color: #818cf8; }
.hero-sub { font-size: 1rem; color: #64748b; max-width: 520px; margin: 0 auto; line-height: 1.7; }
.divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(99,102,241,0.25), transparent); margin: 2rem 0; }

.input-card {
    background: rgba(255,255,255,0.025); border: 1px solid rgba(99,102,241,0.18);
    border-radius: 16px; padding: 1.8rem 2.2rem 2rem; margin-bottom: 1.5rem;
}

.stTextArea textarea {
    background: rgba(255,255,255,0.04) !important; border: 1px solid rgba(99,102,241,0.28) !important;
    border-radius: 10px !important; color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.96rem !important;
    transition: border-color 0.2s !important; resize: none !important;
}
.stTextArea textarea:focus { border-color: #818cf8 !important; box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important; }
.stTextArea label {
    font-family: 'JetBrains Mono', monospace !important; font-size: 0.68rem !important;
    letter-spacing: 0.16em !important; text-transform: uppercase !important;
    color: #818cf8 !important; font-weight: 500 !important;
}

.stButton > button {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    color: #fff !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; font-size: 0.95rem !important; border: none !important;
    border-radius: 10px !important; padding: 0.75rem 2rem !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
    transition: transform 0.15s, box-shadow 0.15s !important; width: 100%;
}
.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 30px rgba(99,102,241,0.45) !important; }

.step-card {
    background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px; padding: 0.95rem 1.4rem; margin-bottom: 0.65rem;
    position: relative; overflow: hidden;
}
.step-card::before {
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    border-radius: 12px 0 0 12px; background: rgba(255,255,255,0.06);
}
.step-card.waiting::before  { background: rgba(255,255,255,0.06); }
.step-card.running::before  { background: #818cf8; }
.step-card.success::before  { background: #10b981; }
.step-card.error::before    { background: #f43f5e; }
.step-card.running { border-color: rgba(99,102,241,0.35); background: rgba(99,102,241,0.05); }
.step-card.success { border-color: rgba(16,185,129,0.3);  background: rgba(16,185,129,0.04); }
.step-card.error   { border-color: rgba(244,63,94,0.3);   background: rgba(244,63,94,0.04); }

.step-header { display: flex; align-items: center; gap: 0.6rem; }
.step-num { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; letter-spacing: 0.15em; color: #818cf8; opacity: 0.65; }
.step-title { font-family: 'Syne', sans-serif; font-size: 0.85rem; font-weight: 700; color: #e2e8f0; }
.step-badge { margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 0.58rem; letter-spacing: 0.09em; padding: 0.16rem 0.45rem; border-radius: 4px; }
.badge-waiting { color: #475569; background: rgba(71,85,105,0.15); }
.badge-running { color: #818cf8; background: rgba(99,102,241,0.15); }
.badge-success { color: #10b981; background: rgba(16,185,129,0.15); }
.badge-error   { color: #f43f5e; background: rgba(244,63,94,0.15); }

.panel { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 1.5rem 1.8rem; margin-bottom: 1.2rem; }
.panel-label { font-family: 'JetBrains Mono', monospace; font-size: 0.64rem; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 1rem; padding-bottom: 0.65rem; border-bottom: 1px solid rgba(255,255,255,0.07); }
.label-purple { color: #818cf8; }
.label-green  { color: #10b981; }
.label-red    { color: #f43f5e; }
.label-slate  { color: #64748b; }
.label-amber  { color: #f59e0b; }

.status-banner { border-radius: 12px; padding: 1rem 1.5rem; font-family: 'Syne', sans-serif; font-size: 1.05rem; font-weight: 700; display: flex; align-items: center; gap: 0.7rem; margin-bottom: 1.5rem; }
.status-success { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: #10b981; }
.status-failed  { background: rgba(244,63,94,0.09); border: 1px solid rgba(244,63,94,0.3);  color: #f43f5e; }

.file-pill { display: inline-block; background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.28); border-radius: 6px; padding: 0.25rem 0.7rem; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #a5b4fc; margin: 0.2rem 0.3rem 0.2rem 0; }
.app-file-pill { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.35); color: #6ee7b7; }

.test-result-box { background: #0d1117; border: 1px solid rgba(16,185,129,0.25); border-radius: 10px; padding: 1.2rem 1.4rem; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #6ee7b7; line-height: 1.7; }
.test-result-box.failed { border-color: rgba(244,63,94,0.3); color: #fca5a5; }

.log-viewer { background: #0d1117; border: 1px solid rgba(255,255,255,0.07); border-radius: 10px; padding: 1rem 1.2rem; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #64748b; max-height: 300px; overflow-y: auto; line-height: 1.8; }
.log-success { color: #10b981; }
.log-error   { color: #f43f5e; }
.log-info    { color: #818cf8; }
.log-amber   { color: #f59e0b; }

.notice { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; color: #1e293b; text-align: center; margin-top: 3rem; letter-spacing: 0.08em; }
.stSpinner > div { color: #818cf8 !important; }
details summary { font-family: 'JetBrains Mono', monospace !important; font-size: 0.7rem !important; color: #475569 !important; cursor: pointer; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def step_card_html(num: str, icon: str, title: str, state: str, desc: str = ""):
    badge_map = {
        "waiting": ("WAITING", "badge-waiting"),
        "running": ("● RUNNING", "badge-running"),
        "success": ("✓ DONE",   "badge-success"),
        "error":   ("✗ ERROR",  "badge-error"),
    }
    label, badge_cls = badge_map.get(state, ("", ""))
    desc_html = f"<div style='font-size:0.75rem;color:#475569;margin-top:0.2rem;'>{desc}</div>" if desc else ""
    st.markdown(f"""
    <div class="step-card {state}">
        <div class="step-header">
            <span class="step-num">{num}</span>
            <span style="font-size:0.95rem;">{icon}</span>
            <span class="step-title">{title}</span>
            <span class="step-badge {badge_cls}">{label}</span>
        </div>
        {desc_html}
    </div>
    """, unsafe_allow_html=True)


def colorize_log(line: str) -> str:
    low = line.lower()
    if "✓" in line or "success" in low or "passed" in low:
        return f'<span class="log-success">{line}</span>'
    if "error" in low or "failed" in low or "✗" in line:
        return f'<span class="log-error">{line}</span>'
    if any(k in low for k in ["assembler", "api_tester", "api_debug"]):
        return f'<span class="log-amber">{line}</span>'
    if any(k in low for k in ["planner", "coder", "pipeline", "executor"]):
        return f'<span class="log-info">{line}</span>'
    return line


PIPELINE_STEPS = [
    ("01", "🗂️", "Planner Agent",   "Breaks task into ordered steps"),
    ("02", "💻", "Coder Agent",      "Generates Python for each step"),
    ("03", "⚙️", "Executor Agent",   "Runs code in sandboxed subprocess"),
    ("04", "🐛", "Debugger Agent",   "Fixes errors & retries (max 3×)"),
    ("05", "💾", "File Writer",      "Saves working step files"),
    ("06", "🔧", "Assembler Agent",  "Merges steps into one app.py"),
]


def render_pipeline_cards(active: int = -1, done: bool = False, failed_at: int = -1):
    for i, (num, icon, title, desc) in enumerate(PIPELINE_STEPS):
        if done and failed_at == -1:
            s = "success"
        elif failed_at >= 0 and i > failed_at:
            s = "waiting"
        elif failed_at >= 0 and i == failed_at:
            s = "error"
        elif failed_at >= 0 and i < failed_at:
            s = "success"
        elif i == active:
            s = "running"
        elif done and i <= active:
            s = "success"
        else:
            s = "waiting"
        step_card_html(num, icon, title, s, desc)


# ── Session state init ────────────────────────────────────────────────────────
for key, default in [("result", None), ("running", False), ("done", False), ("test_result", None), ("payload_draft", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── API Test Helper ───────────────────────────────────────────────────────────

def _free_port(port: int):
    """Kill any process using the port."""
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        pids = result.stdout.strip().split()
        for pid in pids:
            subprocess.run(["kill", "-9", pid], capture_output=True)
        if pids:
            time.sleep(0.5)
    except Exception:
        pass


def run_api_test_inline(task: str, assembled_app_path: str, custom_payload: Optional[dict] = None) -> dict:
    """
    Start the assembled FastAPI app, discover its endpoint+schema,
    POST the payload (custom if provided, otherwise auto-generated), return result.
    """
    _free_port(TEST_PORT)
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app",
             f"--port={TEST_PORT}", "--log-level=error"],
            cwd=str(GENERATED_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Poll until server is up (up to 30 seconds)
        ready = False
        crash_err = ""
        for _ in range(30):
            time.sleep(1)
            # Check if process died
            if proc.poll() is not None:
                crash_err = proc.stderr.read().decode(errors="replace")[:600]
                break
            try:
                # Accept /health → 200 OR any connection (handles missing /health route)
                r = req.get(f"http://127.0.0.1:{TEST_PORT}/health", timeout=2)
                if r.status_code < 500:   # 200 or even 404 means uvicorn is up
                    ready = True
                    break
            except req.exceptions.ConnectionError:
                pass  # still starting
            except Exception:
                pass

        if not ready:
            err = crash_err if crash_err else "Timeout — server did not start in 30s"
            return {"success": False, "error": f"Server failed to start: {err}"}

        # Discover endpoint + full openapi schema
        base     = f"http://127.0.0.1:{TEST_PORT}"
        endpoint = "/predict"
        openapi  = {}
        try:
            openapi = req.get(f"{base}/openapi.json", timeout=5).json()
            for path, methods in openapi.get("paths", {}).items():
                if "post" in methods and path not in ("/", "/health"):
                    endpoint = path
                    break
        except Exception:
            pass

        # Use custom payload if the user edited it; otherwise auto-generate
        payload = custom_payload if custom_payload is not None else generate_test_payload(task, endpoint, openapi)

        # POST to endpoint
        response = req.post(f"{base}{endpoint}", json=payload, timeout=10)
        if response.status_code != 200:
            return {
                "success": False,
                "endpoint": endpoint,
                "payload": payload,
                "error": f"HTTP {response.status_code}: {response.text[:300]}",
            }

        return {
            "success":     True,
            "endpoint":    endpoint,
            "payload":     payload,
            "status_code": response.status_code,
            "response":    response.json(),
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


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-badge">Plan · Code · Run · Test · Deliver</div>
    <h1>Autonomous <em>AI Engineer</em></h1>
    <p class="hero-sub">
        Describe any coding task — seven specialized AI agents will plan, write,
        execute, debug, assemble, launch, and validate a working API automatically.
    </p>
</div>
<div class="divider"></div>
""", unsafe_allow_html=True)


# ── Layout ────────────────────────────────────────────────────────────────────
col_left, col_gap, col_right = st.columns([5, 0.4, 4])

with col_right:
    st.markdown('<div style="font-family:\'Syne\',sans-serif;font-size:1.15rem;font-weight:700;color:#e2e8f0;margin-bottom:1rem;">Pipeline</div>', unsafe_allow_html=True)
    pipeline_placeholder = st.empty()

    with pipeline_placeholder.container():
        render_pipeline_cards()

    log_placeholder = st.empty()

with col_left:
    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    task = st.text_area(
        "Coding Task",
        placeholder='e.g. "Build a REST API for a TODO app using FastAPI"',
        height=110,
        key="task_input",
    )
    run_btn = st.button("⚡  Run Autonomous Pipeline", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <span style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#334155;letter-spacing:0.12em;">TRY →</span><br/>
        <span style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-radius:6px;padding:0.22rem 0.65rem;font-size:0.74rem;color:#94a3b8;margin:0.2rem 0.2rem 0 0;">Build a sentiment analysis API</span>
        <span style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-radius:6px;padding:0.22rem 0.65rem;font-size:0.74rem;color:#94a3b8;margin:0.2rem 0.2rem 0 0;">Build a TODO REST API</span>
        <span style="display:inline-block;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-radius:6px;padding:0.22rem 0.65rem;font-size:0.74rem;color:#94a3b8;margin:0.2rem 0.2rem 0 0;">Build a text summarizer API</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Results ───────────────────────────────────────────────────────────
    r = st.session_state.result
    if r:
        # Status banner
        success = r["status"] == "success"
        files_count = len(r.get("generated_files", []))
        if success:
            st.markdown(f"""<div class="status-banner status-success">
                ✅ Pipeline completed successfully
                <span style="font-weight:400;font-size:0.85rem;">· {files_count} file(s) generated</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="status-banner status-failed">
                ❌ Pipeline ended with errors — see log
            </div>""", unsafe_allow_html=True)

        # API Test Result — removed (feature disabled)

        # Plan
        if r.get("plan"):
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="panel-label label-purple">🗂️ &nbsp;Generated Plan</div>', unsafe_allow_html=True)
            for i, step in enumerate(r["plan"], 1):
                st.markdown(
                    f"<div style='font-size:0.83rem;color:#94a3b8;margin-bottom:0.35rem;'>"
                    f"<span style='color:#818cf8;font-family:JetBrains Mono,monospace;font-size:0.7rem;'>{i:02d} &nbsp;</span>{step}</div>",
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

        # Generated files
        all_files = r.get("generated_files", [])
        if all_files:
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="panel-label label-green">💾 &nbsp;Generated Files</div>', unsafe_allow_html=True)

            pills = ""
            for p in all_files:
                name = p.split("/")[-1]
                cls  = "file-pill app-file-pill" if name in ("app.py", "requirements.txt") else "file-pill"
                pills += f'<span class="{cls}">{name}</span>'
            st.markdown(f"<div style='margin-bottom:1rem;'>{pills}</div>", unsafe_allow_html=True)

            # Tabs — show assembled app.py first, then step files
            ordered = sorted(all_files, key=lambda p: (0 if p.endswith("app.py") else 1, p))
            tabs = st.tabs([p.split("/")[-1] for p in ordered])
            for tab, fpath in zip(tabs, ordered):
                with tab:
                    try:
                        content = open(fpath).read()
                        lang = "python" if fpath.endswith(".py") else "text"
                        st.code(content, language=lang)
                        st.download_button(
                            label="⬇  Download",
                            data=content,
                            file_name=fpath.split("/")[-1],
                            mime="text/plain",
                            key=f"dl_{fpath}",
                        )
                    except Exception:
                        st.warning("File not found on disk.")
            st.markdown('</div>', unsafe_allow_html=True)

        # Errors
        errors = r.get("errors", [])
        if errors:
            with st.expander("⚠️  Step execution errors (intermediate)", expanded=False):
                for err in errors:
                    st.markdown(
                        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.74rem;color:#f43f5e;"
                        f"background:rgba(244,63,94,0.06);border-radius:6px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;white-space:pre-wrap;'>{err}</div>",
                        unsafe_allow_html=True,
                    )

        # Execution outputs
        outputs = r.get("outputs", [])
        if outputs:
            with st.expander("🖥️  Step execution outputs", expanded=False):
                for i, out in enumerate(outputs, 1):
                    st.markdown(
                        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.74rem;color:#94a3b8;"
                        f"background:#0d1117;border-radius:6px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;'>"
                        f"<span style='color:#475569;'>step {i} ›</span> {out}</div>",
                        unsafe_allow_html=True,
                    )

        # ── Test API button ───────────────────────────────────────────────
        app_path = r.get("assembled_app_path", "")
        if success and app_path and Path(app_path).exists():
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            # Extract imports from app.py and show install notice
            try:
                app_src = Path(app_path).read_text()
                stdlib = {
                    "os","sys","re","json","math","time","datetime","pathlib",
                    "typing","collections","itertools","functools","subprocess",
                    "hashlib","uuid","random","string","io","abc","copy",
                }
                third_party = []
                for line in app_src.splitlines():
                    line = line.strip()
                    if line.startswith("import ") or line.startswith("from "):
                        pkg = line.split()[1].split(".")[0]
                        if pkg not in stdlib and pkg not in third_party:
                            third_party.append(pkg)
                if third_party:
                    pip_cmd = "pip install " + " ".join(third_party)
                    st.markdown(f"""
                    <div style="background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.25);
                                border-radius:12px;padding:1rem 1.3rem;margin-bottom:0.8rem;">
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;letter-spacing:0.18em;
                                    text-transform:uppercase;color:#fbbf24;margin-bottom:0.5rem;">
                            ⚠️ &nbsp;Before testing — make sure all dependencies are installed
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:#94a3b8;margin-bottom:0.5rem;">
                            Your generated app uses: <span style="color:#e2e8f0;">{', '.join(third_party)}</span>
                        </div>
                        <div style="background:#0d1117;border-radius:6px;padding:0.5rem 0.8rem;">
                            <pre style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#fbbf24;margin:0;">{pip_cmd}</pre>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception:
                pass

            # ── Editable payload ─────────────────────────────────────────
            # Seed the draft with a task-keyword guess (no server needed)
            if st.session_state.payload_draft is None:
                seed = generate_test_payload(r["task"], "/predict", {})
                st.session_state.payload_draft = json.dumps(seed, indent=2)

            st.markdown("""
            <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;letter-spacing:0.18em;
                        text-transform:uppercase;color:#64748b;margin-bottom:0.4rem;margin-top:0.2rem;">
                ✏️ &nbsp;Edit test payload
            </div>
            """, unsafe_allow_html=True)

            edited_json = st.text_area(
                label="payload_editor",
                value=st.session_state.payload_draft,
                height=120,
                label_visibility="collapsed",
                key="payload_editor",
                help="Edit the JSON payload that will be sent to your API",
            )
            st.session_state.payload_draft = edited_json

            # Parse and validate JSON — try to auto-fix common mistakes first
            payload_valid = True
            parsed_payload = None

            def _try_fix_json(raw: str):
                """
                Try to fix JSON with literal newlines/tabs inside string values.
                e.g. the user pressed Enter inside a string field: {"text": "line1\nline2"}
                """
                import re as _re
                # Replace literal control chars inside JSON strings with escaped versions
                def fix_string(m):
                    inner = m.group(1)
                    inner = inner.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                    return '"' + inner + '"'
                fixed = _re.sub(r'"((?:[^"\\]|\\.)*)"', fix_string, raw, flags=_re.DOTALL)
                return json.loads(fixed)

            try:
                parsed_payload = json.loads(edited_json)
            except json.JSONDecodeError:
                # Attempt auto-fix (handles Enter key inside string values)
                try:
                    parsed_payload = _try_fix_json(edited_json)
                    # Update the draft to the corrected version so user sees clean JSON
                    st.session_state.payload_draft = json.dumps(parsed_payload, indent=2)
                except json.JSONDecodeError as e:
                    payload_valid = False
                    st.markdown(
                        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.7rem;"
                        f"color:#f43f5e;margin-top:0.2rem;'>⛔ Invalid JSON: {e}"
                        f"<br><span style='color:#64748b;font-size:0.65rem;'>"
                        f"Tip: if your text has line breaks, press Reset and retype on one line.</span></div>",
                        unsafe_allow_html=True,
                    )

            col_a, col_b = st.columns([3, 1])
            with col_a:
                test_btn = st.button(
                    "🧪  Run Test",
                    use_container_width=True,
                    key="test_btn",
                    disabled=not payload_valid,
                )
            with col_b:
                if st.button("↺  Reset", use_container_width=True, key="reset_payload"):
                    seed = generate_test_payload(r["task"], "/predict", {})
                    st.session_state.payload_draft = json.dumps(seed, indent=2)
                    st.session_state.test_result = None
                    st.rerun()

            if test_btn and payload_valid:
                st.session_state.test_result = None
                with st.spinner("Starting server · posting payload · waiting for response…"):
                    st.session_state.test_result = run_api_test_inline(
                        r["task"], app_path, custom_payload=parsed_payload
                    )

        # ── Test result display ───────────────────────────────────────────
        tr = st.session_state.test_result
        if tr:
            if tr.get("success"):
                endpoint = tr.get("endpoint", "/predict")
                payload  = tr.get("payload", {})
                response = tr.get("response", {})
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.25);
                            border-radius:14px;padding:1.4rem 1.6rem;margin-top:0.8rem;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;letter-spacing:0.2em;
                                text-transform:uppercase;color:#10b981;margin-bottom:1rem;padding-bottom:0.6rem;
                                border-bottom:1px solid rgba(16,185,129,0.15);">🧪 &nbsp;API Test — Passed ✓</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:#64748b;margin-bottom:0.8rem;">
                        POST &nbsp;<span style="color:#818cf8;">{endpoint}</span>
                    </div>
                    <div style="background:#0d1117;border-radius:8px;padding:0.9rem 1.1rem;margin-bottom:0.8rem;">
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#475569;
                                    letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.4rem;">Request</div>
                        <pre style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#a5b4fc;margin:0;white-space:pre-wrap;">{json.dumps(payload, indent=2)}</pre>
                    </div>
                    <div style="background:#0d1117;border-radius:8px;padding:0.9rem 1.1rem;">
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;color:#475569;
                                    letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.4rem;">
                            Response &nbsp;<span style="color:#10b981;">HTTP {tr.get('status_code')}</span></div>
                        <pre style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#6ee7b7;margin:0;white-space:pre-wrap;">{json.dumps(response, indent=2)}</pre>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:rgba(244,63,94,0.06);border:1px solid rgba(244,63,94,0.25);
                            border-radius:14px;padding:1.4rem 1.6rem;margin-top:0.8rem;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;letter-spacing:0.2em;
                                text-transform:uppercase;color:#f43f5e;margin-bottom:0.8rem;">🧪 &nbsp;API Test — Failed ✗</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#fca5a5;">{tr.get('error','Unknown error')[:400]}</div>
                </div>
                """, unsafe_allow_html=True)


# ── Run logic ─────────────────────────────────────────────────────────────────
if run_btn:
    if not task.strip():
        st.warning("Please enter a coding task first.")
    else:
        st.session_state.result  = None
        st.session_state.running = True
        st.session_state.done    = False
        st.rerun()

if st.session_state.running and not st.session_state.done:
    task_val = st.session_state.task_input.strip()

    # Show Planner as running — pipeline is synchronous so we can't
    # track real-time step progress; just indicate work has started.
    with pipeline_placeholder.container():
        render_pipeline_cards(active=0)

    with st.spinner("🤖  Autonomous AI Engineer at work — this takes ~60 seconds…"):
        try:
            result = run_pipeline(task_val)
        except Exception as e:
            result = {
                "status": "failed", "task": task_val, "plan": [],
                "generated_files": [], "outputs": [], "errors": [str(e)],
                "test_result": {}, "logs": [f"Pipeline crashed: {e}"],
            }

    st.session_state.result  = result
    st.session_state.running = False
    st.session_state.done    = True

    # Final pipeline render
    success   = result["status"] == "success"
    fail_step = -1 if success else 4

    with pipeline_placeholder.container():
        render_pipeline_cards(
            active=len(PIPELINE_STEPS) - 1,
            done=success,
            failed_at=fail_step if not success else -1,
        )

    # Render log
    logs = result.get("logs", [])
    if logs:
        log_html = "<br>".join(colorize_log(l) for l in logs)
        with log_placeholder.container():
            st.markdown(
                '<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.62rem;'
                'letter-spacing:0.18em;text-transform:uppercase;color:#334155;margin-bottom:0.5rem;">'
                '📋 &nbsp;Execution Log</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="log-viewer">{log_html}</div>', unsafe_allow_html=True)

    st.rerun()


# Show log if result already available (after rerun)
r = st.session_state.result
if r and not st.session_state.running:
    logs = r.get("logs", [])
    if logs:
        log_html = "<br>".join(colorize_log(l) for l in logs)
        with log_placeholder.container():
            st.markdown(
                '<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.62rem;'
                'letter-spacing:0.18em;text-transform:uppercase;color:#334155;margin-bottom:0.5rem;">'
                '📋 &nbsp;Execution Log</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="log-viewer">{log_html}</div>', unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="notice">
    Autonomous AI Engineer &nbsp;·&nbsp; Plan → Code → Run → Assemble → Test &nbsp;·&nbsp; Powered by LangGraph + Groq
</div>
""", unsafe_allow_html=True)
