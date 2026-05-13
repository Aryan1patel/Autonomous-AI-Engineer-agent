# Research Pipeline — Multi-Agent Web Research System

## What It Does

You give it a topic like _"Quantum computing trends"_ and it autonomously searches the web, scrapes the most relevant page, writes a structured research report, and then self-reviews it with a critic — all without you doing anything.

It uses **LangGraph ReAct agents** for search and scraping, and **LangChain chains** for writing and reviewing.

---

## How to Run

```bash
streamlit run search_app.py
```

Opens in your browser automatically. Type a topic and hit submit.

---

## Files Involved

| File | Role |
|------|------|
| `search_app.py` | Streamlit UI — input topic, display report + critic review |
| `search_pipeline.py` | Orchestrator — runs all 4 steps in sequence |
| `search_agents.py` | Agent and chain definitions — Search, Reader, Writer, Critic |
| `search_tools.py` | Tools — Tavily web search + BeautifulSoup URL scraper |

---

## Agents & Chains

| Component | Type | What It Does |
|-----------|------|-------------|
| **Search Agent** | ReAct Agent | Uses Tavily API to search the web for the topic |
| **Reader Agent** | ReAct Agent | Picks the most relevant URL and scrapes its full content |
| **Writer Chain** | LLM Chain | Synthesizes search + scraped content into a structured report |
| **Critic Chain** | LLM Chain | Reviews the report and scores it with strengths and improvements |

**ReAct Agent** = the LLM reasons step-by-step and decides when to call a tool (search or scrape) and what to do with the result.

**LLM Chain** = a simple prompt → LLM → output parser pipeline. No tool use, just generation.

---

## Workflow

```
You submit: "Quantum computing trends"
                    │
                    ▼
        ┌───────────────────────┐
        │   STEP 1: SEARCH      │
        │   Search Agent        │
        │   Tool: Tavily API    │
        └──────────┬────────────┘
                   │  Returns raw search results
                   │  (titles, snippets, URLs)
                   │  → capped at 2000 chars
                   ▼
        ┌───────────────────────┐
        │   STEP 2: SCRAPE      │
        │   Reader Agent        │
        │   Tool: BeautifulSoup │
        └──────────┬────────────┘
                   │  Picks top URL from results
                   │  Scrapes full page content
                   │  → capped at 2000 chars
                   ▼
        ┌───────────────────────┐
        │   STEP 3: WRITE       │
        │   Writer Chain        │
        │   (LLM only)          │
        └──────────┬────────────┘
                   │  Combines search + scraped content
                   │  LLM writes a structured report:
                   │    - Introduction
                   │    - Key Findings (3 points)
                   │    - Conclusion
                   │    - Sources
                   ▼
        ┌───────────────────────┐
        │   STEP 4: CRITIQUE    │
        │   Critic Chain        │
        │   (LLM only)          │
        └──────────┬────────────┘
                   │  Reviews the report strictly
                   │  Returns:
                   │    Score: X/10
                   │    Strengths
                   │    Areas to Improve
                   │    One line verdict
                   ▼
              Final Output:
              { report, feedback }
```

---

## Architecture Difference vs Coding Pipeline

| | Research Pipeline | Coding Pipeline |
|---|---|---|
| **Structure** | Sequential chain (4 steps, no branching) | LangGraph directed graph with conditional edges |
| **Retry logic** | No retry — each step runs once | Executor → Debugger loop (up to 3 retries per step) |
| **Agent type** | ReAct agents (search/scrape) + LLM chains (write/review) | Pure LLM chains only |
| **Tools** | Tavily search, BeautifulSoup scraper | Python subprocess executor |
| **Output** | Report + critic feedback (text) | Working FastAPI app (Python files) |

The research pipeline is sequential because there's no retry or branching needed — each step feeds directly into the next. The complexity lives in the tools (web search + scraping), not the control flow.

---

## Tools

**`web_search` (Tavily)**
Calls the Tavily API with the topic query. Returns structured search results — titles, URLs, and snippets from the web. Tavily is optimized for AI use, returning cleaner results than raw Google/Bing.

**`scrape_url` (BeautifulSoup)**
Takes a URL and fetches the page using `requests`. Parses it with BeautifulSoup to extract readable text, stripping HTML tags, scripts, and styles. Returns the cleaned body text.

---

## Key Design Decisions

**Why ReAct agents for search and scraping, not plain chains?**
ReAct agents can reason about which tool to call and when. The Reader Agent decides which URL to pick from the search results before scraping — that decision-making needs an agent, not a static chain.

**Why LLM chains for writing and critiquing?**
Writing and reviewing don't need tools — just a good prompt and the LLM's knowledge. A chain (prompt → LLM → parser) is simpler, faster, and cheaper than a full agent for these steps.

**Why cap content at 2000 chars?**
The free Groq tier has an 8000 TPM limit. A scraped web page can easily be 5000+ tokens alone. Capping search results and scraped content keeps the total prompt size under the limit.

**Why a separate API key for this pipeline?**
The coding and research pipelines share the same Groq account but have separate API keys. This gives each pipeline its own independent TPM bucket — so running one doesn't starve the other.
