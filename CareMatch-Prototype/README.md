# CareMatch API

**An AI tool that helps hospital staff check if a patient qualifies for a clinical trial — and shows its work, every single time.**

**New here?** See [setup_guide.md](./setup_guide.md) for step-by-step setup instructions, and [seed_data.md](./seed_data.md) for copy-paste examples to try once it's running.

---

## Table of Contents

- [Setup — Get It Running](#setup--get-it-running)
- [Documentation Map](#documentation-map)
- [What This Project Does](#what-this-project-does)
- [Why It's Built This Way](#why-its-built-this-way)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [The API](#the-api)
- [Guardrails](#guardrails)
- [Running It Yourself](#running-it-yourself)
- [Deployment — Cloud Run (Live)](#deployment--cloud-run-live)
- [Environment Variables](#environment-variables)
- [Monitoring, Logging & Tracing](#monitoring-logging--tracing)
- [Testing](#testing)
- [Key Decisions (and Why)](#key-decisions-and-why)
- [Real Problems We Found and Fixed](#real-problems-we-found-and-fixed)
- [How Well Does It Actually Work?](#how-well-does-it-actually-work)
- [What's Not Built](#whats-not-built)

---

## Documentation Map

Everything worth reading, and what to read it for. This file ([`README.md`](./README.md)) is the technical overview; the four guides below take you from "nothing installed" to "I understand the whole project."

**For everyone — read in this order:**

| Doc | Read it to |
|---|---|
| [`setup_guide.md`](./setup_guide.md) | Get the app running, step by step, from a fresh computer. This is the only doc you need to start. |
| [`seed_data.md`](./seed_data.md) | Type in exact values and confirm the app is actually working with your own eyes. |
| [`monitoring_guide.md`](./monitoring_guide.md) | Understand what Prometheus and Grafana are, and look at the app's health numbers yourself — click by click. |
| [`project_summary.md`](./project_summary.md) | Get the whole story: what got built, what actually broke and got fixed, and the honest results. |

> **Two similar-sounding terms, worth telling apart:** "Needs More Information" is what the AI suggests when it can't tell from the record alone (see the `suggested_status` field). "Needs More Review" is a separate action a coordinator can choose afterward, to flag an assessment for later follow-up. One comes from the AI, the other from a human — they are not the same thing.

**For developers:**

| Doc | Read it to |
|---|---|
| [`dashboard/README.md`](./dashboard/README.md) | Developer notes for the dashboard — how to run it and what's built. |
| [`dashboard/src/routes/README.md`](./dashboard/src/routes/README.md) | Internal note on how the dashboard's file-based routing works. |

**The rest of the repository (this folder is one sub-project of `Production-Layer`):**

| Doc | Read it to |
|---|---|
| [`../README.md`](../README.md) | The `Production-Layer` monorepo overview — the repository that holds this folder. |
| [`../CareMatch-SDD/README.md`](../CareMatch-SDD/README.md) | The other sub-project: a larger spec-driven CareMatch API (FHIR, JWT auth, AI agent team). |
| [`../CareMatch-SDD/SPECKIT_WORKFLOW.md`](../CareMatch-SDD/SPECKIT_WORKFLOW.md) | How the SDD sub-project is developed with GitHub Spec Kit. |

The suggested path for a newcomer is simple: [setup_guide.md](./setup_guide.md) → [seed_data.md](./seed_data.md) → [monitoring_guide.md](./monitoring_guide.md) → [project_summary.md](./project_summary.md).

---

## Setup — Get It Running

Getting the app from a fresh computer to a running app — cloning the code,
the one machine requirement (Docker Desktop), the API key, starting
everything, verifying it works, and troubleshooting — all lives in
**[setup_guide.md](./setup_guide.md)**. It's the only doc you need to start;
this README is the technical overview for after it's running.

---

## What This Project Does

Hospitals run clinical trials — tests of new medicines or treatments. Before a patient can join one, someone has to check if they qualify against a list of rules (called a **protocol**). Today, a hospital staff member called a **research coordinator** does this by hand — reading through a patient's whole medical file and checking it line by line. It's slow, and it's easy to miss something.

**CareMatch reads the patient's file and the trial's rules, and hands the coordinator a clear report** — not a decision. It never says "yes, this patient qualifies" on its own. Instead, it checks every single rule one at a time and says: *this one clearly matches, this one clearly doesn't, and this one we can't tell from the record.* Then a real human decides.

## Why It's Built This Way

Two things usually break AI tools in hospitals:

1. **It's too expensive to plug in.** Big AI systems often need $250,000+ just to connect to a hospital's existing computer systems.
2. **Nobody trusts a black box.** If an AI just says "excluded" with no explanation, no doctor is going to act on that — and legally, they probably shouldn't.

CareMatch is built to avoid both. It's a small, simple tool that plugs into anything with a basic web connection, and it **never gives an answer without showing exactly how it got there.**

---

## How It Works

```mermaid
flowchart TD
    A[Patient's medical record + Trial's rulebook] --> B[AI checks each rule, one at a time]
    B --> C{For every single rule}
    C --> D[✅ Matches - with a quote as proof]
    C --> E[❌ Does Not Match - with a quote as proof]
    C --> F[❓ Unclear - because info is missing]
    D --> G[All results bundled into one report]
    E --> G
    F --> G
    G --> H[Human coordinator reviews the report]
    H --> I{Coordinator decides}
    I --> J[✅ Accept]
    I --> K[❌ Deny, with a written reason]
    I --> N[❓ Needs More Review]
    J --> L[Decision saved permanently]
    K --> L
    N --> M[Assessment stays open, flagged]
    M --> H
```

**The one rule that never changes:** the AI's answer is always a *suggestion*. Even if every single rule looks like a clean match, a human still has to make a final call — Accept or Deny — before it counts as anything real. The third option, "Needs More Review," is not a dead end: it simply keeps the assessment open while the coordinator gathers the missing information, and the decision is finished with an Accept or Deny later. There is no way to skip this step — it's built into the code itself, not just a policy someone has to remember.

---

## Architecture

```mermaid
flowchart LR
    subgraph Browser
        UI[Dashboard<br/>React / TanStack Start]
    end

    subgraph Backend
        API[API<br/>FastAPI]
        ENGINE[Reasoning Engine<br/>Python]
        DB[(Postgres on Supabase<br/>trials, assessments, decisions)]
    end

    subgraph Monitoring
        PROM[Prometheus]
        GRAF[Grafana]
    end

    LLM[(AI Model<br/>Claude Haiku)]
    LS[(LangSmith<br/>AI decision history)]

    UI -- HTTP requests --> API
    API -- one call per rule --> ENGINE
    ENGINE -- asks a question about one rule --> LLM
    LLM -- answer + evidence --> ENGINE
    API -- reads/writes --> DB
    API -- exposes /metrics --> PROM
    PROM -- feeds data to --> GRAF
    ENGINE -. every real AI call also logged to .-> LS
```

**In plain words:**
- **Dashboard** — the webpage a coordinator actually looks at
- **API** — the doorway other systems (like the dashboard) use to send data in and get answers back
- **Reasoning Engine** — the actual "brain." It goes through a trial's rules one at a time
- **Postgres database (Supabase)** — where trial rules, patient assessments, and coordinator decisions are permanently stored, so nothing is lost if the app restarts — and since the database is hosted remotely, not even a hard kill of the app machine loses it
- **AI Model** — the underlying language model that reads the patient text and judges each rule
- **Prometheus & Grafana** — a health dashboard for the *system itself* (is it fast? is it breaking? how many checks has it done?), separate from the coordinator's dashboard
- **LangSmith** (optional) — a permanent, browsable history of every individual AI decision, useful for reviewing or evaluating reasoning quality later

---

## Project Structure

The folder layout only — each box is one file or folder. What each file does is covered in the README section that describes it (Guardrails, The API, Testing, Deployment, Monitoring) and in the guides linked above. Two notes:

- **`observability/` is retired** — it was an early standalone monitoring test; real monitoring now lives directly inside `api/main.py`.
- **`run_evaluation.py`** is the 12-patient accuracy test script — its results are in [project_summary.md](./project_summary.md).

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 6, "rankSpacing": 30, "padding": 8}}}%%
flowchart LR
    ROOT["carematch/"] --> RE_CORE
    ROOT --> RE_SCRIPTS
    ROOT --> API
    ROOT --> DASH
    ROOT --> RT_DOCS
    ROOT --> RT_CFG
    ROOT --> EV["run_evaluation.py"]
    ROOT --> OBS["observability/"]

    subgraph RE_CORE["reasoning_engine/ — core logic & safety"]
        RE_SCHEMA["schema.py"]
        RE_PROTO["protocol.py"]
        RE_ENG["engine.py"]
        RE_LLM["llm_client.py"]
        RE_GR["guardrails.py"]
    end

    subgraph RE_SCRIPTS["reasoning_engine/ — scripts, tests & data"]
        RE_RUN["run_real_assessment.py"]
        RE_TEST["test_engine.py"]
        RE_REQ["requirements.txt"]
        RE_ENV[".env.example"]
        RE_DATA["test_data/"]
    end

    subgraph API["api/ — web service"]
        API_MAIN["main.py"]
        API_DB["db.py"]
        API_TEST["test_api.py"]
        API_DOCK["Dockerfile"]
        API_REQ["requirements.txt"]
    end

    subgraph DASH["dashboard/ — web UI"]
        direction TB
        DASH_SRC["src/"]
        DASH_SRC --> DASH_ROUTES["routes/"]
        DASH_SRC --> DASH_COMP["components/"]
        DASH_SRC --> DASH_HOOKS["hooks/"]
        DASH_SRC --> DASH_API["lib/api.ts"]
    end

    subgraph RT_DOCS["project root — docs"]
        RT_RM["README.md"]
        RT_PS["project_summary.md"]
        RT_SETUP["setup_guide.md"]
        RT_SEED["seed_data.md"]
        RT_MON["monitoring_guide.md"]
    end

    subgraph RT_CFG["project root — deployment & config"]
        RT_DC["docker-compose.yml"]
        RT_DF["Dockerfile"]
        RT_CBD["cloudbuild.dashboard.yaml"]
        RT_PC["prometheus_config.yml"]
    end
```

---

## Tech Stack

| Piece | What It's Built With | Why |
|---|---|---|
| Reasoning Engine | Python, Pydantic | Pydantic forces every AI answer to follow our exact required shape — an answer that doesn't fit gets rejected automatically |
| AI Model Access | Anthropic Claude (direct) | Every assessment calls Anthropic directly; model is switchable via one env var, no code changes needed |
| API | FastAPI | Lightweight, fast, and automatically generates interactive docs |
| Persistence | Postgres (Supabase) | A hosted Postgres database — trials, assessments, and decisions survive a restart and even a hard kill of the app process |
| Dashboard | React + TanStack Start + Tailwind CSS | A modern, fast web app framework |
| Metrics | Prometheus + Grafana | Industry-standard tools for watching the system's health in real time |
| AI Tracing (optional) | LangSmith | Records every individual AI reasoning call permanently, so decisions can be reviewed or evaluated later — not just watched live |
| Packaging | Docker + Docker Compose | Lets the whole project start with one command, on any computer |

---

## The API

| Method | Path | What It Does |
|---|---|---|
| GET | `/health` | Simple check — is the API alive? |
| GET | `/metrics` | Raw performance/usage numbers, read by Prometheus |
| POST | `/trials` | Register a new trial's rulebook |
| GET | `/trials` | List every trial that's been registered |
| GET | `/trials/{trial_id}` | Look up one specific trial |
| POST | `/assess` | Run a real eligibility check for one patient against one trial |
| GET | `/assessments` | List every assessment ever run, newest first (Assessment History view) |
| GET | `/assessments/{assessment_id}` | Look up a past assessment |
| POST | `/assessments/{assessment_id}/decision` | Record the coordinator's decision — Accept, Deny, or Needs More Review |
| DELETE | `/assessments/{assessment_id}` | Permanently delete an assessment, its per-rule results, and any recorded decision (204; unknown id → 404) |
| DELETE | `/trials/{trial_id}` | Delete a trial and its rulebook (204; refused with 409 while any assessments reference it) |

Every response also includes an `X-Request-ID` header — a unique ID for that specific request, useful for tracing a problem through the logs later (see [Monitoring, Logging & Tracing](#monitoring-logging--tracing)).

A coordinator decision is one of three values: `accepted`, `denied`, or `needs_more_review`. **Accept and Deny are final** — once recorded, the assessment is locked. **`needs_more_review` is temporary.** It just flags the assessment as "still being worked on" and leaves it open, so the coordinator can come back later and turn it into a final Accept or Deny once the missing information arrives.

**Example — what you get back from `/assess`:**
```json
{
  "assessment_id": "67207011-cda7-4ba9-a2f6-4388d7144fd5",
  "assessment": {
    "patient_id": "P-1001",
    "trial_id": "T-004",
    "suggested_status": "likely_eligible",
    "requires_coordinator_approval": true,
    "rule_results": [
      {
        "rule_id": "INC-01",
        "rule_text": "Patient must be 50 years of age or older",
        "status": "matches",
        "evidence": "60-year-old patient"
      }
    ]
  },
  "decision": null,
  "provider_used": "anthropic",
  "model_used": "claude-haiku-4-5-20251001"
}
```
Notice: no confidence score, no flat "yes." Just a status, a quote, and a note that a human still needs to sign off.

---

## Guardrails

The AI is never trusted blindly. Every assessment passes through two layers of safety checks (enforced in `reasoning_engine/guardrails.py`, wired into the API in `api/main.py`):

- **Input guardrails** run *before* anything is sent to the AI, so a rejected record costs zero API credits: a 10,000-character length limit, PII pattern scanning (SSN-format numbers, email addresses, phone numbers), and injection-pattern scanning (instructional phrases like "ignore previous instructions"). A rejection is a clean **422** that never echoes the matched value — e.g. "Possible SSN detected in patient record."
- **Output guardrail** runs after each AI answer: evidence the model quotes must actually appear in the patient record, or it's overridden to `unclear` rather than trusted as fact.

Each guardrail has its own Prometheus counter (`input_length_rejected_total`, `input_pii_rejected_total`, `input_injection_rejected_total`, `hallucinated_evidence_caught_total`). See [monitoring_guide.md](./monitoring_guide.md) for the queries and [project_summary.md](./project_summary.md) for the full story, including the real false-positive fix.

---

## Running It Yourself

Step-by-step run instructions — Docker or manual, plus all the local URLs and
the data-persistence details — are in **[setup_guide.md](./setup_guide.md)**.
If you'd rather use the live hosted version than run your own copy, see
[Deployment — Cloud Run (Live)](#deployment--cloud-run-live).

One thing to remember before any client demo: **CareMatch always runs with
real AI.** Confirm the top-level `.env` has a valid `ANTHROPIC_API_KEY` — a
missing key fails loudly with a 502, never quietly. Every assessment makes a
real, paid call to the AI model.

---

## Deployment — Cloud Run (Live)

The whole stack is deployed to Google Cloud Run and is reachable from anywhere with an internet connection:

| Service | Live URL |
|---|---|
| CareMatch API | `https://carematch-api-726123996575.us-central1.run.app` |
| CareMatch Dashboard | `https://carematch-dashboard-726123996575.us-central1.run.app` |

Project: `infra-window-477206-f2` · Region: `us-central1`. This is a real deployment — real Supabase Postgres, real Anthropic calls — so a live assessment still spends a little API credit.

### The API image

The top-level `Dockerfile` builds the API for Cloud Run. Its last line is the one Cloud Run cares about:

```dockerfile
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Cloud Run injects `PORT` (default 8080) at runtime, so the app listens on `0.0.0.0` and the port Cloud Run expects; `${PORT:-8000}` keeps it runnable on a local machine too. Deploy it with:

```bash
gcloud run deploy carematch-api --source . --region us-central1 --allow-unauthenticated
```

### The dashboard image

The dashboard's `Dockerfile` builds a TanStack Start/Nitro app (the `node-server` preset) and ships only the built `.output/`. Nitro's bundled server reads `NITRO_PORT`, then `PORT`, and falls back to **3000** if both are unset — so the container maps Cloud Run's `PORT` onto Nitro explicitly:

```dockerfile
CMD ["sh", "-c", "NITRO_PORT=${PORT:-8080} exec node .output/server/index.mjs"]
```

**The one dashboard gotcha:** the API URL is baked in at **build time**, not read at runtime. `dashboard/src/lib/api.ts` resolves `import.meta.env.VITE_API_BASE_URL`, so the dashboard image must be built with `--build-arg VITE_API_BASE_URL=https://carematch-api-726123996575.us-central1.run.app`. Two consequences:

- `gcloud run deploy carematch-dashboard --source ./dashboard` **does not work for this project**: the Dockerfile copies `dashboard/...` (it needs the repo root as build context) and `gcloud run deploy` has no `--build-arg` flag — the image would bake in `http://localhost:8000`, and the live dashboard would ask each visitor's own browser to fetch from their computer.
- The correct path is a two-step build-then-deploy via `cloudbuild.dashboard.yaml`, which passes the live API URL as the build arg:

```bash
gcloud builds submit . --config cloudbuild.dashboard.yaml
gcloud run deploy carematch-dashboard \
  --image us-central1-docker.pkg.dev/infra-window-477206-f2/cloud-run-source-deploy/carematch-dashboard \
  --region us-central1 \
  --allow-unauthenticated
```

### CORS and health

`api/main.py` whitelists both dashboard origins — the local dev server (`http://localhost:8080`) and the live Cloud Run dashboard — so the browser can call the API from either one. The live API also exposes `/health` and `/metrics`; local Prometheus scrapes both the live endpoint (job `carematch-api-live`) and, when you run the stack locally, your local API (job `carematch-api`) — see [monitoring_guide.md](./monitoring_guide.md).

---

## Environment Variables

**CareMatch always makes real AI calls** — every assessment uses a small amount of API credits. The automated test suite is the exception: it substitutes a mock for the AI call from inside the test file itself, so tests are free to run and never touch the real API. Each variable below is only needed if you want to turn on the specific feature it controls.

There are a few different `.env` files depending on how you're running things:

| File | When You Need It | Template Available? |
|---|---|---|
| `carematch/.env` (project root) | Running everything via Docker — `docker-compose.yml` reads this one | Yes — copy `carematch/.env.example` |
| `api/.env` | Running the API manually with `uvicorn` (no Docker) — `api/db.py` loads this one itself | Yes — copy `api/.env.example` |
| `reasoning_engine/.env` | Running the reasoning engine's own scripts directly, without Docker | Yes — copy `reasoning_engine/.env.example` |

**When running on Google Cloud Run, none of these are used** — the deployed service reads its environment variables (including `DATABASE_URL`) from the Cloud Run service configuration, not from any `.env` file.

| Variable | What It Does | Required When |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key | Always — every assessment makes a real call to Anthropic directly |
| `ANTHROPIC_MODEL` | Which Anthropic model to use | Never — has a default |
| `LANGSMITH_TRACING` | `"true"` turns on permanent AI decision logging | Never — defaults to off |
| `LANGSMITH_API_KEY` | Your LangSmith key | Only if `LANGSMITH_TRACING=true` |
| `LANGSMITH_PROJECT` | Which LangSmith project traces go into | Never — has a default |
| `LANGSMITH_WORKSPACE_ID` | Your LangSmith workspace ID | Only if tracing is on **and** your key is an org-scoped "Service" key (starts with `lsv2_sk_`) — LangSmith rejects requests without it in that case |
| `DATABASE_URL` | Postgres connection string for Supabase. Use the **transaction pooler** DSN — `postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres` — **not** the "direct connection" string. The direct endpoint (`db.<project-ref>.supabase.co`) resolves to IPv6 only, and cloud hosts like Cloud Run have no IPv6 path to it; the pooler provides the IPv4 address they need. If your password contains special characters like `@`, percent-encode them (e.g. `@` → `%40`) | Always — the API persists everything to Postgres |
| `CAREMATCH_DB_SCHEMA` | Schema to put all tables in | Never — defaults to `public` (the test suite uses a throwaway schema) |

**Good to know:** a missing or misconfigured LangSmith key never breaks the app itself — tracing failures are silently logged, but every real feature keeps working normally either way.

**Never commit either real `.env` file** — only the `.env.example` templates (with no real secrets in them) belong in version control.

---

## Monitoring, Logging & Tracing

CareMatch has three separate, complementary ways of watching what the system is doing — each answering a different question. **Want to look at these numbers yourself, click by click? See [monitoring_guide.md](./monitoring_guide.md).**

### 1. Prometheus + Grafana — "Is the system healthy?"
Tracks system-wide numbers over time: how many assessments have run, how long reasoning takes, how often coordinators accept vs. deny, and standard web traffic stats. Prometheus collects the numbers (configured in `prometheus_config.yml`, which also watches its own health); Grafana turns them into charts. Good for spotting trends — "did things slow down this week?" — not for looking at one specific event.

### 2. Request Logging — "What happened on this exact request?"
Every single request to the API gets a unique ID (visible in the `X-Request-ID` response header) and one log line recording what happened: which endpoint, how long it took, what it returned. If something goes wrong for one specific user action, this is how you'd trace it — "show me everything about request abc123."

### 3. LangSmith (optional) — "Why did the AI decide this?"
While Prometheus shows *how many* checks ran, LangSmith shows the actual *content* of each one — the exact question asked and the exact answer given, for every single rule the AI ever evaluated, permanently stored and browsable. This is useful for reviewing reasoning quality after the fact, well beyond what a live dashboard number can show. Entirely optional — the app works fully without it, and a failure to record a trace never affects a real request.

---

## Testing

```bash
# Reasoning engine tests (no API key needed — injects a fake LLM for testing)
cd reasoning_engine
pytest test_engine.py -v

# API tests (also free — mocks the LLM call from the test file, uses a throwaway database)
cd api
pytest test_api.py -v
```

Both test suites are fully automated and cost nothing to run, since they never make a real call to an AI model. The API tests run against the real Supabase database but entirely inside a throwaway `carematch_test` schema — created fresh at the start and dropped again at the end, so real data in `public` is never touched and repeated runs never collide.

The dashboard also has a browser end-to-end suite (Playwright, in `dashboard/tests/`) that drives the real UI against the local stack. It needs the local services running (dashboard on `http://localhost:8080`, API on `http://localhost:8000`, e.g. via `docker compose`):

```bash
# Dashboard browser tests (Playwright)
cd dashboard
npm install
npx playwright test --workers=1
```

Two things to know about it: it runs against **your local** services, never the live deployment, and it makes real AI calls, so running it spends a little API credit. Always use `--workers=1` — Playwright's default parallel run fires many real LLM requests at once and makes the suite flaky against a local API.

---

## Key Decisions (and Why)

| Decision | Why |
|---|---|
| **Never a flat yes/no** | A decision with no explanation can't be trusted or checked. Every answer comes with a direct quote as proof. |
| **No confidence score, anywhere** | We deliberately left this out. A percentage score can feel more certain than it actually is, and it was explicitly ruled out during planning. |
| **A human always makes the final call** | Even a clean "everything matches" case still needs a person to make a real decision — Accept or Deny — or deliberately flag it for more review. Nothing is ever decided by the AI alone. This is enforced in the code itself — there's no way around it. |
| **Rules are written by hand, not read from a PDF automatically** | Automatically parsing rules out of messy trial documents is a much bigger, riskier problem. For now, a human converts the rulebook into a clean checklist first. |
| **Exclusion rules are phrased as plain statements, not "must not" rules** | Testing showed the AI reasoning got confused by double-negatives. "Patient is taking Warfarin" works much better than "Patient must not be taking Warfarin." |
| **When information is missing, the AI says so — it doesn't guess** | A wrongly excluded patient never gets a second chance. Being cautious costs less than being wrong. |
| **A real database, not just memory** | Early versions lost everything on restart. A tool coordinators actually rely on can't forget their decisions. Data now lives in hosted Postgres on Supabase. |

---

## Real Problems We Found and Fixed

Building this surfaced some genuine bugs — the useful kind, found and fixed before this ever touched anything real:

1. **Confusing rule wording tripped up the AI.** Rules phrased as "must not be taking X" caused wrong answers almost every time. Fixed by rephrasing rules as plain statements instead.
2. **The AI guessed too confidently when information was simply missing.** "No screening on file" was being read as "doesn't have the condition." Fixed by explicitly telling the AI to say "unclear" instead of guessing.
3. **A single bad AI response could crash the whole check.** Now, if the AI's answer doesn't fit the expected format, that one rule safely falls back to "unclear" instead of breaking everything.
4. **A leftover test service was quietly stealing web traffic meant for the real system**, because both were using the same computer port. Fixed by removing the old service entirely and building monitoring directly into the real system instead.
5. **The app forgot everything every time it restarted.** All trials and assessments lived only in memory. Fixed by adding a real SQLite database — tested by actually killing the running server process and confirming the data survived. That database was later moved to hosted Postgres on Supabase (see [project_summary.md](./project_summary.md)), so the data now survives a hard kill of the whole app machine too.

*(Full details of each issue, exactly what caused it and how it was proven fixed, are in [project_summary.md](./project_summary.md).)*

---

## How Well Does It Actually Work?

Since we didn't have a real hospital to test with, we ran a stand-in test: **12 made-up patients, each with a known correct answer, run through the real AI.**

**Result: 12 out of 12 correct. Zero patients wrongly excluded.**

This included tricky cases on purpose — patients right at an age cutoff, patients failing multiple rules at once, and irrelevant information mixed in to see if it would cause confusion. All handled correctly.

**Being honest about the limits:** 12 patients is a good sign, not final proof. A real trial usually has more rules than the 3 we tested with, and real patient records are messier than our clean test examples.

---

## What's Not Built

Two things are intentionally left for later, because they need more than code to finish:

- **Legal & security review** — getting the paperwork and security testing done to safely handle real patient data. This needs real lawyers and real security auditors.
- **Turning this into an actual product** — onboarding real hospitals, handling many trials at once, figuring out pricing. This needs a real business, not more engineering.

Everything else — the AI reasoning, the API, the database, the dashboard, monitoring, logging, tracing, and testing — is built, working, and verified.