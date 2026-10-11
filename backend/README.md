# Backend

The Rest API: a FastAPI service in front of Supabase. It validates each request's access token, stores user-owned data in Postgres, and enforces that users reach only their own records.

See [DESIGN.md](DESIGN.md) for tables, endpoints, access control, and what is built so far.

## Layout

```
backend/
├── DESIGN.md
├── requirements.txt, requirements-dev.txt
├── src/
│   ├── main.py              # App factory
│   ├── config.py            # Settings from environment variables
│   ├── errors.py            # Error responses
│   ├── auth/                # Token validation, current user
│   ├── api/profile/         # /v1/me
│   ├── api/checkins/        # /v1/checkins
│   ├── context/             # /v1/summary, insight feedback
│   ├── privacy/             # /v1/consents, /v1/export, /v1/account
│   └── storage/             # In-memory and Postgres stores
└── tests/
```

The other directories under `src/` are planned and hold only a README.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/uvicorn src.main:create_app --factory --env-file .env --reload
```

Fill in `.env` first. `SUPABASE_URL` is required; the server will not start without it. Without `DATABASE_URL` the server keeps data in memory and loses it on restart.

Apply the SQL in [`data/migrations/`](../data/migrations/README.md) to the Supabase project before pointing `DATABASE_URL` at it.

Interactive API docs are at `/docs` once the server is running.

## Test

```bash
.venv/bin/pytest
```

This runs the API tests against the in-memory store. To also run them against Postgres, and to run the row-level security tests, set `REST_TEST_DATABASE_URL` to a local or throwaway database:

```bash
REST_TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres .venv/bin/pytest
```

Never point it at a database with real data. The tests create and delete users, and they apply the migrations if the tables are missing.

## CUDA illustration jobs

The authenticated backend now proxies a private model worker. Setup, endpoint contract,
AWS Ohio deployment, retention limits and the CUDA smoke test are documented in
[`deploy/aws/README.md`](../deploy/aws/README.md). Configure `MODEL_SERVICE_URL` and
`MODEL_SERVICE_TOKEN` together; the token stays server-side. Start exactly one API
process for this staging deployment. Consent revocation and account-data deletion
purge temporary model jobs before reporting success.

## Account routines and product matching

Apply `data/migrations/0002_routine_state.sql` after `0001` before deploying the
updated backend. Routine state uses user ownership, Postgres row-level security,
and a version check; the memory store remains for local tests only.

- `GET /v1/routine`: the caller's `{version, items}`.
- `PUT /v1/routine`: submit that version and the complete edited item list.
  Requires service consent; a stale version returns 409 without replacing data.
- `POST /v1/export` includes routines. `DELETE /v1/account` deletes them too.
- `GET /v1/products`: reviewed catalog; category/search/offset/limit supported.
- `GET /v1/products/{id}`: reviewed product detail; pending candidates are absent.
- `POST /v1/recommendations`: authenticated, service-consented request containing
  category and optional goal/texture; profile constraints come from the caller's
  saved profile, never a client-supplied user ID.

Recommendations currently cover cosmetic cleansers and moisturizers. Explicit
exclusions, unknown ingredient names, unsupported label restrictions, budget
currency/price gaps, stale prices, and missing goal evidence fail closed. Price
freshness is an operational 90-day cutoff, not an efficacy rule. Matching is
versioned and deterministic, with stable product-ID ordering among equally
eligible products. There is no trained ranker, learned effectiveness score,
lifestyle inference, feedback-training pipeline or medical outcome prediction.
See `data/catalog/README.md` for the verification gate. The first source audit
publishes nine manufacturer records; 18 candidates remain unpublished. Five reviewed cleansers/moisturizers are eligible for preference matching.
Reviewed direction/warning summaries are explicitly marked and shown with the
manufacturer source. Restart the API after deploying the catalog update.

Validation added: routine ownership/version conflicts/export/deletion, catalog
verification failures, exact ingredient alias matching, unknown exclusions,
budget and currency constraints, stable ranking, and rejection of unsupported
marketing/lifestyle inference. Postgres tests require a disposable
`REST_TEST_DATABASE_URL`; never point tests at real user data.

## Observed progress and recommendation feedback

Apply migration 0003 before using the new routes. `POST /v1/progress/usage` records product-use intervals, helpfulness/irritation and package-match confirmation, with product/routine snapshots. `POST /v1/progress/photos` accepts a bounded multipart real-photo upload only with separate photo-storage consent. GET routes list own reports/photos; `/photos/{id}/image` privately downloads normalized JPEGs. `POST /v1/progress/comparisons` checks date order and flags capture differences. It never attributes differences to a product.

Recommendations now retain an owned snapshot and return `recommendation_id`; `POST /v1/progress/recommendation-feedback` accepts useful/not-useful feedback only for products actually shown in that snapshot. Account export/deletion includes all progress records. Revoking photo storage removes saved photos from active storage. `/v1/progress/model-readiness` always reports prediction unavailable until a separately validated model is implemented. See `deploy/pilot/README.md` for the CPU-only launch path and outstanding release checks.
