# CareMatch — Monitoring Guide

*What the health numbers mean, and how to look at them yourself. A companion to `setup_guide.md` and `seed_data.md` — read those first to get the app running, then come back here.*

---

## What Prometheus Is

Prometheus is the app's **memory for numbers**. While CareMatch runs, it quietly records things like *how many eligibility checks have run, how long each one took, and how many times coordinators accepted, denied, or flagged a patient for more review*. It answers the question: **"Is the system healthy, day to day?"**

There are two other ways to look at what the app did, and it helps to know which one to reach for:

- **The request logs** (each request gets its own `X-Request-ID`): *"What happened on this one exact request?"* — the tool for tracing a single problem.
- **LangSmith** (only if you turned tracing on): *"Why did the AI decide what it decided?"* — it stores the actual reasoning behind every rule.
- **Prometheus**: *"How is the whole system doing over time?"* — the big-picture health numbers.

You don't have to start Prometheus or do anything to make it record. It starts itself when you run the command below, and it checks on the app automatically every 15 seconds:

```
docker compose up -d --build
```

---

## Looking at Prometheus Yourself

1. Make sure the app is running (click to copy):

   ```
   docker compose up -d --build
   ```

2. Open **http://localhost:9090** in your browser.
3. Click **Status** in the menu at the top, then **Targets**.

You should see three rows:

| Job | What it watches | Healthy if |
|---|---|---|
| `carematch-api` | Your **local** API (`http://api:8000`) — the engine behind the app when you run it with `docker compose` | green dot + **UP** |
| `carematch-api-live` | The **deployed** CareMatch API on Google Cloud Run — its public `/metrics` endpoint | green dot + **UP** |
| `carematch-prometheus` | Prometheus watching itself | green dot + **UP** |

A healthy screen shows all rows with a green circle and the word **UP**. If a row shows red and **DOWN**, something is wrong — most commonly the local API isn't running (start it again), or a service just restarted (a new Cloud Run revision, or waking from scale-to-zero) and Prometheus hasn't re-checked yet. It re-checks every 15 seconds, so give it a moment before worrying.

### What it scrapes — your local dev API and the deployed one

`prometheus_config.yml` has three jobs: one scrapes your **local** API (so anyone who clones the repo and runs `docker compose up -d --build` gets a working dashboard with no extra config), one scrapes the **deployed** Cloud Run API, and the last watches Prometheus itself:

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

**If you deploy your own instance, update the `carematch-api-live` target.** The address `carematch-api-726123996575.us-central1.run.app` is *this project's* live URL. If someone clones the repo and deploys their own separate instance of the API, they must change that target to their own address — otherwise their Prometheus would silently scrape the original team's deployment by default, and the "deployed" charts wouldn't be their app at all.

After editing `prometheus_config.yml`, reload it into the running container (the file is bind-mounted, so no rebuild is needed):

```
docker compose restart prometheus
```

A few things worth knowing:

- **Which numbers you're seeing.** Queries tagged `job="carematch-api"` answer questions about your local API; `job="carematch-api-live"` answers them about the deployed one — the same real system users hit, with real Supabase Postgres and real Anthropic calls. A bare query like `assessments_total` merges both together, so use `{job="carematch-api-live"}` (or put `{{job}}` in a Grafana legend) when you want only the deployed API.
- **The local row shows DOWN until you run the stack.** The `carematch-api` job scrapes `api:8000`, a Docker-network address that only exists while `docker compose up` is running. Before you start it (or after you stop it) that row is red — expected.
- **Counters reset per process instance.** Counters like `assessments_total` or `trials_registered_total` only count since the current process started. When Cloud Run deploys a new revision or the service wakes from scale-to-zero, the deployed API's numbers start back at zero — even though the database still has all the data. `http_requests_total` (and its `rate(...)`) shows live traffic immediately, because Prometheus's own scrape every 15 seconds counts as a request.
- **Only while your machine runs.** Prometheus and Grafana live in your local Docker stack. The scraping happens from your computer, so it records only while `docker compose` is up — it is not a 24/7 hosted monitoring service.
- **Scraping keeps the deployed instance warm.** Because Prometheus hits the live `/metrics` every 15 seconds, the deployed API can't fully sleep between real users. Harmless at this scale, but the live instance will never be completely idle.

---

## Running a Query in Prometheus

