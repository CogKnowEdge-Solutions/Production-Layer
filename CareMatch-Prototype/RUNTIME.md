# CareMatch — Operational Runbook

*What to do when something needs doing, or something goes wrong. This is different from `setup_guide.md` (first-time setup) and `monitoring_guide.md` (understanding metrics) — this document is for day-to-day operation and incident response, once the system is already running somewhere real.*

---

## 1. System Overview

CareMatch has 4 core pieces, plus 2 external services it depends on:

| Component | What It Is | Where It Lives |
|---|---|---|
| **Dashboard** | React/TanStack Start UI (coordinator-facing) | Docker container / Cloud Run |
| **API** | FastAPI backend — the reasoning loop, guardrails, persistence | Docker container / Cloud Run |
| **Prometheus** | Collects system health metrics | Docker container, **local only — deliberate decision, not yet deployed to any cloud service** |
| **Grafana** | Visualizes Prometheus metrics | Docker container, **local only — same as above** |
| **Supabase (Postgres)** | External — all persistent data (trials, assessments, decisions) | Hosted by Supabase |
| **Anthropic API** | External — the actual AI reasoning calls | Hosted by Anthropic |
| **LangSmith** (optional) | External — traces every real AI call | Hosted by LangSmith |

**Key fact to remember:** the API is stateless itself — all real data lives in Supabase, not on any local disk. This is why the API can be safely restarted, redeployed, or scaled without losing data.

---

## 2. Quick Reference — URLs, Ports, Commands

### Local (Docker Compose)

| What | Address |
|---|---|
| Dashboard | `http://localhost:8080` |
| API | `http://localhost:8000` |
| API docs (interactive) | `http://localhost:8000/docs` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` (admin/admin) |

### Start / stop everything locally

```bash
docker compose up -d --build
docker compose down
docker compose ps
docker compose logs api --tail 50
```

### Cloud Run (live production)

| What | Real URL |
|---|---|
| **Dashboard (live)** | `https://carematch-dashboard-726123996575.us-central1.run.app` |
| **API (live)** | `https://carematch-api-726123996575.us-central1.run.app` |

*(These URLs are stable across redeploys of the same service — only the revision ID changes underneath. If either service is ever deleted and recreated with a different name, this table needs updating.)*

```bash
# Deploy / redeploy the API
gcloud run deploy carematch-api --source . --region us-central1 --allow-unauthenticated --set-env-vars DATABASE_URL="...",ANTHROPIC_API_KEY="...",ANTHROPIC_MODEL="claude-haiku-4-5-20251001"

# Deploy / redeploy the dashboard
gcloud run deploy carematch-dashboard --source ./dashboard --region us-central1 --allow-unauthenticated

# Check current service status and URL
gcloud run services describe carematch-api --region us-central1
gcloud run services describe carematch-dashboard --region us-central1

# View live logs
gcloud run services logs read carematch-api --region us-central1 --limit 50
gcloud run services logs read carematch-dashboard --region us-central1 --limit 50
```

---

## 3. Health Checks — Is It Actually Working?

Run these in order. Stop at the first one that fails — that tells you where the problem is.

1. **Is the API reachable at all?**
   ```bash
   curl -s -w "\nHTTP %{http_code}\n" https://YOUR-CLOUD-RUN-URL/health
   ```
   Expect: `{"status":"ok"}` and `HTTP 200`.

2. **Is the database reachable?**
   ```bash
   curl -s https://YOUR-CLOUD-RUN-URL/trials
   ```
   Expect: a JSON array (empty `[]` is fine — that just means no trials exist yet). If this hangs or errors, the problem is the Postgres/Supabase connection, not the API itself.

3. **Is real AI reasoning working?** Run one real assessment (see `seed_data.md` for exact copy-paste values) and confirm you get a real `suggested_status` back, not an error.

4. **Are guardrails behaving correctly?** Try submitting a patient record containing a fake SSN-format string (e.g. `123-45-6789`) — you should get a `422` with `"Possible SSN detected in patient record."`, not a `500` or a silent pass-through.

---

## 4. Deployment Procedure

### Deploying a new version of the API to Cloud Run

1. Confirm all tests pass locally first — **never deploy untested code**:
   ```bash
   docker compose exec -T api python -m pytest -q
   ```
   Expect `20 passed`. If this isn't 20/20, stop and fix it before deploying.

