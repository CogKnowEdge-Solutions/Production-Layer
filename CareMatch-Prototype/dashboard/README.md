# CareMatch — Dashboard (Phase 3)

The coordinator-facing dashboard for CareMatch's clinical trial eligibility
review tool. Wired to the real backend (the FastAPI service in `api/`).

## Development

```sh
npm install
npm run dev
```

The dev server runs on `http://localhost:8080` and talks to the local API on
`http://localhost:8000`. The API URL comes from `VITE_API_BASE_URL`
(`dashboard/src/lib/api.ts`), defaulting to `http://localhost:8000`.

## Tests

Playwright end-to-end suite in `tests/` that drives the real UI against the
local stack (dashboard on 8080, API on 8000 — e.g. via `docker compose`):

```sh
npx playwright test --workers=1
```

Always use `--workers=1`: the suite makes real LLM calls, and Playwright's
default parallel workers fire many assessments at once, which makes the suite
flaky against a local API. The current spec (`needs-more-review.spec.ts`)
covers the "Flag for further review" confirmation flow.

## Deployment (Cloud Run)

The `Dockerfile` builds a TanStack Start/Nitro app (the `node-server` preset,
set in `vite.config.ts`) and ships only the built `.output/`. Two things make
it deploy correctly on Cloud Run:

- **Port-aware command.** The bundled Nitro server reads `NITRO_PORT`, then
  `PORT`, and falls back to 3000 if both are unset, so the image runs
  `NITRO_PORT=${PORT:-8080} exec node .output/server/index.mjs` and maps
  Cloud Run's injected `PORT` onto Nitro.
- **Build-time API URL.** `VITE_API_BASE_URL` is baked into the client bundle
  at `npm run build` time (`ARG VITE_API_BASE_URL=http://localhost:8000` in
  the Dockerfile); a runtime env var does not change where the browser
  fetches. The deployed image is built with the live API URL via
  `cloudbuild.dashboard.yaml` (repo root), then deployed with
  `gcloud run deploy carematch-dashboard --image ...`. Do not use
  `gcloud run deploy --source ./dashboard` — the Dockerfile needs the repo
  root as build context and Cloud Run deploy has no `--build-arg` flag.

Live: `https://carematch-dashboard-726123996575.us-central1.run.app`

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS

## Status

- [x] New Assessment screen
- [x] Assessment Review screen (evidence display, inclusion/exclusion columns, accept/deny/needs-more-review flow). Flagging for more review shows a clean "Flagged for further review" confirmation right after submitting; the Accept/Deny buttons return on a genuine return visit to the flagged assessment
- [x] Trial Setup screen
- [x] Trials list screen (every registered trial with its rules)
- [x] Assessment History screen (every assessment ever run, newest first, click any row through to Review)
- [x] Wired to the real CareMatch API
- [x] Deployed to Cloud Run
- [x] Playwright end-to-end test suite (`tests/`)
