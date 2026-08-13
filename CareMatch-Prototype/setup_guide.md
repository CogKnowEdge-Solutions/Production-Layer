# CareMatch — Setup Guide

Step-by-step instructions to get CareMatch running on your own computer, from nothing to a working app. Written so that someone with basic computer skills (not necessarily a programmer) can follow it.

---

## Before You Start

You need one thing installed: **Docker Desktop**. This is the only requirement — Docker handles installing everything else (Python, Node.js, the database, the monitoring tools) automatically, inside isolated containers, so nothing else needs to be installed directly on your computer.

- Download it from [docker.com](https://www.docker.com/products/docker-desktop/)
- Install it, then **open the Docker Desktop app** and leave it running in the background. Every command below will fail if this app isn't open.

---

## Step 1 — Get the Code

If you haven't already, download or clone the project folder onto your computer. You should see folders like `api/`, `dashboard/`, `reasoning_engine/`, and a file called `docker-compose.yml` at the top level.

Open a terminal (Command Prompt, PowerShell, or Terminal) and navigate into that top-level folder — the one containing `docker-compose.yml`.

---

## Step 2 — CareMatch Always Runs with Real AI

**Important thing to know:** CareMatch always runs with **real AI** — that is the only configuration. Every assessment makes a real call to an AI model and uses a small amount of API credits. There is no test/fake mode in the app itself. (The automated test suite is the one exception: it substitutes a mock for the AI call from inside the test file, so running the tests never costs anything and never touches the real API.)

**To run the app you need a valid API key — continue to Step 3.**

---

## Step 3 — Set Up Real AI

1. In the top-level folder, find the file called `.env.example`. Make a copy of it in the same folder, and rename the copy to exactly `.env` (no `.example` at the end).
2. Open `.env` in a text editor.
3. Get a free or paid API key from [console.anthropic.com](https://console.anthropic.com) (click around for "API Keys").
4. In your `.env` file, change this line:
   ```
   ANTHROPIC_API_KEY=paste-your-real-key-here
   ```
5. Save the file.

**Optional, extra step — AI tracing/evaluation (LangSmith):** if you also want a permanent, browsable history of every single AI decision the app makes, get a free account and API key at [smith.langchain.com](https://smith.langchain.com), then add to the same `.env` file:
```
LANGSMITH_API_KEY=paste-your-key-here
LANGSMITH_TRACING=true
```
This step is entirely optional — the app works completely fine without it.

**One important gotcha if you use a "Service" key:** LangSmith has two kinds of API keys, and they behave differently:
- **Personal keys** start with `lsv2_pt_` — these work with just the `LANGSMITH_API_KEY` line above. Nothing more needed.
- **Service (org) keys** start with `lsv2_sk_` — these are scoped to a specific workspace, and **without an explicit workspace ID LangSmith rejects every request with a confusing `403 Forbidden` error**. If your key starts with `lsv2_sk_`, you must also find your workspace ID and add it.

**How to find your workspace ID (only if your key is a Service key):** in LangSmith, go to **Settings**, then look at the **API Keys** page. Your workspace ID is shown in the LangSmith settings/workspace area (it's a short identifier like `carematch-prototype`). Then add a line to the same `.env` file:
```
LANGSMITH_WORKSPACE_ID=your-own-workspace-id-here
```
That one extra line is what fixes the `403 Forbidden` — without it, a Service key simply won't work, and the error message LangSmith gives you doesn't say why.

### Finding Your Workspace ID the Reliable Way

LangSmith's website doesn't have an obvious place that shows your workspace ID directly — it can be surprisingly hard to find by clicking around. The most reliable way is to ask LangSmith's own servers directly with one command. It asks the server "which workspaces does this key belong to?", and the answer includes the exact ID you need.

**For PowerShell (most common on Windows):**

```
curl.exe -s -w "`nHTTP status: %{http_code}`n" https://api.smith.langchain.com/workspaces -H "x-api-key: YOUR_LANGSMITH_API_KEY_HERE"
```

**For Mac, Linux, or Windows Command Prompt:**

```
curl -s -w "\nHTTP status: %{http_code}\n" https://api.smith.langchain.com/workspaces -H "x-api-key: YOUR_LANGSMITH_API_KEY_HERE"
```

How to read the result:

1. **Replace `YOUR_LANGSMITH_API_KEY_HERE` with your real key** from your `.env` file (the value of the `LANGSMITH_API_KEY=...` line) before running the command.
2. **On Windows, this must be run in PowerShell using `curl.exe` specifically** — not plain `curl`. Plain `curl` secretly runs a different Windows command (`Invoke-WebRequest`) that doesn't understand this syntax and will show a confusing error like `Missing an argument for parameter 'SessionVariable'`. Using `curl.exe` (with the `.exe` on the end) makes PowerShell use the real curl program, which works.
3. **A successful run shows real JSON text ending in `HTTP status: 200`.** Inside that JSON, look for a field called `id` — that long string (something like `3d46e6ff-4cba-4827-a504-b69772d9b27c`) is your workspace ID. Copy that value into the `LANGSMITH_WORKSPACE_ID=` line in your `.env` file.

**Nothing here is required just to start the app** — but without a key, assessments fail loudly with an error rather than silently returning placeholder answers; the app never fakes a result by accident.

---

## Step 4 — Start Everything

You have two options here: the easy way (Docker), or a manual way if you'd rather not install Docker at all. Both are real, working options — pick whichever suits you.

### Option A — With Docker (Recommended, Easiest)

```bash
docker compose up -d --build
```

The first time you run this, it'll take a few minutes — it's downloading and building everything. Every time after that, it'll be much faster.

### Option B — Without Docker (Manual Setup)

This runs the exact same code, just installed directly on your computer instead of inside containers. A bit more setup, but works identically. **Note:** this simpler path does not include the Prometheus/Grafana monitoring dashboards — those are Docker-only in this guide, since they're separate applications, not something `pip` or `npm` installs.

**You'll need installed directly on your computer:**
- Python 3.12 or newer
- Node.js (any recent version)

**1. Set up and start the backend:**
```bash
cd api
pip install -r requirements.txt -r ../reasoning_engine/requirements.txt
```

Every assessment makes a real AI call. Create a file named `.env` right here inside the `api` folder (not the top-level one — this backend reads its own local `.env`) with:
```
ANTHROPIC_API_KEY=your-real-key-here
```

Then start it:
```bash
uvicorn main:app --reload
```
Leave this terminal window open and running. You should see `Application startup complete.`

**2. In a second, separate terminal window, set up and start the frontend:**
```bash
cd dashboard
npm install
npm run dev
```
This will print a local address (usually `http://localhost:8080`) — open that in your browser.

Both terminal windows need to stay open while you're using the app. Closing either one stops that half of the app.

---

## Step 5 — Check It Actually Worked

**If you used Option A (Docker):**
```bash
docker compose ps
```
You should see **4 things** listed, each saying **"Up"**: `api`, `dashboard`, `prometheus`, `grafana`.

**If you used Option B (manual setup):**
Check both terminal windows — the backend one should say `Application startup complete.`, and the frontend one should show a local address with no errors.

If something doesn't look right, see the Troubleshooting section at the bottom.

---

## Step 6 — Open the App

In your web browser, go to:

**`http://localhost:8080`**

This is the actual app — the screen a hospital coordinator would use. You should see a page called "New Assessment." Across the top is a navigation bar with five tabs: **New Assessment**, **Assessment Review**, **Trial Setup**, **Trials** (which lists every registered trial and its rules), and **Assessment History** (which lists every assessment ever run, newest first, and opens any one of them with a click). This address is the same either way, Docker or manual.

---

## Step 7 — Try It Out

See the separate file `seed_data.md` for exact copy-paste examples of what to type in — trial rules and patient records — with the expected correct answer for each, so you can check the app is working correctly with your own eyes.

---

## Other Useful Pages, While the App Is Running

| What | Address | What You'll See |
|---|---|---|
| The main app | `http://localhost:8080` | The coordinator's screen |
| API documentation | `http://localhost:8000/docs` | A technical, interactive list of everything the app can do behind the scenes |
| Prometheus | `http://localhost:9090` | Raw system health numbers (mostly for technical debugging) |
| Grafana | `http://localhost:3000` | A nicer visual dashboard of those same health numbers (login: `admin` / `admin`) |

Want click-by-click instructions for Prometheus and Grafana? See `monitoring_guide.md`.

---

## Stopping the App

**If you used Docker:**
```bash
docker compose down
```
This stops everything cleanly. **Your data is not lost** — trial records, patient assessments, and your saved Grafana dashboards are all kept safely and will still be there next time.

To start it again later:
```bash
docker compose up -d
```
(No `--build` needed unless the code itself changed.)

**If you used the manual (non-Docker) setup:** just close both terminal windows, or press `Ctrl+C` in each one. Your trial and assessment data is still safely saved in a file (`api/data/carematch.db`) and will be there next time you run `uvicorn main:app --reload` again.

---

## Troubleshooting

**"Cannot connect to Docker daemon" or similar error**
→ Docker Desktop isn't open. Open the Docker Desktop application and wait for it to fully start, then try again. (Only relevant if you chose Option A.)

**One of the 4 Docker services doesn't say "Up"**
→ Run `docker compose logs <service-name>` (e.g. `docker compose logs api`) to see what went wrong, and check that error message.

**Manual setup: the backend terminal shows an import error**
→ Make sure you ran the `pip install` command exactly as shown, with **both** requirements files listed — the app needs packages from both `api/requirements.txt` and `reasoning_engine/requirements.txt` to work.

**Port already in use**
→ Something else on your computer is already using one of the ports (8000, 8080, or — Docker only — 9090, 3000). Close whatever that is, or ask for help changing the port.

**Assessments fail with an error even though I added an API key**
→ Docker: double-check the top-level `.env` has a valid `ANTHROPIC_API_KEY`, then run `docker compose up -d --build` again.
→ Manual setup: double-check `api/.env` (not the top-level one) has the same, then restart `uvicorn` (`Ctrl+C`, then run it again).

**My assessment was rejected — "Possible SSN detected in patient record" (or similar)**
→ CareMatch runs input guardrails before anything is sent to the AI, and if one fires, the API refuses the record with a clean error (HTTP 422) and a message like **"Possible SSN detected in patient record."**, **"Possible email address detected in patient record."**, **"Possible phone number detected in patient record."**, or **"Suspicious instructional content detected in patient record field."** — or a length message for records over 10,000 characters. The message deliberately never shows the exact text that triggered it. If a real patient record trips this, look inside the record you pasted for an SSN-format number, an email address, a phone number, or instruction-like wording (for example "ignore previous instructions"), remove it, and re-run. These checks are described in `monitoring_guide.md`.