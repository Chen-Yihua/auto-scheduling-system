# Auto Scheduling System

A full-stack dashboard that pulls a user's tasks and deadlines into one place — manually created tasks, GitHub issues/PRs, Jira issues, Moodle assignments — alongside their Google Calendar, with AI-assisted priority/duration estimates and rule-based schedule suggestions.

Built with FastAPI (Backend) + MongoDB and Nuxt 3 (Frontend), authenticated end-to-end with Clerk.

---

## Architecture

```
├── Backend/   # FastAPI + MongoDB, deployed to Google Cloud Run (Docker)
└── Frontend/  # Nuxt 3 + TypeScript, deployed to Vercel
```

- **Auth**: [Clerk](https://clerk.com/) on both sides — the frontend never sees a password, the backend only ever verifies a JWT against Clerk's JWKS.
- **Database**: MongoDB (persistent data) + Redis (optional — rate-limit counters and short-TTL caches; falls back to in-process memory when `REDIS_URL` isn't set).
- **CI/CD**: GitHub Actions (`.github/workflows/deploy.yml`) — backend and frontend each have their own test job that must pass before their respective deploy job runs.

See [`Backend/README.md`](Backend/README.md) and [`Frontend/README.md`](Frontend/README.md) for setup instructions specific to each side.

---

## Features

- **Manual task management** — create/edit/delete tasks; priority and duration are AI-inferred (Gemini) when left blank, optionally steered by a user-supplied hint (e.g. "this took longer than it looked").
- **Third-party platform sync** (GitHub issues/PRs, Jira issues, Moodle assignments) — live fetch on every read, paginated, with automatic fallback to the last successfully synced snapshot if the live fetch fails; items no longer present upstream are pruned from the local cache instead of lingering forever.
- **Google Calendar integration** — embedded calendar view, computed free/busy slots, and a rule-based schedule suggestion endpoint built on top of them.
- **Linked account management** — connect GitHub/Jira/Moodle accounts; credentials are encrypted at rest and only ever returned to the client masked; Moodle connections are verified with a real login check (via Selenium) before being saved.
- **Security hardening** — whitelisted update fields (no mass assignment), rate limiting per authenticated user, encrypted secrets, and generic error responses that never leak internal exception detail to the client.
- **GitHub PR summary bot** — a webhook (separate from the user-facing product) that posts an AI-generated summary of opened PRs to Discord for this repo's own dev workflow.

---

## Tech Stack

| Layer | Stack |
|---|---|
| Frontend | Nuxt 3, Vue 3 (Composition API), TypeScript, Nuxt UI, Tailwind CSS, Clerk |
| Backend | FastAPI, Motor (async MongoDB driver), Pydantic, slowapi (rate limiting), Selenium (Moodle scraping), Google Gemini (AI inference & PR summaries) |
| Database | MongoDB (persistent), Redis (optional cache / rate-limit store) |
| Testing | Pytest (unit + end-to-end API scenario tests), Vitest (component/composable unit tests), Playwright via `@nuxt/test-utils` + `@clerk/testing` (real-browser E2E) |
| Deploy | Docker → Google Cloud Run (backend), Vercel (frontend), GitHub Actions (CI/CD) |

---

## Testing Strategy

- **Backend**: layered — `crud`/`router`-level unit tests mock out the database and external APIs; a separate set of **scenario tests** chains multiple real HTTP calls against an in-memory-but-real (`mongomock-motor`) database to catch integration bugs that per-endpoint mocking hides (e.g. "does an update actually persist and show up on the next read").
- **Frontend**: component and composable tests run against jsdom with Nuxt's auto-imports mocked; a separate **E2E suite** builds and boots the real Nuxt app and drives it with a real headless browser (Playwright), covering both the signed-out state and — with a real Clerk test account configured in CI — a genuine password sign-in flow.

Run locally:
```bash
# Backend
cd Backend && pytest

# Frontend
cd Frontend && npm run test       # unit/component
cd Frontend && npm run test:e2e   # real-browser E2E
```
