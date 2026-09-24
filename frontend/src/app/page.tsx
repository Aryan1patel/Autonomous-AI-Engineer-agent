import Link from "next/link";
import s from "./landing.module.css";

const PIPELINE_STEPS = [
  {
    emoji: "🗂️",
    agent: "Planner Agent",
    title: "Decomposes your task into steps",
    desc: "An LLM reads your natural-language description and outputs a precise, ordered JSON array of implementation milestones — no ambiguity, no guesswork.",
  },
  {
    emoji: "💻",
    agent: "Coder Agent",
    title: "Writes production-ready Python",
    desc: "For each step, a dedicated Coder agent generates clean, executable Python with strict safety rules — no blocking servers, no unavailable libraries.",
  },
  {
    emoji: "⚙️",
    agent: "Executor Agent",
    title: "Runs code in a sandboxed subprocess",
    desc: "Every snippet is executed in an isolated subprocess with a hard 30-second timeout. Stdout and stderr are captured and fed into the next stage.",
  },
  {
    emoji: "🐛",
    agent: "Debugger Agent",
    title: "Fixes errors & retries automatically",
    desc: "If execution fails, the Debugger receives the broken code + full error trace and returns a corrected version. It retries up to 3 times per step.",
  },
  {
    emoji: "🔧",
    agent: "Assembler Agent",
    title: "Merges all steps into one app",
    desc: "Once all steps pass, an Assembler merges every generated file into a single, complete, runnable FastAPI application — ready to deploy.",
  },
  {
    emoji: "🧪",
    agent: "API Tester",
    title: "Validates the assembled API end-to-end",
    desc: "The test agent boots the assembled app on a local port, reads its OpenAPI schema, auto-generates a realistic test payload, and validates a successful 200 response.",
  },
];

const FEATURES = [
  {
    icon: "🤖",
    title: "Fully Autonomous",
    desc: "Zero human intervention from task description to working, tested API. The agents handle planning, coding, debugging, and testing automatically.",
  },
  {
    icon: "⚡",
    title: "Ultra-Fast Inference",
    desc: "Powered by Groq's hardware-accelerated inference. Typical end-to-end pipeline completes in 60–120 seconds versus minutes on standard LLM APIs.",
  },
  {
    icon: "🔄",
    title: "Self-Healing Pipeline",
    desc: "The Debugger agent catches and fixes code errors in real time. With up to 3 retries per step, broken code almost never reaches the final output.",
  },
  {
    icon: "📡",
    title: "Real-Time Streaming",
    desc: "Every agent event streams live to the frontend via Server-Sent Events. Watch each step transition from Waiting → Running → Done in real time.",
  },
  {
    icon: "🏗️",
    title: "Stateful LangGraph",
    desc: "Built on LangGraph's directed state graph. Every agent reads from and writes to a shared TypedDict — explicit, inspectable, and safely concurrent.",
  },
  {
    icon: "🔒",
    title: "Secure by Design",
    desc: "Path traversal prevention, sandboxed subprocess execution, configurable timeouts, and strict import allowlists keep the system safe in production.",
  },
];

const TECH = [
  { label: "LangGraph", color: "#818cf8" },
  { label: "LangChain", color: "#818cf8" },
  { label: "Groq", color: "#10b981" },
  { label: "FastAPI",   color: "#10b981" },
  { label: "Next.js",   color: "#a78bfa" },
  { label: "Pydantic",  color: "#f59e0b" },
  { label: "Tavily",    color: "#f97316" },
  { label: "Streamlit", color: "#f43f5e" },
  { label: "Python 3.11", color: "#64748b" },
  { label: "TypeScript",  color: "#6366f1" },
  { label: "Server-Sent Events", color: "#64748b" },
  { label: "uvicorn",   color: "#475569" },
];

