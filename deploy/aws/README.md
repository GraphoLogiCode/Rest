# Rest CUDA staging deployment — AWS Ohio (us-east-2)

Prepared locally; no AWS resources have been created. Docker build and real CUDA inference still need verification on an NVIDIA host. The service contract is tested using a fake model, not a substitute CUDA benchmark.

## Architecture

Phone/browser → HTTPS Rest API → private GPU worker → local SDXL + IP-Adapter Plus Face weights.

The browser signs in with Supabase. The Rest API verifies that user JWT, checks illustration consent, and supplies the verified user ID to the worker with a separate server-only service token. Photos are never sent to Supabase or a public model endpoint. Supabase stores profiles, check-ins and consent; temporary jobs live on the GPU host's disk.

This is a **single-host, single API process, single GPU worker** staging design. A SQLite queue survives process restarts; interrupted jobs fail rather than silently rerunning. Do not increase Uvicorn workers or add replicas. A future multi-host deployment needs shared job storage, distributed consent/deletion coordination, and a queue such as SQS.

## Account setup status (2026-10-11)

- Target account: Rest (`620214493890`), Ohio (`us-east-2`). The local default AWS CLI profile's region has been corrected from `us` to `us-east-2` and verified.
- The user authorized using the existing **$100 AWS credits** for initial testing. Treat this as the total initial spending ceiling, not a recurring monthly budget. No instance has been launched or paid-plan upgrade performed by this setup.
- The account console showed $100 credits and zero Ohio G/VT On-Demand vCPU quota. The proposed `g6.2xlarge` needs 8 vCPUs. A quota increase does not itself launch an instance.
- AWS Free account plans restrict instance types. A Paid-plan upgrade is required for the proposed GPU; eligible credits can still apply, but usage beyond credits can be billed. Obtain the user's decision before upgrading. Budget alerts are not a hard spending cap. See [AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
- With explicit user approval, inline policy `RestSetupReadOnlyOhio` was attached to IAM user `Ben`. Its source is `rest-setup-readonly-policy.json`. CLI checks confirmed the policy name, EC2 inspection, and G/VT quota access; the budgets command also completed without AccessDenied. The policy grants inspection only, not deployment or IAM administration. Additional deployment permissions should be scoped to the resources selected for launch.
- Supabase Rest project `byrndjhgzusfjdgjfbev` is healthy in Ohio on the Free organization. Both SQL migrations were applied in one transaction through the SQL editor. All five tables were verified to have RLS enabled, one owner policy each, and no anonymous SELECT privilege. These manual SQL runs do not create Supabase CLI migration-history entries; do not reapply the initial migrations to this project.
- The project URL and public publishable key are saved in ignored local configuration files. The database password was supplied through the local setup prompt. A subsequent credential value accidentally inserted into the script's URL-encoding argument was removed, and the saved URI encoding was repaired. `python3 backend/scripts/configure_supabase.py` prompts without echo and percent-encodes the password into an IPv4-compatible session-pooler URL with TLS. The live connection passed read-only schema, owner-context, and anonymous-access checks. The backend started with `PostgresStore`, read through its real pool, returned HTTP 200 for health, and rejected an unauthenticated jobs request with HTTP 401. Local frontend cloud mode remains disabled pending a running API and real app-user sign-in; full app authentication and GPU generation are not yet verified. AWS credits do not pay Supabase charges; retain Supabase's Free plan.

## Information still needed

- Expected GPU testing hours. No GPU instance should be launched until current price, credits, quota, and a shutdown plan are checked in the account.
- An actual Supabase app test-user session (the database connection is verified). The public JWKS endpoint returned HTTP 200 with one ES256 key, compatible with the backend's asymmetric JWT verification; no legacy JWT secret is needed. Put secrets in local ignored environment files or a secret manager, not chat.
- A frontend/API domain for HTTPS, and whether phone testing is on iPhone or Android.
- An AWS CLI SSO profile with permission to inspect EC2 quotas and eventually create the approved instance. Do not share root credentials or access keys in chat.

## Host preparation (after deployment is approved)

Use Linux x86-64 with an NVIDIA GPU. A full **G6 with one 24 GB L4** is the initial target; `g6.2xlarge` also provides 32 GiB system RAM. Confirm Ohio availability, On-Demand G-family vCPU quota and current price in the account before launching. This configuration is a starting point, not a measured CUDA sizing result. Budget alerts do not automatically stop spending. Stop the instance after testing; EBS storage continues to incur charges while stopped.

