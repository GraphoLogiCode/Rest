# Rest

**A skincare and well-being companion that helps people make informed product choices, without judging how they look.**

Rest combines a verified product catalog, daily well-being check-ins (sleep, mood, connection), routines, and a private skin-progress journal. Lifestyle context is tracked alongside skin changes so a bad week of sleep isn't mistaken for a product that "didn't work."

![Rest demo: home, daily check-in, routine, products, and skin journal](docs/demo.mp4)

*Demo: logging a daily check-in, building a morning routine, browsing the reviewed product catalog, and the skin journal. [Full-quality video](docs/demo.mp4).*

## Highlights

- **Full-stack app**: React + TypeScript PWA (installable on phones) backed by a FastAPI service on Postgres/Supabase.
- **Privacy by design**: consent-gated features, row-level security so users only reach their own records, one-click data export and account deletion.
- **Verified product catalog**: products and ingredients go through a review pipeline before users ever see them ([catalog docs](data/catalog/README.md)).
- **Explainable recommendations**: rule-based filtering and ranking with an evidence record behind each suggestion ([design](backend/src/recommendations/DESIGN.md)).
- **Targeted AI illustration**: SDXL + IP-Adapter inpainting that edits only a user-selected skin region and leaves every other pixel unchanged; always labeled as an illustration, never a predicted result ([ML service](ml/scenario-visualization/README.md)).
- **Cloud deployment**: Docker images, AWS ECS/CodeBuild scripts with least-privilege IAM policies, and a GPU worker for model jobs ([deploy docs](deploy/ecs/README.md)).
- **Tested**: 140+ backend tests (auth, privacy, row-level security, deployment policy checks) plus frontend unit tests.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React 19, TypeScript, Vite, PWA (service worker + manifest), Supabase Auth |
| Backend | Python, FastAPI, Pydantic, psycopg, PyJWT, pytest |
| Data | PostgreSQL (Supabase), SQL migrations, row-level security |
| ML | PyTorch, Diffusers (SDXL + IP-Adapter Plus Face), CUDA worker |
| Infra | Docker, AWS ECS Fargate, ECR, CodeBuild, IAM, Caddy |

## Run it locally

```sh
# Frontend (works on its own; data stays in the browser)
cd frontend && npm install && npm run dev        # http://127.0.0.1:5173

# Backend API (optional; enables the live product catalog and accounts)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env                              # fill in SUPABASE_URL
.venv/bin/uvicorn src.main:create_app --factory --env-file .env --reload   # docs at /docs

# Tests
cd backend && .venv/bin/pytest
cd frontend && npm test
```

More detail: [frontend](frontend/README.md) · [backend](backend/README.md) · [AI illustration service](ml/scenario-visualization/LOCAL_SETUP.md) · [deployment](deploy/aws/README.md)

## Repository layout

```
rest/
├── frontend/   React + TypeScript PWA (screens, components, services, tests)
├── backend/    FastAPI API: auth, profile, check-ins, routine, catalog, privacy, progress
├── data/       Product catalog, SQL migrations, data schemas and sources
├── ml/         AI illustration service + ranking/model design notes
├── deploy/     Docker, AWS ECS, IAM policies, GPU worker setup
├── evaluation/ How Rest is evaluated before shipping learned models
└── PROJECT_TREE.md  Full concept tree
```

Each directory has its own `README.md`.

## Design documents

- [Recommendation engine design](backend/src/recommendations/DESIGN.md): filtering, ranking, service contracts, and build sequence.
- [Data to collect](data/schema/recommendations/README.md): catalog, profiles, impressions, usage episodes, outcomes, and consent.
- [How to train the model](ml/ranking/README.md): labels, features, baseline models, splits, and deployment gates.
- [Evaluation plan](evaluation/README.md): evidence needed before releasing a learned model.

## What is hard to copy

- [Longitudinal follow-up histories](data/schema/recommendations/README.md#longitudinal-history), collected with separate training consent. They take time to build, and their value comes from quality and trust.
- [A test of whether well-being context adds value](ml/ranking/README.md#testing-whether-well-being-context-helps) before it is used in ranking.
- [Traceable explanations](backend/src/recommendations/explanations/README.md#evidence-records), each backed by an evidence record.
- [Evidence about Rest itself](evaluation/README.md#evidence-about-rest-itself): whether the app helps people understand their choices.

Confidential methods and internal datasets may qualify as trade secrets when the requirements are met, though that does not prevent independent development ([WIPO guidance](https://www.wipo.int/en/web/trade-secrets/protection)). A patent could protect a qualifying specific invention, not the broad idea of combining skincare and lifestyle data. This repository is public, so nothing meant to stay confidential belongs in it.

## Product boundaries

- Photos are opt-in, encrypted, and deletable by the user.
- Not a medical diagnosis; users are pointed to a dermatologist for skin conditions.
- No beauty or attractiveness scores.
- Observed patterns are never presented as proof of causation.