export default function Landing() {
  return (
    <>
      {/* Animated background */}
      <div className={s.bg}>
        <div className={s.bgGrid} />
        <div className={s.bgGlow1} />
        <div className={s.bgGlow2} />
        <div className={s.bgGlow3} />
      </div>

      <div className={s.shell}>
        {/* ── Nav ── */}
        <nav className={s.nav}>
          <div className={s.navBrand}>
            <div className={s.navLogo}>🤖</div>
            <span className={s.navName}>AI Engineer</span>
          </div>
          <div className={s.navLinks}>
            <a href="#how" className={s.navLink}>How it works</a>
            <a href="#features" className={s.navLink}>Features</a>
            <a href="#tech" className={s.navLink}>Tech Stack</a>
            <Link href="/engineer" className={s.navCta}>
              Launch App <span className={s.btnArrow}>→</span>
            </Link>
          </div>
        </nav>

        {/* ── Hero ── */}
        <section className={s.hero}>
          <div className={s.heroBadge}>
            <div className={s.badgeDot} />
            LangGraph · Groq · FastAPI · Next.js
          </div>

          <h1 className={s.heroTitle}>
            Describe it.
            <span className={s.heroTitleLine2}>We ship the API.</span>
          </h1>

          <p className={s.heroSub}>
            A multi-agent AI system that takes any natural-language backend task
            and autonomously plans, writes, executes, debugs, assembles, and
            validates a working FastAPI application — no human in the loop.
          </p>

          <div className={s.heroCtas}>
            <Link href="/engineer" className={s.btnHeroPrimary}>
              Start Building <span className={s.btnArrow}>→</span>
            </Link>
            <a
              href="https://github.com/Aryan1patel/Autonomous-AI-Engineer-agent"
              target="_blank"
              rel="noopener noreferrer"
              className={s.btnHeroSecondary}
            >
              ⭐ View on GitHub
            </a>
          </div>

          {/* Terminal mock */}
          <div className={s.heroVisual}>
            <div className={s.terminalCard}>
              <div className={s.terminalBar}>
                <div className={`${s.termDot} ${s.termDotRed}`} />
                <div className={`${s.termDot} ${s.termDotYellow}`} />
                <div className={`${s.termDot} ${s.termDotGreen}`} />
                <span className={s.termTitle}>autonomous-ai-engineer — pipeline</span>
              </div>
              <div className={s.termBody}>
                <div>
                  <span className={s.termPrompt}>$ </span>
                  <span className={s.termCmd}>curl -X POST /submit-task -d </span>
                  <span className={s.termDim}>{'"Build a sentiment analysis API"'}</span>
                </div>
                <div className={s.termDim}>→ task_id: a3f9c2d1 submitted</div>
                <div>&nbsp;</div>
                <div><span className={s.termStep}>✓ [PLANNER]</span>   <span className={s.termOut}>Plan created with 4 steps</span></div>
                <div><span className={s.termStep}>✓ [CODER]</span>     <span className={s.termOut}>step_1_setup_fastapi.py written</span></div>
                <div><span className={s.termStep}>✓ [EXECUTOR]</span>  <span className={s.termOut}>step 1 → OK (0.4s)</span></div>
                <div><span className={s.termStep}>✓ [CODER]</span>     <span className={s.termOut}>step_2_sentiment_logic.py written</span></div>
                <div><span className={s.termStep}>✓ [EXECUTOR]</span>  <span className={s.termOut}>step 2 → OK (0.6s)</span></div>
                <div><span className={s.termStep}>✓ [CODER]</span>     <span className={s.termOut}>step_3_api_endpoint.py written</span></div>
                <div><span className={s.termStep}>✓ [EXECUTOR]</span>  <span className={s.termOut}>step 3 → OK (0.3s)</span></div>
                <div><span className={s.termStepRunning}>⟳ [ASSEMBLER]</span> <span className={s.termOut}>merging 3 step files → generated/app.py</span></div>
                <div><span className={s.termStep}>✓ [API_TESTER]</span> <span className={s.termOut}>POST /predict → HTTP 200</span></div>
                <div>&nbsp;</div>
                <div><span className={s.termSuccess}>✅ Pipeline complete in 68s  ·  4 files generated</span></div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats ── */}
        <div className={s.statsStrip}>
          {[
            { value: "7", label: "Specialized Agents" },
            { value: "~90s", label: "Avg pipeline time" },
            { value: "3×", label: "Auto-debug retries" },
            { value: "100%", label: "Autonomous end-to-end" },
          ].map((st, i) => (
            <div key={i} className={s.statItem}>
              <div className={s.statValue}>{st.value}</div>
              <div className={s.statLabel}>{st.label}</div>
            </div>
          ))}
        </div>

        {/* ── How it works ── */}
        <section id="how" className={s.howSection}>
          <div className={s.sectionLabel}>How it works</div>
          <h2 className={s.sectionTitle}>Six agents.<br />One working API.</h2>
          <p className={s.sectionSub}>
            Each agent is a pure function with a single responsibility. LangGraph
            wires them into a stateful directed graph with conditional retry edges.
          </p>
          <div className={s.pipelineFlow}>
            {PIPELINE_STEPS.map((step, i) => (
              <div key={i} className={s.pipelineStep}>
                <div className={s.pipelineNum}>{step.emoji}</div>
                <div className={s.pipelineContent}>
                  <div className={s.pipelineStepLabel}>Agent {String(i + 1).padStart(2, "0")}</div>
                  <div className={s.pipelineStepTitle}>{step.agent} — {step.title}</div>
                  <div className={s.pipelineStepDesc}>{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Features ── */}
        <section id="features" className={s.featuresSection}>
          <div className={s.sectionLabel}>Features</div>
          <h2 className={s.sectionTitle}>Built for real<br />autonomous work.</h2>
          <p className={s.sectionSub}>
            Every design decision optimizes for reliability, speed, and safety
            in a fully unsupervised agentic workflow.
          </p>
          <div className={s.featureGrid}>
            {FEATURES.map((f, i) => (
              <div key={i} className={s.featureCard}>
                <span className={s.featureIcon}>{f.icon}</span>
                <div className={s.featureTitle}>{f.title}</div>
                <div className={s.featureDesc}>{f.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Tech Stack ── */}
        <section id="tech" className={s.techSection}>
          <div className={s.sectionLabel}>Tech Stack</div>
          <h2 className={s.sectionTitle}>Production-grade<br />open-source stack.</h2>
          <p className={s.sectionSub}>
            Every component chosen for performance, reliability, and developer
            experience — from LLM orchestration down to the HTTP layer.
          </p>
          <div className={s.techGrid}>
            {TECH.map((t, i) => (
              <div key={i} className={s.techPill}>
                <div className={s.techPillDot} style={{ background: t.color }} />
                {t.label}
              </div>
            ))}
          </div>
        </section>

        {/* ── CTA ── */}
        <section className={s.ctaSection}>
          <div className={s.ctaCard}>
            <h2 className={s.ctaTitle}>
              Ready to ship your<br />
              <span className={s.ctaGrad}>first autonomous API?</span>
            </h2>
            <p className={s.ctaSub}>
              Describe what you want to build. Seven agents will plan, write,
              debug, and deliver a working FastAPI app in under two minutes.
            </p>
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
              <Link href="/engineer" className={s.btnHeroPrimary}>
                Launch the Engineer <span className={s.btnArrow}>→</span>
              </Link>
              <a
                href="https://github.com/Aryan1patel/Autonomous-AI-Engineer-agent"
                target="_blank"
                rel="noopener noreferrer"
                className={s.btnHeroSecondary}
              >
                ⭐ Star on GitHub
              </a>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className={s.footer}>
          <div className={s.footerLeft}>
            <div style={{ fontSize: "1.2rem" }}>🤖</div>
            <span className={s.footerName}>Autonomous AI Engineer</span>
          </div>
          <div className={s.footerRight}>
            Plan → Code → Run → Assemble → Test &nbsp;·&nbsp; Powered by LangGraph + Groq
          </div>
        </footer>
      </div>
    </>
  );
}