The main page of Prometheus (**http://localhost:9090**) has a box at the top where you can type questions. Type one of these (click to copy), then click **Execute** (or press Enter):

```
assessments_total
```

The total number of eligibility checks that have ever run.

```
rate(assessments_total[5m])
```

The average number of checks per second over the last 5 minutes — the "is anyone using the app right now?" number.

```
trials_registered_total
```

How many trials have been set up on the Trial Setup page.

```
coordinator_decisions_total
```

How many coordinator decisions have been recorded (Accept, Deny, or Needs More Review).

The four guardrail metrics below are the system's own honesty counters — how often its safety checks fired. The first three are **input guardrails**, checked before anything is sent to the AI; the last one is the **output guardrail**, checked after the AI answers.

```
input_length_rejected_total
```

How many patient records were rejected before reaching the AI because they were over the 10,000-character limit.

```
input_pii_rejected_total
```

How many records were rejected because they looked like they contained personal information — an SSN-format number, an email address, or a phone number. The error message never echoes the matched value back.

```
input_injection_rejected_total
```

How many records were rejected because they looked like they contained prompt-injection-style instructions (for example, "ignore previous instructions").

```
hallucinated_evidence_caught_total
```

How many times the output guardrail caught the AI quoting evidence that isn't actually in the patient record. Each one was overridden to `unclear` instead of trusting a possibly made-up quote. This is the most important guardrail metric: it's the system's own count of its AI hallucinating, so a number above zero is worth looking at.

**Why a brand-new install shows mostly zeros:** these are counting numbers. They start at zero and only go up as the app actually gets used. If you installed the app two minutes ago and haven't clicked anything yet, there's nothing to have counted — so you'll see `0`, or no result at all for `rate(...)`. A rate of change needs something to have changed. That is normal, not a fault. (See the troubleshooting note at the end.)

---

## What Grafana Is

Grafana is the **chart-maker**. Prometheus keeps the numbers; Grafana draws them as easy-to-read graphs and dashboards. It answers the question: **"What does that data look like over time?"** — without you having to type queries by hand.

---

## Logging Into Grafana

1. Open **http://localhost:3000** in your browser.
2. Log in with username **admin** and password **admin**.
3. On a fresh install, Grafana will ask you to set a new password. You can set one (and remember it), or click **Skip** — either works.

---

## What You'll See When You Get There

CareMatch does **not** ship with a pre-built Grafana dashboard. When you start fresh — or after wiping your Docker volumes — Grafana will be empty: no dashboards, and no connection to Prometheus set up yet. That is expected. You have two paths:

- **If a dashboard already exists** (for example, you or a teammate built one earlier and the storage was never wiped): on the menu on the left, click **Dashboards** and open the one you saved. It fills itself in from Prometheus automatically.
- **If you're starting fresh** (the likely case): follow the next section once, and you never have to again.

---

## Connecting Grafana to Prometheus (One-Time, If Starting Fresh)

Grafana needs to be told where Prometheus is. This is the one slightly technical step, and the address matters:

1. In Grafana, on the menu on the left, go to **Connections → Data sources**.
2. Click **Add data source**, then choose **Prometheus**.
3. Find the **URL** box and type exactly (click to copy):

   ```
   http://prometheus:9090
   ```

   - **Why not `localhost`?** Grafana and Prometheus each run in their own box (a "container") inside Docker. To each of them, "localhost" means *their own* box — not yours, and not each other's. Inside Docker's own private network, Grafana reaches Prometheus by its service name: **`prometheus`**. If you typed `http://localhost:9090`, Grafana would search inside its own container, find nothing, and the connection would fail. Your browser uses `localhost` because your browser is *not* inside Docker — different world, different address.
4. Click **Save & test** at the bottom. You should see a green **"Successfully queried the Prometheus API"** message.

That's the whole connection. Now let's make one simple chart:

5. On the menu on the left, go to **Dashboards → New dashboard**, then click **Add visualization**.
6. It will ask which data source to use — pick **Prometheus**.
7. In the query box near the top, type (click to copy):

   ```
   rate(assessments_total[5m])
   ```

8. Click **Run queries**. You'll likely see an empty graph for now — that's fine. It means no assessments have run yet (see the end of this guide).
9. Click **Apply** (top right), then **Save dashboard**, give it a name like "CareMatch health", and click **Save** again.

You can add more panels the same way, using any of the other queries from the Prometheus section above.

*(The exact button wording can vary slightly between Grafana versions, but the steps are the same.)*

---

## Your Setup Is One-Time

Grafana's saved dashboards and Prometheus's recorded history are stored in **named volumes** (`grafana_data` and `prometheus_data`) — special storage that survives `docker compose down`. So once you've connected Prometheus and saved a dashboard, it stays: restart the app, shut it down overnight, even rebuild it, and your charts and history are still there next time. You do this setup once, not every day.

One catch: run `docker compose down` with **no extra flags** (click to copy):

```
docker compose down
```

If you run `docker compose down -v`, the `-v` means "delete the storage too" — that wipes the dashboards and history, and you'd have to do this whole setup again. Don't add `-v` unless you want to start over on purpose.

---

## Troubleshooting: "I See No Data / All Zeros"

The almost-always answer: **the app just hasn't been used yet.** These are counters — they only go up when the app actually does something. If you've just started CareMatch, nothing is recorded yet, so of course it's all zeros (or an empty graph for `rate(...)`).

The fix is easy — go make some real activity:

1. Open the app at **http://localhost:8080**.
2. Follow `seed_data.md` — set up the demo trial, then run a few of the sample patient assessments.
3. Come back to Prometheus or Grafana and refresh.

You should now see `assessments_total` above zero and the graph bumping. If it's *still* all zeros after real use, check the **Targets** screen from earlier in this guide: if a job shows **DOWN**, the API isn't being watched at all — and that's a different problem than "not used yet."

---

*This guide matches the actual configuration in `prometheus_config.yml` and `docker-compose.yml`: Prometheus runs at http://localhost:9090, Grafana at http://localhost:3000, and both keep their data in named volumes. Prometheus scrapes your local API (job `carematch-api`), the deployed Cloud Run API's public `/metrics` endpoint (job `carematch-api-live`), and itself (job `carematch-prometheus`). The whole setup is local-Docker-only — it records while your machine runs `docker compose`, not as a 24/7 hosted service.*
