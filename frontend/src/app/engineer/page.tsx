"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import clsx from "clsx";

// ── Test panel types ─────────────────────────────────────────────────────────
interface TestResult {
  success: boolean;
  endpoint?: string;
  payload?: Record<string, unknown>;
  status_code?: number;
  response?: Record<string, unknown>;
  error?: string;
}
import {
  Zap, CheckCircle2, XCircle, Clock, Download,
  Copy, Check, ChevronDown, ChevronUp, RotateCcw, Activity
} from "lucide-react";
import s from "./engineer.module.css";

// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────
type StepState = "waiting" | "running" | "success" | "error";

interface PipelineResult {
  status: "success" | "failed";
  task: string;
  plan: string[];
  generated_files: string[];
  outputs: string[];
  errors: string[];
  logs: string[];
}

interface SSEEvent {
  type: "status" | "log" | "plan" | "files" | "done" | "error";
  stage?: string;
  message?: string;
  steps?: string[];
  files?: string[];
  // done fields
  status?: string;
  plan?: string[];
  generated_files?: string[];
  outputs?: string[];
  errors?: string[];
  logs?: string[];
}

// ── Pipeline step definitions ─────────────────────────────────────────────────
const STEPS = [
  { id: "planner",   emoji: "🗂️", label: "Planner Agent",  desc: "Breaks task into ordered steps" },
  { id: "coder",     emoji: "💻", label: "Coder Agent",     desc: "Generates Python for each step" },
  { id: "executor",  emoji: "⚙️", label: "Executor Agent",  desc: "Runs code in sandboxed subprocess" },
  { id: "debugger",  emoji: "🐛", label: "Debugger Agent",  desc: "Fixes errors & retries (max 3×)" },
  { id: "writer",    emoji: "💾", label: "File Writer",     desc: "Saves working step files" },
  { id: "assembler", emoji: "🔧", label: "Assembler Agent", desc: "Merges all steps into one app.py" },
];