Use an encrypted EBS volume (start with 80 GB for container layers, approximately 10 GB weights, download caches and temporary jobs), no public inbound access initially, and an SSM-capable instance role. Avoid snapshots/backups of the temporary job directory. Install Docker Compose with GPU device support (Compose 2.30+), an NVIDIA driver compatible with CUDA 12.8, and NVIDIA Container Toolkit. Verify `nvidia-smi` first.

Official references: [AWS G6](https://aws.amazon.com/ec2/instance-types/g6/), [AWS NVIDIA drivers](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/install-nvidia-driver.html), [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), [PyTorch CUDA wheels](https://download.pytorch.org/whl/cu128/torch/).

On the EC2 host, from this directory:

```sh
cp .env.example .env
chmod 600 .env
# Fill .env locally. Generate MODEL_SERVICE_TOKEN with:
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
sudo install -d -o 10001 -g 10001 -m 700 /srv/rest/models /srv/rest/jobs
docker compose build
```

The containers run as UID 10001. GPU inference is offline; provision the pinned weights separately. The download command uses outbound networking only during setup and checks the manifest's sizes and SHA-256 hashes:

```sh
docker run --rm --user 10001:10001 \
  --mount type=bind,src=/srv/rest/models,dst=/app/.local/models \
  rest-gpu:cuda python download_models.py

docker compose run --rm --no-deps gpu python preflight.py
```

`preflight.py` exercises a CUDA matrix operation and verifies every model asset. It does **not** prove a complete image generation fits in GPU memory. The model weights are mounted read-only during service operation. No Hugging Face token is required for the currently pinned public model assets.

Apply both existing SQL migrations in filename order to the intended empty Supabase project according to `backend/README.md`: `data/migrations/0001_profiles_consents_checkins_insights.sql`, then `data/migrations/0002_routine_state.sql`. Inspect an existing database before applying them; the first migration is not idempotent. Then start:

```sh
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8000/healthz
```

The worker has **no host port** and an internal Docker network without outbound internet. The API binds only `127.0.0.1:8000` and can reach Supabase. Use SSM port forwarding for initial testing. Before phone access, add an HTTPS reverse proxy/load balancer, a valid certificate and domain, an 11 MB request-body limit, request-rate limits, and an appropriate upload timeout. Expose only HTTPS; do not expose ports 8000 or 8767 publicly. The worker's `/healthz` checks queue-thread liveness, not model readiness.

## Connect the app

Set these in the frontend's ignored `.env.local`, then rebuild:

```dotenv
VITE_REST_API_URL=https://api.your-domain.example
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your-public-publishable-or-anon-key
```

Set backend `CORS_ORIGINS` to the exact frontend HTTPS origin. Create/invite a test user in Supabase Auth; the photo-preview section now includes email/password sign-in. Self-service signup, password reset and app-wide account UI are not included. Existing check-ins/routines still use the frontend's local storage; this change connects the **illustration feature** to the authenticated backend.

In development, leaving `VITE_REST_API_URL` unset preserves the existing Mac local-preview service. Production builds require the cloud configuration. Never put the private model token, database password or Supabase service-role key into any `VITE_` variable. Use HTTPS on phones; an HTTPS installable app should not call an HTTP API.

## Real CUDA smoke test

Install `httpx` in your test environment or use `backend/.venv/bin/python`. Set `REST_API_URL` and a short-lived signed-in test user's `REST_ACCESS_TOKEN` in the local shell. The script grants illustration consent for that user, uploads the selected photo, polls, downloads the labeled output, and deletes the temporary server job. Do not run it with someone else's photo without their permission.

```sh
python smoke_test.py --photo /path/to/approved-test-photo.png \
  --face-box 0 0 128 128 --edit-box 30 50 60 80 \
  --output smoke-output.png
```

Replace the sample coordinates with valid regions in your test photo. Inspect the image and run an actual face-edit CLI benchmark before choosing size, timeout or capacity. `run_face_edit.py --device cuda` records CUDA peak allocated/reserved memory and verifies exact preservation of pixels outside the selected mask. No expected latency is claimed until this test is run.

## API contract

All public paths require `Authorization: Bearer <Supabase access token>`.

| Operation | Route |
| --- | --- |
| Record illustration consent | `PUT /v1/consents/illustration` with `{"version":"illustration-2026-10-11"}` |
| Submit | `POST /v1/illustrations` with `Idempotency-Key: <UUID>` |
| List own jobs | `GET /v1/jobs` |
| Poll own job | `GET /v1/jobs/{id}` |
| Fetch PNG with bearer token | `GET /v1/jobs/{id}/image` |
| Cancel/delete own job | `DELETE /v1/jobs/{id}` |
| Revoke consent and purge jobs | `DELETE /v1/consents/illustration` |

Submission is multipart: `reference` file, `consent=true`, and an `options` JSON string:

```json
{"mode":"face-edit","face_box":[0,0,128,128],"edit_box":[30,50,60,80],"strength":0.15,"finish":"original","size":512,"steps":30,"seed":42}
```

Face and edit coordinates refer to the EXIF-oriented input. Face must be a square at least 64 pixels wide; the edit ellipse must fit inside it. Strength is 0.15 or 0.25, finish is `original` or `soft-light`, size 512 or 768, steps 10–50. Arbitrary prompts and product claims are not accepted. The scene runner also accepts `mode: scene` and one of the three fixed scenarios in `job_worker.py`; the current UI uses face editing.

Status is `queued`, `running`, `completed` or `failed`. `progress`, when present, measures **denoising only** with `completedSteps`, `totalSteps`, `progressStage: denoising`; model loading and export have no invented percentage. A completed response contains a relative authenticated image path. The frontend fetches image bytes with its JWT and uses a temporary browser blob URL.

Retry an uncertain POST with the same idempotency UUID and the same input while the job exists. Reusing it with different input returns 409. Expired or deleted keys can create a new job. Jobs belonging to another user return 404. Maximum four pending/running jobs globally, six retained jobs per user, one active GPU subprocess, 300-second generation timeout. Every job reloads the pipeline; this isolates cancellation and GPU memory but includes model-load overhead.

## Data lifecycle and verification

Uploads accept JPG/PNG/WebP up to 10 MB and four megapixels; full multipart requests are capped at 11 MB. Decoding/re-encoding removes metadata. Input files, masks, logs and intermediates are removed when the job finishes or fails. Only the labeled illustration remains until deletion or the 30-minute TTL from submission. Expired results immediately become inaccessible; active jobs receive cancellation at expiry and disk cleanup follows process termination. Cleanup runs while the worker is operating, and again on startup. A powered-off host cannot execute retention cleanup. Keep the job volume encrypted and out of backups.

Account-data deletion purges the worker first and returns a retryable failure if it cannot confirm deletion; it still does not delete the Supabase sign-in identity. Export includes temporary job metadata, with images available through the authenticated download route while unexpired. Jobs and photos are not used for training.

Local checks:

```sh
cd ../../backend
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest ../ml/scenario-visualization/test_cloud_api.py ../ml/scenario-visualization/test_face_regions.py -q
cd ../frontend
npm test
npm run build
```

Postgres integration tests skip unless `REST_TEST_DATABASE_URL` points to a throwaway test database. The CPU tests inject a fake image runner and cover ownership, consent, private downloads, deletion, expiry, cancellation, idempotency and restart recovery. Container build, CUDA inference, Supabase project integration, public HTTPS and phone installation are separate deployment checks still pending.

## GPU deployment readiness and customer metering — 2026-10-11

Run `python3 deploy/aws/prepare_gpu.py --output output/gpu-readiness.json` from
repository root for a read-only account/quota check. `--request-quota` requests the
8-vCPU Ohio G/VT quota only when no request is pending; it never launches an instance.
The live check found quota 0, no pending request and no instances. The attempted
quota request failed with `AccessDeniedException` under Ben's read-only credentials.
The console also requires administrator sign-in. No GPU deployment has occurred.
`rest-gpu-quota-request-policy.json` is a narrowly scoped, unapplied policy for an
administrator to review; it grants no instance launch or IAM administration rights.
Existing ECS deployment permissions also do not grant EC2 GPU deployment access.

The CUDA worker now records durable, deduplicated completion usage by verified
customer ID. The API exposes authenticated customer usage and includes it in
account export/deletion. See `backend/src/billing/README.md` (from repository root).
No payment provider is activated and no customer charges are created. Local anonymous
Mac previews are not billed or retroactively attached to customers.
