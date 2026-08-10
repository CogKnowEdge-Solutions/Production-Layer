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

## Step 2 — Real AI Is the Normal Way to Run CareMatch

**Important thing to know:** CareMatch is built to run with **real AI** — that is the normal configuration and what any real user (or client demo) should see. There is also a **free developer testing mode** (`LLM_MODE=fake`) that returns placeholder answers instead of asking the AI. That mode exists so the automated test suite and plumbing checks cost nothing — it is **not** the mode you run the app in for a real demo.

**For any real use or demo, continue to Step 3 — real AI with a valid API key is the expected setup.**

---

## Step 3 — (Optional) Set Up Real AI

1. In the top-level folder, find the file called `.env.example`. Make a copy of it in the same folder, and rename the copy to exactly `.env` (no `.example` at the end).
2. Open `.env` in a text editor.
3. Get a free or paid API key from [console.anthropic.com](https://console.anthropic.com) (click around for "API Keys").
4. In your `.env` file, change these two lines:
   ```
   LLM_MODE=real
   ANTHROPIC_API_KEY=paste-your-real-key-here
   ```
5. Save the file.

**Optional, extra step — AI tracing/evaluation (LangSmith):** if you also want a permanent, browsable history of every single AI decision the app makes, get a free account and API key at [smith.langchain.com](https://smith.langchain.com), then add to the same `.env` file:
```
LANGSMITH_API_KEY=paste-your-key-here
LANGSMITH_TRACING=true
```
This step is entirely optional — the app works completely fine without it.

**Nothing here is required just to start the app** — but for any real use or demo, `LLM_MODE=real` with a valid key is the expected configuration. Without a key, assessments fail loudly with an error rather than silently returning placeholder answers; the app never fakes a result by accident. The free developer testing mode is reserved for running the automated test suite, not for demos.

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

Real AI is the normal configuration. Create a file named `.env` right here inside the `api` folder (not the top-level one — this backend reads its own local `.env`) with:
```
LLM_MODE=real
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

This is the actual app — the screen a hospital coordinator would use. You should see a page called "New Assessment." Across the top is a navigation bar with four tabs: **New Assessment**, **Assessment Review**, **Trial Setup**, and **Trials** (which lists every registered trial and its rules). This address is the same either way, Docker or manual.

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

**I set up a real API key, but it's still not doing real AI reasoning**
→ Docker: double-check the top-level `.env` has `LLM_MODE=real`, then run `docker compose up -d --build` again.
→ Manual setup: double-check `api/.env` (not the top-level one) has `LLM_MODE=real`, then restart `uvicorn` (`Ctrl+C`, then run it again).