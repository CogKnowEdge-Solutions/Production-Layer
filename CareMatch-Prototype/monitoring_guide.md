# CareMatch — Monitoring Guide

*What the health numbers mean, and how to look at them yourself. A companion to `setup_guide.md` and `seed_data.md` — read those first to get the app running, then come back here.*

---

## What Prometheus Is

Prometheus is the app's **memory for numbers**. While CareMatch runs, it quietly records things like *how many eligibility checks have run, how long each one took, and how many times coordinators accepted, denied, or flagged a patient for more review*. It answers the question: **"Is the system healthy, day to day?"**

There are two other ways to look at what the app did, and it helps to know which one to reach for:

- **The request logs** (each request gets its own `X-Request-ID`): *"What happened on this one exact request?"* — the tool for tracing a single problem.
- **LangSmith** (only if you turned tracing on): *"Why did the AI decide what it decided?"* — it stores the actual reasoning behind every rule.
- **Prometheus**: *"How is the whole system doing over time?"* — the big-picture health numbers.

You don't have to start Prometheus or do anything to make it record. It starts itself when you run `docker compose up -d --build`, and it checks on the app automatically every 15 seconds.

---

## Looking at Prometheus Yourself

1. Make sure the app is running (`docker compose up -d --build`).
2. Open **http://localhost:9090** in your browser.
3. Click **Status** in the menu at the top, then **Targets**.

You should see two rows:

| Job | What it watches | Healthy if |
|---|---|---|
| `carematch-api` | The API itself — the engine behind the app | green dot + **UP** |
| `carematch-prometheus` | Prometheus watching itself | green dot + **UP** |

A healthy screen shows both rows with a green circle and the word **UP**. If a row shows red and **DOWN**, something is wrong — most commonly the app isn't running (start it again), or the API just restarted and Prometheus hasn't re-checked yet. It re-checks every 15 seconds, so give it a moment before worrying.

---

## Running a Query in Prometheus

The main page of Prometheus (**http://localhost:9090**) has a box at the top where you can type questions. Type one of these, then click **Execute** (or press Enter):

| Query | What it shows |
|---|---|
| `assessments_total` | The total number of eligibility checks that have ever run. |
| `rate(assessments_total[5m])` | The average number of checks per second over the last 5 minutes — the "is anyone using the app right now?" number. |
| `trials_registered_total` | How many trials have been set up on the Trial Setup page. |
| `coordinator_decisions_total` | How many coordinator decisions have been recorded (Accept, Deny, or Needs More Review). |

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
3. Find the **URL** box and type exactly: `http://prometheus:9090`
   - **Why not `localhost`?** Grafana and Prometheus each run in their own box (a "container") inside Docker. To each of them, "localhost" means *their own* box — not yours, and not each other's. Inside Docker's own private network, Grafana reaches Prometheus by its service name: **`prometheus`**. If you typed `http://localhost:9090`, Grafana would search inside its own container, find nothing, and the connection would fail. Your browser uses `localhost` because your browser is *not* inside Docker — different world, different address.
4. Click **Save & test** at the bottom. You should see a green **"Successfully queried the Prometheus API"** message.

That's the whole connection. Now let's make one simple chart:

5. On the menu on the left, go to **Dashboards → New dashboard**, then click **Add visualization**.
6. It will ask which data source to use — pick **Prometheus**.
7. In the query box near the top, type: `rate(assessments_total[5m])`
8. Click **Run queries**. You'll likely see an empty graph for now — that's fine. It means no assessments have run yet (see the end of this guide).
9. Click **Apply** (top right), then **Save dashboard**, give it a name like "CareMatch health", and click **Save** again.

You can add more panels the same way, using any of the other queries from the Prometheus section above.

*(The exact button wording can vary slightly between Grafana versions, but the steps are the same.)*

---

## Your Setup Is One-Time

Grafana's saved dashboards and Prometheus's recorded history are stored in **named volumes** (`grafana_data` and `prometheus_data`) — special storage that survives `docker compose down`. So once you've connected Prometheus and saved a dashboard, it stays: restart the app, shut it down overnight, even rebuild it, and your charts and history are still there next time. You do this setup once, not every day.

One catch: run `docker compose down` with **no extra flags**. If you run `docker compose down -v`, the `-v` means "delete the storage too" — that wipes the dashboards and history, and you'd have to do this whole setup again. Don't add `-v` unless you want to start over on purpose.

---

## Troubleshooting: "I See No Data / All Zeros"

The almost-always answer: **the app just hasn't been used yet.** These are counters — they only go up when the app actually does something. If you've just started CareMatch, nothing is recorded yet, so of course it's all zeros (or an empty graph for `rate(...)`).

The fix is easy — go make some real activity:

1. Open the app at **http://localhost:8080**.
2. Follow `seed_data.md` — set up the demo trial, then run a few of the sample patient assessments.
3. Come back to Prometheus or Grafana and refresh.

You should now see `assessments_total` above zero and the graph bumping. If it's *still* all zeros after real use, check the **Targets** screen from earlier in this guide: if a job shows **DOWN**, the API isn't being watched at all — and that's a different problem than "not used yet."

---

*This guide matches the actual configuration in `prometheus_config.yml` and `docker-compose.yml`: Prometheus runs at http://localhost:9090, Grafana at http://localhost:3000, and both keep their data in named volumes.*
