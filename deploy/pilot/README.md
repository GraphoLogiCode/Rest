# Real-progress pilot deployment

Use `../ecs/README.md` for the selected AWS-managed URL deployment. App Runner templates are archived and no longer used.

This is the CPU-only deployment for saved accounts, catalog matching, feedback and real photo comparisons. It has no GPU, model token or illustration worker. A data-based outcome preview is disabled because no validated outcome model exists.

The user selected an AWS-managed URL. Use `../ecs/README.md` for ECS Express Mode. The Compose/Caddy option below is retained for a self-managed domain.

## Current launch blockers

The Supabase project exists and migrations 0001–0002 were applied by the account-setup chat. The database connection and all six owner-protected tables were verified. Migration 0003 has now been applied transactionally. AWS access inspected so far is read-only; no public domain or HTTPS deployment is verified. Docker is unavailable on the current development machine, so this container build and Caddy configuration still need an actual container smoke test.

## Launch sequence

1. Complete `python3 backend/scripts/configure_supabase.py` locally. Do not paste passwords into chat. Migrations 0001–0003 are already applied to the Rest project; do not reapply them. Use filename order only for a new empty project. Keep the database connection server-side with TLS.
2. Run `backend/.venv/bin/python backend/scripts/check_pilot_database.py`. This performs read-only checks for all six tables, RLS and no anonymous reads. It does not modify data or run the destructive test fixture.
3. Use an approved CPU EC2 host with Docker Compose in the chosen AWS region. Scope deployment permissions to that host, encrypted storage, security group and access mechanism. Check cost against the existing $100 total test-credit ceiling and set a shutdown time. Only expose ports 80/443; use SSM for administration. The database and port 8000 must remain private.
4. Copy `.env.example` to ignored `.env` in this directory, chmod 600, and fill it locally. Point the selected DNS name at the host. The browser uses `/rest-api` on the same HTTPS origin. Only the public Supabase key enters the frontend build.
5. In Supabase Auth, configure the Site URL and allowed redirects for `https://YOUR_DOMAIN/#settings` and `https://YOUR_DOMAIN/?reset=1#settings`. Configure and test confirmation/recovery email delivery; enforce a matching 12-character password minimum server-side. The new app includes signup, signin and recovery forms.
6. From this directory run `docker compose config --quiet`, `docker compose build`, then `docker compose up -d`. Keep one API process per container. Progress and photo-consent/deletion coordination now also uses a shared Postgres transaction advisory lock. Do not expand beyond the limited pilot before load and other account-writer concurrency checks.
7. Verify HTTPS and two actual test accounts: confirm signup/recovery, save a check-in and routine, sign out/back in, request a suggestion and rate it, enable photo storage, save two approved test photos with different dates, compare, download, delete, revoke photo consent, and export/delete account data. Confirm the second account cannot access the first account's photo ID. Use no customer data until this passes.

## Pilot limits and release gates

- Nine reviewed catalog records; five eligible cleansers/moisturizers. Eighteen candidates remain held. Unsupported goals and uncertain ingredient exclusions produce no recommendation.
- Photos: authenticated owner-only downloads; up to 12 per account, 10 MB/4 MP input, max 1280px/2 MiB normalized JPEG. EXIF removed, no cosmetic edits. Stored as bounded Postgres bytes for this small pilot. Monitor database space before adding users; move to private object storage with equivalent ownership/deletion controls for larger use. Supabase backup retention is separate from deletion in active storage.
- Up to 1,000 records per account per other record kind. Recommendations save the exact response for feedback provenance. Exports include metadata/reports; image downloads are in the journal.
- Add and test edge rate limiting/abuse controls before open registration or a public launch. The upload size cap is not a request-rate limit. Load, mobile and production email checks are outstanding.
- Training is not running. Any future dataset extraction must require both training consent at collection and current consent, exclude withdrawn/deleted records, split by user and time, and evaluate skin-tone/capture subgroups. Self-reported use and photos cannot alone identify causal product effects. Outcome-preview release requires a predefined endpoint, reliable paired observations, independently reviewed labels and held-out validation; collecting a certain number of photos is not a release criterion.
