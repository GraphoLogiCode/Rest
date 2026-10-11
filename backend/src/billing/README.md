# Customer metering and future billing integration

Status: tracking only. No plans, subscriptions, card collection, invoices, payment
SDK or external billing calls are enabled. This is not a production billing system.

The verified Supabase user UUID is the customer identity. The private model worker
receives it only from the Rest backend; a browser-supplied customer header is ignored.
`GET /v1/billing/usage?after=0&limit=100` requires the user's JWT and returns only
that customer's events, with `paymentsEnabled: false` and `billingMode: tracking_only`.
No configured worker returns 503, not a misleading zero-usage report.

The worker atomically commits one `illustration.completed` event with the completed
job state after image validation. The job UUID is the unique event ID. Polling,
downloads and retrying an existing idempotency key create no extra usage. Failed,
cancelled, expired-before-completion and interrupted jobs create no completed event.
Resubmitting after a job was deleted/expired starts a new generation and therefore
can produce a new event. Generation runtime is wall time, not NVIDIA GPU utilization
or an AWS charge. It includes model loading and output preparation.

Events retain only customer UUID, job/event UUID, UTC Unix time, count, runtime,
model label and region. No photo, prompt, product, email or face measurements enter
the ledger. They survive image TTL, individual image deletion and process restarts
in the worker's SQLite database on the encrypted persistent job volume. Account-data
deletion removes usage after cancelling the owner's jobs. Consent revocation removes
photos/jobs but retains prior operational usage until account deletion. Account
export includes the owner's usage. There is currently no paid-record retention policy;
that must be designed before payments are enabled.

## Adapter boundary

Run on the worker host (operator access only):

```sh
python export_usage.py --database /var/lib/rest/jobs/jobs.sqlite3 --output /tmp/rest-usage.jsonl --after 0
```

The exclusive, owner-readable export contains versioned events and reports the last
sequence. It makes no network calls and never marks an event delivered. Treat exports
as customer data; store them privately. A future billing adapter must deduplicate by
`eventId`, map `customerId` to the provider's customer, apply a versioned pricing plan,
and record provider acknowledgement before advancing its delivery checkpoint. It
must retry partial failures and reconcile totals independently of customer polling.
Do not trust quantities, customer IDs or prices supplied by a browser.

AWS App Monetization is the intended future provider. Its SDK and authorization
contract are not installed or verified in this workspace; no interface is invented.
Confirm supported integration for React/Vite + FastAPI, complete authorized sandbox
onboarding, then implement the adapter against the supplied SDK. Keep evaluation and
production configurations separate. Do not commit private onboarding documents,
registry credentials, interaction logs or seller details. Accept terms and configure
payments through an explicit owner-led onboarding step.

AWS infrastructure costs and customer prices are separate. Before charging, add a
shared durable ledger/outbox (for multiple workers), customer/subscription mappings,
entitlements, delivery retries, authenticated webhook verification, price versions,
refund/reversal handling, retention/export controls and cost reconciliation. This
single-host tracking ledger is a tested starting point, not those completed systems.