2. Confirm your local `Dockerfile` (top-level, the Cloud Run one) genuinely includes `reasoning_engine/` — this exact thing broke once already (see Known Issue #7 below). Quick check:
   ```bash
   grep -A2 "COPY" Dockerfile
   ```
   You should see both `api` and `reasoning_engine` being copied in.

3. Deploy:
   ```bash
   gcloud run deploy carematch-api --source . --region us-central1 --allow-unauthenticated --set-env-vars DATABASE_URL="...",ANTHROPIC_API_KEY="..."
   ```

4. **Verify immediately after deploying** — don't just trust that "deploy succeeded" means it's actually working. Run the Health Checks in Section 3 against the new URL.

5. If anything fails, see the Rollback Procedure below **before** trying to debug live in production.

### Deploying a new version of the dashboard to Cloud Run

This has one extra gotcha the API doesn't have: **`VITE_API_BASE_URL` gets permanently baked into the frontend at build time**, not read later at runtime. If the API's URL ever changes, the dashboard must be rebuilt and redeployed — editing an environment variable on the already-deployed dashboard afterward does nothing.

1. Confirm `VITE_API_BASE_URL` is set to the real, current API URL (see the table above) before building.
2. Deploy:
   ```bash
   gcloud run deploy carematch-dashboard --source ./dashboard --region us-central1 --allow-unauthenticated
   ```
3. **After the dashboard has a URL, the API doesn't know about it yet.** Add the dashboard's real Cloud Run URL to `_default_allowed_origins` in `api/main.py`, then redeploy the API too. Skipping this step causes a CORS failure that looks like a broken backend but isn't — see Issue 5.1.
4. Verify end-to-end: open the real dashboard URL, register a trial, run one real assessment, confirm no CORS errors in the browser console and a genuine AI response comes back.

### Rollback Procedure

Cloud Run keeps previous revisions automatically. If a new deploy is broken:

```bash
# List recent revisions
gcloud run revisions list --service carematch-api --region us-central1

# Route 100% of traffic back to the last known-good revision
gcloud run services update-traffic carematch-api --region us-central1 --to-revisions PREVIOUS-REVISION-NAME=100
```

This is fast and safe — it doesn't delete the broken revision, it just stops sending traffic to it, so you can debug it later without pressure.

---

## 5. Common Issues and Fixes (Real Problems We Actually Hit)

This section only contains things that genuinely happened during this project's build and deployment — not hypothetical scenarios.

### 5.1 — "Couldn't reach the API to load trials" in the dashboard

**Likely cause:** CORS. The API only allows requests from origins explicitly listed in `api/main.py`'s `_default_allowed_origins`.

**Fix:** Add the dashboard's real deployed address to that list, rebuild, redeploy. Check the browser's DevTools Console (F12) — a genuine CORS block shows an explicit message: `"has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present."`

### 5.2 — Docker container can't connect to Supabase (`Network is unreachable`)

**Real cause found:** Supabase's *direct* connection hostname can be IPv6-only. Docker Desktop (on Windows/WSL2 at least) does not route IPv6 traffic out of containers, so the connection fails even though the connection string itself is correct.

**Fix:** Use Supabase's **connection pooler** string instead (port `6543`), not the direct connection (port `5432`). The pooler runs on normal IPv4-reachable addresses.

**How to confirm this is the actual problem:**
```bash
docker run --rm carematch-prototype-api python -c "import socket; print(socket.getaddrinfo('YOUR-SUPABASE-HOST', 5432, socket.AF_UNSPEC, socket.SOCK_STREAM))"
```
If this only returns `AF_INET6` addresses, this is the issue.

### 5.3 — LangSmith traces failing with `403 Forbidden`

**Real cause found:** Org-scoped "Service" API keys (starting `lsv2_sk_`) require an explicit `LANGSMITH_WORKSPACE_ID` — without it, every request is silently rejected.

**Fix:** Add `LANGSMITH_WORKSPACE_ID` to the environment. To find the real workspace ID:
```bash
curl -s https://api.smith.langchain.com/workspaces -H "x-api-key: YOUR_KEY"
```
Look for the `"id"` field in the response.

### 5.4 — Assessment rejected with a guardrail error the user doesn't understand

**This is by design, not a bug.** The API automatically rejects patient records containing SSN-format numbers, email addresses, phone numbers, or suspicious instructional text — *before* any AI call is made, to avoid cost and PII exposure.

**If a legitimate clinical note gets rejected:** check if it happens to contain something that looks like the above (e.g. a stray phone number in the text). This has happened before with ordinary clinical language matching an overly broad pattern — see Known Issue #6.

### 5.5 — `docker compose up --build` is extremely slow

**Real cause found once:** two completely unrelated packages (`gradio`, `spaces`) had accidentally been added to `api/requirements.txt`, dragging in ~50MB of unrelated dependencies (numpy, pandas, pillow, huggingface-hub).

**Fix:** Check `api/requirements.txt` only contains packages the project actually imports. If in doubt:
```bash
grep -rn "import gradio\|import spaces\|from gradio\|from spaces" .
```
If this returns nothing, those packages don't belong there.

### 5.6 — A guardrail is flagging genuine clinical language as suspicious

**Real cause found once:** an early version of the injection-detection pattern for `"system:"` flagged completely normal medical documentation like *"Review of systems: Cardiovascular system: regular rate and rhythm."*

**Fix:** Injection patterns in `reasoning_engine/guardrails.py` should only fire on *actual* instructional phrases following a suspicious word, not the bare word alone. If you add new patterns, always test them against realistic clinical language first, not just the attack you're trying to catch.

### 5.7 — Cloud Run deployment crashes on startup with `ImportError`

**Real cause found:** the API imports code from a sibling folder (`reasoning_engine/`) via a `sys.path.insert()` trick in `main.py`, rather than being a properly installed Python package. Any Dockerfile that only copies `api/` and installs `api/requirements.txt` — without also copying `reasoning_engine/` and installing *its* requirements — will build successfully but crash the moment the app actually starts.

**Fix:** the top-level `Dockerfile` must copy **both** folders and install **both** `requirements.txt` files. See Section 4, step 2 for how to verify this before deploying.

### 5.8 — Cloud Run deploy fails: "container failed to start and listen on the port defined by PORT"

**Real cause found, hit on both the API and dashboard deploys:** Cloud Run injects its own `PORT` environment variable (commonly `8080`) and requires the container to listen on *that*, not a hardcoded number. Both Dockerfiles originally hardcoded a fixed port matching local `docker-compose` usage (`8000` for the API, `8080` for the dashboard) — the dashboard happened to work by coincidence since its hardcoded number matched Cloud Run's default, which masked the same underlying problem until the API's mismatch made it obvious.

**Fix:** the container's startup command must read `$PORT` at runtime, falling back to the local default only when `PORT` isn't set — e.g. `--port ${PORT:-8000}`. Test this locally before redeploying by explicitly running the built image with `-e PORT=8080` (or a different number, like `3000`, to rule out a lucky coincidence) and confirming it actually listens there.

**The build succeeding is not proof this works** — this exact error only shows up at container *startup*, after a fully successful build. Always verify locally with an explicit non-default `PORT` before trusting a Cloud Run deploy will succeed.

### 5.9 — `docker compose up` shows all 4 services "Up" but something's still wrong

**Real cause found:** a leftover, unrelated process was still running on the same port as the real API, silently intercepting traffic meant for Docker.

**Fix (Windows):**
```bash
netstat -ano | findstr :8000
taskkill /PID <the-real-PID> /F
```
Then restart Docker normally.

### 5.10 — `gcloud init` fails a network reachability check

**Real cause found:** this specific pre-flight check is known to be overly strict and can fail even when the actual connection works fine.

**Fix:** When prompted *"Would you like to continue anyway?"*, answer `y`. If the subsequent login and project-selection steps work normally, the earlier failure was a false alarm.

---

### 5.11 — Assessment Review immediately shows Accept/Deny again right after flagging "Needs More Review"

**Expected fix, already in place — not a bug if you're seeing the correct behavior.** Clicking "Needs More Review" should show a clean confirmation message with no buttons, immediately after submitting. The Accept/Deny buttons should only reappear if a coordinator navigates away and comes back to that same assessment later — that's the intended "come back and finish this" moment, not the moment right after flagging it.

**If the buttons ARE reappearing immediately after submitting** (not on a later revisit), that's a real regression of this fix — check `dashboard/src/routes/review.tsx` for the flag distinguishing "just submitted in this session" from "loaded fresh with an existing needs_more_review status."

## 6. Database Operations

**Never connect directly to the `public` schema for testing.** The test suite already handles this correctly — it creates a throwaway `carematch_test` schema, runs everything there, and drops it afterward. Don't manually run test data against `public`.

**To check real data directly** (read-only, be careful):
```bash
psql "YOUR_DATABASE_URL"
```
or via a quick Python script using `psycopg2`, matching the pattern already used throughout this project's verification steps.

**Never drop the `public` schema.** That's where all real production data lives.

**A note on decision values, if you're reading raw rows.** The `decision` column only accepts 3 values going forward (`accepted`, `denied`, `needs_more_review`), but a handful of older rows may still contain the original 2-value system (`approved`, `overridden`) from before the redesign. This is expected and handled correctly by the app (it reads old values without crashing), but if you're querying the database directly and see one of these older values, that's not a bug — it's real history from before the decision system was redesigned.

---

## 7. Environment Variables Reference

| Variable | Required? | Notes |
|---|---|---|
| `DATABASE_URL` | Always | Use the Supabase **pooler** string (port 6543), not the direct connection (port 5432) — see Issue 5.2 |
| `ANTHROPIC_API_KEY` | Always | Real cost is incurred per assessment |
| `ANTHROPIC_MODEL` | No (has default) | Currently `claude-haiku-4-5-20251001` |
| `CAREMATCH_DB_SCHEMA` | No (defaults to `public`) | Only override for testing |
| `LANGSMITH_TRACING` | No | Set `true` to enable |
| `LANGSMITH_API_KEY` | Only if tracing is on | |
| `LANGSMITH_WORKSPACE_ID` | Only if using an org-scoped Service key | See Issue 5.3 |

---

## 8. Monitoring — Current State

Prometheus and Grafana themselves are **intentionally not deployed to the cloud** — a deliberate decision, not an oversight. Cloud Run's stateless containers don't naturally support the persistent storage both tools need, and the added complexity/cost wasn't judged worth it at this stage.

**However, local Prometheus now watches both the local and the live API.** `prometheus_config.yml` has 3 scrape jobs:

```yaml
scrape_configs:
  - job_name: "carematch-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["api:8000"]
  - job_name: "carematch-api-live"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["carematch-api-726123996575.us-central1.run.app"]
  - job_name: "carematch-prometheus"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["localhost:9090"]
```

**What this means practically:** whenever `docker compose up -d` is running locally, Grafana shows real metrics from **both** the local dev API and the real, live, publicly-used deployed API — side by side, at zero extra cost. Reload the config after any edit with `docker compose restart prometheus` (no rebuild needed, the file is bind-mounted).

**Three things worth knowing when reading these numbers:**

1. **Keep the two sets of numbers separate.** Both jobs report metrics under the same names (e.g. `assessments_total`). A bare query merges both together — use `{job="carematch-api-live"}` (or `{job="carematch-api"}`) to isolate one or the other.
2. **Counters reset on every fresh Cloud Run process.** Custom counters live in the API's memory, not the database. A new deploy, or waking from scale-to-zero, resets them to zero — even though the database still has all the real historical data. Not a bug.
3. **Scraping the live API keeps it from fully resting.** Because Prometheus checks in every 15 seconds, Cloud Run never gets a long enough gap to scale that instance to zero. Harmless for occasional local dev sessions; worth knowing if the local stack is ever left running for many hours or days straight.

**One important limitation, unchanged:** this only records data while your own machine is running `docker compose up`. It is not a 24/7 hosted monitoring service. If that's ever needed, revisit the options considered: Google's built-in Cloud Monitoring (free, zero setup, already collecting basic Cloud Run metrics automatically with no configuration at all), a managed Grafana Cloud account, or a small dedicated VM.

**A note for anyone deploying their own separate copy of this project:** the `carematch-api-live` target above points at this specific team's deployed URL. Update it to your own deployed address, or your local Prometheus will scrape the original team's deployment instead of yours.

## 9. Cost & Billing

- A real credit card is on file with GCP (confirmed via the "Paid account" badge in Billing).
- **Confirmed via GCP's own billing dashboard**: real, actual cost for this entire project's deployment and testing work has been **zero (0.00 Indian Rupees)**, for the full billing period checked — not an estimate, a real number pulled directly from Google's own Cost Summary and Reports pages.
- **A budget alert has been set up** as an automatic safety net — an email trigger the moment spending crosses a small threshold, rather than relying on manually checking.
- If a billing report ever looks alarming, check which **service** the charge is actually under before worrying — a "Gemini API" / "Vertex AI" cost report was once mistaken for a CareMatch charge, when it was actually a small, old, unrelated charge from a completely different Google AI product that this project has never used (CareMatch only ever calls Anthropic's API, never Google's Gemini/Vertex). Always confirm the charge is under **Cloud Run**, **Cloud Build**, or **Artifact Registry** specifically before treating it as this project's cost.
- No domain name has been purchased — the app currently runs on Cloud Run's default `*.run.app` addresses, which are free.

## 10. Escalation

If something is broken and the fixes in Section 5 don't resolve it:

1. Check `project_summary.md` — it documents the full history of real bugs found and fixed throughout development, which may cover the issue in more depth.
2. Check the relevant service's own status page (Supabase status, Anthropic status, GCP status) — sometimes it's not your system at all.
3. If it's a genuinely new issue, document it the same way every issue in this runbook was documented: **what broke, the real error message, the actual root cause, and the actual fix** — then add it here for the next person.

---

*This runbook reflects real issues actually encountered during CareMatch's build and deployment — not hypothetical scenarios. Keep it that way: when something new breaks, add it here with the real details, not a generic placeholder.*