const EXAMPLES = [
  "Build a sentiment analysis REST API",
  "Build a TODO app API with CRUD endpoints",
  "Build a text summarizer API",
  "Build a URL shortener API",
  "Build a weather data API with caching",
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function classifyLog(line: string): string {
  const low = line.toLowerCase();
  if (low.includes("✓") || low.includes("success") || low.includes("passed")) return "success";
  if (low.includes("error") || low.includes("failed") || low.includes("✗"))   return "error";
  if (low.includes("assembler") || low.includes("api_tester"))                 return "amber";
  if (low.includes("planner") || low.includes("coder") || low.includes("pipeline")) return "info";
  return "";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepCard({ step, state, index }: { step: typeof STEPS[0]; state: StepState; index: number }) {
  const BADGE: Record<StepState, { label: string; cls: string }> = {
    waiting: { label: "Waiting",  cls: s.badgeWaiting },
    running: { label: "● Running", cls: s.badgeRunning },
    success: { label: "✓ Done",   cls: s.badgeSuccess },
    error:   { label: "✗ Error",  cls: s.badgeError },
  };
  const badge = BADGE[state];
  return (
    <div
      className={s.stepCard}
      data-state={state}
      style={{ animationDelay: `${index * 0.04}s` }}
    >
      <span className={s.stepIcon}>{step.emoji}</span>
      <div className={s.stepInfo}>
        <div className={s.stepNum}>{String(index + 1).padStart(2, "0")}</div>
        <div className={s.stepName}>{step.label}</div>
        <div className={s.stepDesc}>{step.desc}</div>
      </div>
      {state === "running" && (
        <div className={clsx(s.spinner, "anim-spin")} />
      )}
      <span className={clsx(s.stepBadge, badge.cls)}>{badge.label}</span>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  return (
    <button className={s.copyBtn} onClick={copy} title="Copy to clipboard">
      {copied ? <><Check size={11} /> Copied</> : <><Copy size={11} /> Copy</>}
    </button>
  );
}

function CodeViewer({ files }: { files: string[] }) {
  const [active, setActive] = useState(0);
  const [contents, setContents] = useState<Record<string, string>>({});

  // Fetch file content from backend
  const load = useCallback(async (filename: string) => {
    if (contents[filename] !== undefined) return;
    try {
      const res = await fetch(`${API_BASE}/files/${filename}`);
      const text = await res.text();
      setContents(prev => ({ ...prev, [filename]: text }));
    } catch {
      setContents(prev => ({ ...prev, [filename]: "// Error loading file" }));
    }
  }, [contents]);

  useEffect(() => {
    if (files.length > 0) {
      const name = files[0].split("/").pop()!;
      load(name);
    }
  }, [files, load]);

  const names = files.map(f => f.split("/").pop()!);

  return (
    <div>
      <div className={s.tabBar}>
        {names.map((name, i) => (
          <button
            key={name}
            className={s.tabBtn}
            data-active={active === i ? "true" : "false"}
            onClick={() => { setActive(i); load(name); }}
          >
            {name}
          </button>
        ))}
      </div>
      <div className={s.codeWrap}>
        <CopyButton text={contents[names[active]] ?? ""} />
        <pre className={s.codeBlock}>
          {contents[names[active]] ?? "Loading…"}
        </pre>
      </div>
      <a
        href={`${API_BASE}/files/${names[active]}`}
        download={names[active]}
        className={s.downloadBtn}
      >
        <Download size={12} />
        Download {names[active]}
      </a>
    </div>
  );
}

function LogViewer({ logs }: { logs: string[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (!logs.length) return null;
  return (
    <div className={s.logBox}>
      {logs.map((line, i) => (
        <div key={i} className={clsx(s.logLine, s[classifyLog(line)])}>
          {line}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

// ── TestPanel component ──────────────────────────────────────────────────────
function TestPanel({ result, apiBase }: { result: PipelineResult; apiBase: string }) {
  const STDLIB = new Set(["os","sys","re","json","math","time","datetime","pathlib",
    "typing","collections","itertools","functools","subprocess","hashlib","uuid",
    "random","string","io","abc","copy","threading","asyncio","http","urllib"]);

  // Detect third-party libs from generated files
  const appFile = result.generated_files.find(f => f.endsWith("app.py"));
  const [thirdParty, setThirdParty] = useState<string[]>([]);
  const [payloadStr, setPayloadStr] = useState("{}");
  const [jsonError, setJsonError] = useState("");
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    if (!appFile) return;
    const name = appFile.split("/").pop()!;
    fetch(`${apiBase}/files/${name}`)
      .then(r => r.text())
      .then(src => {
        const libs: string[] = [];
        src.split("\n").forEach(line => {
          const m = line.match(/^(?:import|from)\s+([\w]+)/);
          if (m && !STDLIB.has(m[1]) && !libs.includes(m[1])) libs.push(m[1]);
        });
        setThirdParty(libs);
      }).catch(() => {});
    // seed payload
    fetch(`${apiBase}/generate-payload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: result.task, endpoint: "/predict", openapi_schema: {} }),
    }).then(r => r.json()).then(d => {
      setPayloadStr(JSON.stringify(d.payload ?? {}, null, 2));
    }).catch(() => {});
  }, [appFile, apiBase, result.task]);

  const validate = (s: string) => {
    try { JSON.parse(s); setJsonError(""); return true; }
    catch(e: unknown) { setJsonError(String(e)); return false; }
  };

  const handlePayloadChange = (v: string) => {
    setPayloadStr(v); validate(v);
  };

  const handleReset = async () => {
    setTestResult(null);
    try {
      const r = await fetch(`${apiBase}/generate-payload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: result.task, endpoint: "/predict", openapi_schema: {} }),
      });
      const d = await r.json();
      setPayloadStr(JSON.stringify(d.payload ?? {}, null, 2));
      setJsonError("");
    } catch {}
  };

  const handleRunTest = async () => {
    if (!appFile || !validate(payloadStr)) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await fetch(`${apiBase}/run-api-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: result.task, app_path: appFile, payload: JSON.parse(payloadStr) }),
      });
      const data = await r.json();
      setTestResult(data);
    } catch(e) {
      setTestResult({ success: false, error: String(e) });
    } finally {
      setTesting(false);
    }
  };

  if (!appFile) return null;

  return (
    <div className={s.testPanel}>
      <div className={s.cardTitle}>🧪 &nbsp;Test the Generated API</div>

      {thirdParty.length > 0 && (
        <div className={s.depWarn}>
          <div className={s.depWarnTitle}>⚠️ &nbsp;Before testing — install dependencies</div>
          <div className={s.depWarnLibs}>Your app uses: <span>{thirdParty.join(", ")}</span></div>
          <div className={s.depWarnCmd}>pip install {thirdParty.join(" ")}</div>
        </div>
      )}

      <div className={s.payloadLabel}>✏️ &nbsp;Edit test payload</div>
      <textarea
        className={s.payloadEditor}
        value={payloadStr}
        onChange={e => handlePayloadChange(e.target.value)}
        rows={5}
        spellCheck={false}
      />
      {jsonError && <div className={s.jsonError}>⛔ {jsonError}</div>}

      <div className={s.testBtns}>
        <button
          className={s.btnRunTest}
          onClick={handleRunTest}
          disabled={testing || !!jsonError}
          id="run-test-btn"
        >
          {testing
            ? <><div className={clsx(s.spinner, "anim-spin")} /> Starting server…</>
            : <>🧪 Run Test</>}
        </button>
        <button className={s.btnReset} onClick={handleReset}>↺ Reset</button>
      </div>

      {testResult && (
        <div className={clsx(s.testResultBox, testResult.success ? s.testResultSuccess : s.testResultFailed)}>
          <div className={clsx(s.testResultHeader, testResult.success ? s.testResultHeaderSuccess : s.testResultHeaderFailed)}>
            {testResult.success ? "🧪 API Test — Passed ✓" : "🧪 API Test — Failed ✗"}
          </div>
          {testResult.success ? (
            <>
              <div className={s.testEndpoint}>POST &nbsp;<span>{testResult.endpoint}</span></div>
              <div className={s.testBlock}>
                <div className={s.testBlockLabel}>Request</div>
                <div className={clsx(s.testBlockCode, s.testBlockCodeRequest)}>
                  {JSON.stringify(testResult.payload, null, 2)}
                </div>
              </div>
              <div className={s.testBlock}>
                <div className={s.testBlockLabel}>Response &nbsp;HTTP {testResult.status_code}</div>
                <div className={clsx(s.testBlockCode, s.testBlockCodeResponse)}>
                  {JSON.stringify(testResult.response, null, 2)}
                </div>
              </div>
            </>
          ) : (
            <div className={s.testErrorMsg}>{testResult.error ?? "Unknown error"}</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function Home() {
  const [task, setTask]           = useState("");
  const [running, setRunning]     = useState(false);
  const [stepStates, setStepStates] = useState<StepState[]>(STEPS.map(() => "waiting"));
  const [logs, setLogs]           = useState<string[]>([]);
  const [plan, setPlan]           = useState<string[]>([]);
  const [result, setResult]       = useState<PipelineResult | null>(null);
  const [errorsOpen, setErrorsOpen]   = useState(false);
  const [outputsOpen, setOutputsOpen] = useState(false);
  const textareaRef               = useRef<HTMLTextAreaElement>(null);
  const eventSourceRef            = useRef<EventSource | null>(null);

  // Infer which step is active from log text
  const inferStep = (msg: string): number => {
    const m = msg.toLowerCase();
    if (m.includes("assembler"))            return 5;
    if (m.includes("file") && m.includes("writ")) return 4;
    if (m.includes("debug"))                return 3;
    if (m.includes("executor") || m.includes("execut")) return 2;
    if (m.includes("coder") || m.includes("cod"))       return 1;
    if (m.includes("planner") || m.includes("plan"))    return 0;
    return -1;
  };

  const updateStep = (idx: number, state: StepState) => {
    setStepStates(prev => {
      const next = [...prev];
      if (idx >= 0 && idx < next.length) next[idx] = state;
      return next;
    });
  };

  const handleRun = async () => {
    if (!task.trim() || running) return;
    setRunning(true);
    setResult(null);
    setLogs([]);
    setPlan([]);
    setStepStates(STEPS.map(() => "waiting"));
    updateStep(0, "running");

    // Close any previous SSE
    eventSourceRef.current?.close();

    try {
      // 1. Submit task
      const submitRes = await fetch(`${API_BASE}/submit-task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task.trim() }),
      });
      if (!submitRes.ok) throw new Error(`Submit failed: ${submitRes.status}`);
      const { task_id } = await submitRes.json();

      // 2. Stream SSE events
      const es = new EventSource(`${API_BASE}/stream-task/${task_id}`);
      eventSourceRef.current = es;

      let lastStep = 0;

      es.onmessage = (evt: MessageEvent) => {
        let event: SSEEvent;
        try { event = JSON.parse(evt.data); }
        catch { return; }

        if (event.type === "log" && event.message) {
          setLogs(prev => [...prev, event.message!]);
          const step = inferStep(event.message!);
          if (step >= 0 && step !== lastStep) {
            // Mark previous step success, activate current
            for (let i = 0; i < step; i++) updateStep(i, "success");
            updateStep(step, "running");
            lastStep = step;
          }
        }

        if (event.type === "plan" && event.steps) {
          setPlan(event.steps);
        }

        if (event.type === "done") {
          const r: PipelineResult = {
            status: (event.status === "success" ? "success" : "failed"),
            task: task,
            plan: event.plan ?? [],
            generated_files: event.generated_files ?? [],
            outputs: event.outputs ?? [],
            errors: event.errors ?? [],
            logs: event.logs ?? [],
          };
          setPlan(r.plan);
          setLogs(r.logs);
          setResult(r);
          setRunning(false);

          if (r.status === "success") {
            setStepStates(STEPS.map(() => "success"));
          } else {
            setStepStates(prev => prev.map(s => s === "running" ? "error" : s));
          }
          es.close();
        }

        if (event.type === "error") {
          setLogs(prev => [...prev, `ERROR: ${event.message}`]);
          setRunning(false);
          setStepStates(prev => prev.map(s => s === "running" ? "error" : s));
          es.close();
        }
      };

      es.onerror = () => {
        setRunning(false);
        setStepStates(prev => prev.map(s => s === "running" ? "error" : s));
        es.close();
      };

    } catch (err) {
      setLogs(prev => [...prev, `Error: ${err}`]);
      setRunning(false);
      setStepStates(prev => prev.map(s => s === "running" ? "error" : s));
    }
  };

  const handleReset = () => {
    eventSourceRef.current?.close();
    setTask("");
    setResult(null);
    setLogs([]);
    setPlan([]);
    setRunning(false);
    setStepStates(STEPS.map(() => "waiting"));
    textareaRef.current?.focus();
  };

  const progress = result
    ? 100
    : running
    ? Math.round((stepStates.filter(s => s === "success").length / STEPS.length) * 100)
    : 0;

  return (
    <>
      {/* Background */}
      <div className={s.bg}>
        <div className={s.grid} />
      </div>

      <div className={s.shell}>
        {/* Nav */}
        <nav className={s.nav}>
          <div className={s.navBrand}>
            <Link href="/" style={{ display:"flex", alignItems:"center", gap:"0.5rem", textDecoration:"none", color:"var(--text-muted)", fontFamily:"var(--font-mono)", fontSize:"0.7rem", marginRight:"0.75rem" }}>
              ← Home
            </Link>
            <div className={s.navIcon}>🤖</div>
            <span className={s.navTitle}>Autonomous AI Engineer</span>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <span className={s.navPill}>LangGraph · Groq</span>
            <a
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className={s.btnSecondary}
            >
              API Docs ↗
            </a>
          </div>
        </nav>

        {/* Hero */}
        <section className={s.hero}>
          <div className={s.heroBadge}>
            <div className={s.heroBadgeDot} />
            Plan · Code · Run · Debug · Assemble · Test
          </div>
          <h1 className={s.heroTitle}>
            The AI that{" "}
            <span className={s.heroGradient}>ships your API</span>
          </h1>
          <p className={s.heroSub}>
            Describe any backend task in plain English. Seven specialized agents
            will autonomously plan, write, execute, debug, and deliver a
            working FastAPI application.
          </p>
          <div className={s.heroPills}>
            <span className={s.heroPillLabel}>Try →</span>
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                className={s.chip}
                onClick={() => { setTask(ex); textareaRef.current?.focus(); }}
              >
                {ex}
              </button>
            ))}
          </div>
        </section>

        {/* Main layout */}
        <div className={s.layout}>

          {/* ── LEFT COLUMN ── */}
          <div>
            {/* Input */}
            <div className={s.inputCard}>
              <label className={s.inputLabel}>
                🎯 &nbsp;Your coding task
              </label>
              <textarea
                ref={textareaRef}
                className={s.textarea}
                value={task}
                onChange={e => setTask(e.target.value)}
                placeholder='e.g. "Build a sentiment analysis API using FastAPI with a /predict endpoint"'
                rows={4}
                onKeyDown={e => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleRun();
                }}
              />
              <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.75rem" }}>
                <button
                  className={s.btnPrimary}
                  onClick={handleRun}
                  disabled={running || !task.trim()}
                  id="run-btn"
                >
                  {running ? (
                    <><div className={clsx(s.spinner, "anim-spin")} /> Agents at work…</>
                  ) : (
                    <><Zap size={16} /> Run Autonomous Pipeline</>
                  )}
                </button>
                {(result || logs.length > 0) && (
                  <button className={s.btnSecondary} onClick={handleReset} title="Reset">
                    <RotateCcw size={13} />
                  </button>
                )}
              </div>
              {(running || result) && (
                <div className={s.progressWrap}>
                  <div className={s.progressBar} style={{ width: `${progress}%` }} />
                </div>
              )}
              <div style={{ fontSize: "0.68rem", color: "var(--text-dim)", marginTop: "0.5rem", fontFamily: "var(--font-mono)" }}>
                ⌘↵ to run &nbsp;·&nbsp; ~60–120 seconds end-to-end
              </div>
            </div>

            {/* Result */}
            {result && (
              <>
                {/* Status banner */}
                <div className={clsx(s.banner, result.status === "success" ? s.bannerSuccess : s.bannerFailed)}>
                  {result.status === "success"
                    ? <><CheckCircle2 size={20} /> Pipeline completed</>
                    : <><XCircle size={20} /> Pipeline failed</>}
                  <span className={s.bannerMeta}>
                    {result.generated_files.length} file(s) · {result.plan.length} steps
                  </span>
                </div>

                {/* Stats */}
                <div className={s.statsBar}>
                  {[
                    { label: "Steps", value: result.plan.length },
                    { label: "Files", value: result.generated_files.length },
                    { label: "Errors", value: result.errors.length },
                  ].map((st, i) => (
                    <div key={i} className={s.statCard} style={{ animationDelay: `${i * 0.08}s` }}>
                      <div className={s.statValue}>{st.value}</div>
                      <div className={s.statLabel}>{st.label}</div>
                    </div>
                  ))}
                </div>

                {/* Plan */}
                {result.plan.length > 0 && (
                  <div className={clsx(s.card, "anim-fadeUp")} style={{ marginBottom: "1.25rem" }}>
                    <div className={s.cardTitle}><Activity size={12} /> Generated Plan</div>
                    <div className={s.planList}>
                      {result.plan.map((step, i) => (
                        <div key={i} className={s.planItem} style={{ animationDelay: `${i * 0.05}s` }}>
                          <span className={s.planNum}>{String(i + 1).padStart(2, "0")}</span>
                          {step}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Files */}
                {result.generated_files.length > 0 && (
                  <div className={clsx(s.card, "anim-fadeUp")} style={{ marginBottom: "1.25rem" }}>
                    <div className={s.cardTitle}>💾 &nbsp;Generated Files</div>
                    <div className={s.filePills}>
                      {result.generated_files.map(f => {
                        const name = f.split("/").pop()!;
                        return (
                          <span
                            key={name}
                            className={clsx(s.filePill, name === "app.py" && s.filePillMain)}
                          >
                            {name}
                          </span>
                        );
                      })}
                    </div>
                    <CodeViewer files={result.generated_files} />
                  </div>
                )}

                {/* Step execution outputs — matches original Streamlit feature */}
                {result.outputs.length > 0 && (
                  <div className={s.expander} style={{ borderColor: "rgba(99,102,241,0.2)", marginBottom: "1rem" }}>
                    <button
                      className={s.expanderHeader}
                      style={{ background: "rgba(99,102,241,0.07)", color: "#818cf8" }}
                      onClick={() => setOutputsOpen(o => !o)}
                    >
                      <span>🖥️ &nbsp;Step execution outputs ({result.outputs.length})</span>
                      {outputsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {outputsOpen && (
                      <div className={s.expanderBody}>
                        {result.outputs.map((out, i) => (
                          <div key={i} style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "0.74rem",
                            color: "#94a3b8",
                            background: "rgba(0,0,0,0.3)",
                            borderRadius: "6px",
                            padding: "0.6rem 0.8rem",
                            marginBottom: "0.4rem",
                          }}>
                            <span style={{ color: "#475569" }}>step {i + 1} › </span>{out}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Step errors */}
                {result.errors.length > 0 && (
                  <div className={s.expander}>
                    <button className={s.expanderHeader} onClick={() => setErrorsOpen(o => !o)}>
                      <span>⚠️ &nbsp;Step errors ({result.errors.length})</span>
                      {errorsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {errorsOpen && (
                      <div className={s.expanderBody}>
                        {result.errors.map((err, i) => (
                          <div key={i} className={s.errorItem}>{err}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Test Panel — only shown when pipeline succeeded and app.py exists */}
                {result.status === "success" && result.generated_files.some(f => f.endsWith("app.py")) && (
                  <TestPanel result={result} apiBase={API_BASE} />
                )}
              </>
            )}

            {/* Empty state when idle */}
            {!result && !running && (
              <div className={s.emptyState}>
                <div className={s.emptyIcon}>⚡</div>
                <div className={s.emptyTitle}>Ready to build</div>
                <div className={s.emptyDesc}>
                  Enter a task above, hit Run, and watch seven AI agents<br />
                  collaborate in real-time to deliver your API.
                </div>
              </div>
            )}
          </div>

          {/* ── RIGHT COLUMN ── */}
          <div style={{ position: "sticky", top: "1.5rem" }}>
            <div className={s.card} style={{ marginBottom: "1rem" }}>
              <div className={s.cardTitle}><Clock size={12} /> Pipeline</div>
              <div className={s.stepsGrid}>
                {STEPS.map((step, i) => (
                  <StepCard key={step.id} step={step} state={stepStates[i]} index={i} />
                ))}
              </div>
            </div>

            {/* Live log */}
            {(logs.length > 0 || running) && (
              <div className={s.card}>
                <div className={s.cardTitle}>📋 &nbsp;Execution Log</div>
                <LogViewer logs={logs} />
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className={s.footer}>
          <div className={s.footerText}>
            Autonomous AI Engineer &nbsp;·&nbsp; Plan → Code → Run → Assemble → Test
            &nbsp;·&nbsp; Powered by LangGraph + Groq
          </div>
        </footer>
      </div>
    </>
  );
}
