# Frontend — Workflow AI Copilot

Next.js (App Router) + Tailwind CSS + TypeScript. Talks to the FastAPI backend.

## Layout

```
app/
├── layout.tsx              # root layout + metadata
├── page.tsx                # landing page: header + task composer
├── globals.css             # Tailwind v4 entry + theme tokens
└── components/
    ├── BackendStatus.tsx    # live backend-connectivity indicator (client)
    ├── TaskComposer.tsx     # task input → generate → render → save (client)
    └── WorkflowPreview.tsx  # renders a plan's ordered, typed steps
lib/
├── config.ts               # runtime config (API base URL from env — no hardcoding)
├── constants.ts            # UI constants (task max length, step-type styling)
└── api.ts                  # typed fetch client + workflow/planner helpers
tests/                      # Vitest + React Testing Library
```

## Task flow

The landing page composer calls the backend: **Generate** → `POST /api/planner/preview`
renders the ordered steps; **Save workflow** → `POST /api/workflows` persists it
(reusing the previewed plan to avoid a second LLM call). Backend error details
(e.g. planner disabled → 503, DB down) surface inline.

## Prerequisites

- Node.js 20+ (developed on Node 25)
- The backend running (see [../backend/README.md](../backend/README.md)); CORS
  already allows `http://localhost:3000`.

## Develop

```bash
cd frontend
npm install
cp .env.example .env.local   # optional; defaults to http://localhost:8000
npm run dev                  # http://localhost:3000
```

The landing page shows a live indicator confirming it can reach the backend.

## Environment config

Dev/prod separation mirrors the backend — no hardcoded URLs:

| File | When | Value |
| ---- | ---- | ----- |
| [.env.development](.env.development) | `next dev` | `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` |
| [.env.production.example](.env.production.example) | template for `next build` | your deployed API URL |

`NEXT_PUBLIC_*` vars are inlined into the client bundle at build time.

## Scripts

```bash
npm run dev     # dev server (http://localhost:3000)
npm run build   # production build
npm start       # serve the production build
npm run lint    # ESLint (eslint-config-next)
npm test        # Vitest (unit + component)
```
