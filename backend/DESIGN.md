# Backend: data, API, and access control

Status: the first slice is built and tested. It covers sign-in checks, profiles, consents, check-ins, summaries, export, and account data deletion. Photos, illustrations, routines, products, and recommendations are designed but not built.

## Boundary

FastAPI is the application boundary. Supabase provides sign-in, Postgres, and file storage; browsers talk to the API, not to the tables.

- Every `/v1` request must carry a Supabase access token. The API checks its signature, issuer, audience, expiry, and role.
- The user's identity comes from the token and nowhere else. A `user_id` sent by the browser is rejected in a body and ignored in a query string.
- A record that belongs to someone else returns 404, the same as one that does not exist.

## Where each part lives

| Part | Directory | Status |
|---|---|---|
| Token validation, current user | `src/auth/` | Built |
| Profile and preferences | `src/api/profile/` | Built |
| Check-ins | `src/api/checkins/` | Built |
| Summaries and insight feedback | `src/context/` | Built |
| Consents, export, account deletion | `src/privacy/` | Built |
| Persistence (in-memory and Postgres) | `src/storage/` | Built |
| Tables, row-level security, grants | [`data/migrations/`](../data/migrations/README.md) | Built |
| Photos | `src/api/photos/` | Later |
| Illustration jobs | `src/visualization/` | Later |
| Routine and usage episodes | `src/api/routine/` | Later |
| Products and ingredients | `src/api/products/`, `src/ingredients/` | Later |
| Recommendations | `src/recommendations/` | Later; see its [design](src/recommendations/DESIGN.md) |

## Tables

| Table | Key fields | Status |
|---|---|---|
| `profiles` | `user_id`, `timezone`, `goals`, `skin_type`, `concerns`, `ingredient_exclusions`, `budget_amount`, `budget_currency`, `created_at`, `updated_at` | Built |
| `consents` | `id`, `user_id`, `consent_type`, `version`, `granted_at`, `revoked_at` | Built |
| `checkins` | `id`, `user_id`, `local_date`, `timezone`, `scale_version`, `sleep_hours`, `sleep_quality`, `mood`, `stress`, `connection`, `note`, `created_at`, `updated_at` | Built |
| `insights` | `id`, `user_id`, `period_start`, `period_end`, `input_version`, `rule_version`, `text`, `feedback`, `feedback_at`, `created_at` | Built |
| `photos` | `id`, `user_id`, `storage_key`, `captured_at`, `consent_version` | Later |
| `generation_jobs` | `id`, `user_id`, `status`, `input_photo_id`, `scenario`, `model_version`, `output_key`, `error`, `expires_at` | Later |

Rules the tables and the API both enforce:

- One check-in per user and local date. A second `POST` for the same date returns 409 with the existing check-in's id; edit it with `PATCH`.
- Timestamps are stored and returned in UTC. Each check-in keeps the user's timezone at the time it was made.
- Scale values are optional whole numbers within a fixed range. `sleep_hours` is 0 to 24 with one decimal place. A check-in needs at least one value.
- `ingredient_exclusions` is `null` when the user has not answered and an empty list when they reported none.

## Endpoints

| Method and path | Purpose | Status |
|---|---|---|
| `GET /v1/me` | Profile and preferences; created with defaults on first use | Built |
| `PATCH /v1/me` | Change timezone, goals, skin profile, budget | Built |
| `GET /v1/consents` | Consent history, newest first | Built |
| `PUT /v1/consents/{type}` | Grant a consent at a notice version | Built |
| `DELETE /v1/consents/{type}` | Revoke the active consent | Built |
| `POST /v1/checkins` | Create the check-in for a local date | Built |
| `PATCH /v1/checkins/{id}` | Edit an owned check-in | Built |
| `GET /v1/checkins?from=&to=` | Owned history, newest first | Built |
| `GET /v1/summary?period=week\|month` | Descriptive summary and data coverage | Built |
| `POST /v1/insights/{id}/feedback` | Record whether a summary was useful | Built |
| `POST /v1/export` | Everything stored about the caller, as JSON | Built |
| `DELETE /v1/account` | Delete the caller's stored data | Built |
| `POST /v1/illustrations` | Check consent and queue a generation job | Later |
| `GET /v1/jobs/{id}` | Owned job status and output link | Later |

The recommendation, usage-episode, and outcome operations in the [recommendation design](src/recommendations/DESIGN.md) will sit under the same `/v1` prefix and the same token check.

## Access control

| Requirement | How it is met |
|---|---|
| Row-level security on every user table | Enabled in the migration with one owner policy per table, and tested with plain SQL |
| An API credential that bypasses row-level security must enforce ownership itself | Every statement filters on the owner's id, and each transaction also drops to the `authenticated` role with the owner as `auth.uid()`, so row-level security still applies |
| Clients cannot rewrite history | Column grants: an owner cannot change `user_id`, a check-in's date, a consent's version or grant time, or an insight's text |
| Signed-out clients get nothing | All access is revoked from the `anon` role |
| Privileged credentials stay off the client | Only the server holds `DATABASE_URL`; the browser holds only its own access token |
| Sensitive values are not leaked | Validation errors name the field, never the submitted value; every response is marked `no-store` |

For photos, later: private buckets, short-lived access links, object paths generated by the server, and separate storage policies.

## Changes from the first draft

- **Profile** also holds the skin profile the [recommendation data contract](../data/schema/recommendations/README.md) needs: skin type, concerns, ingredient exclusions, and budget.
- **Consents** use that contract's four scopes: `service`, `model_training`, `photo_storage`, `illustration`. Endpoints to grant and revoke were added.
- **Check-in writes need the `service` consent.** Reading, exporting, and deleting stay available after it is revoked.
- **Scales are stored as numbers** with a `scale_version`, so the labels can change without rewriting history.
- **Insights are descriptive only.** The text is built from fixed wording, states counts and averages of what was logged, and always ends by saying it does not explain a cause. `GET /v1/summary` saves it so feedback has something to attach to.
- **Export is immediate.** It returns the data in the response instead of queuing a job.
- **`PATCH /v1/me` was added** so the timezone and profile can be set.

## Check-in scales, version `checkin.v1`

| Field | Range | Frontend label today |
|---|---|---|
| `sleep_hours` | 0 to 24, one decimal | Sleep slider, 0 to 14 |
| `mood` | 1 to 4 | Low, Okay, Good, Great |
| `connection` | 1 to 3 | Quiet time, A little, Connected |
| `stress` | 1 to 5 | Not collected yet |
| `sleep_quality` | 1 to 5 | Not collected yet |

## Open items

- The frontend still saves to browser storage and does not call this API.
- The frontend's illustration service calls `POST /jobs` and `GET /jobs/{id}`. The paths planned here are `POST /v1/illustrations` and `GET /v1/jobs/{id}`; one side has to change.
- The frontend's routine steps have no table yet. The data contract ties routines to product versions and usage episodes.
- `DELETE /v1/account` removes stored data but not the Supabase sign-in identity, which needs Supabase's admin API.
- There is no rate limiting.
- The database tests ran against an in-process Postgres with stand-ins for Supabase's `auth` schema and roles. The migration has not been applied to a real Supabase project.
