# CareMatch — Dashboard (Phase 3)

The coordinator-facing dashboard for CareMatch's clinical trial eligibility
review tool. Wired to the real backend (the FastAPI service in `api/`).

## Development

```sh
npm install
npm run dev
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS

## Status

- [x] New Assessment screen
- [x] Assessment Review screen (evidence display, inclusion/exclusion columns, accept/deny/needs-more-review flow)
- [x] Trial Setup screen
- [x] Trials list screen (every registered trial with its rules)
- [x] Wired to the real CareMatch API
