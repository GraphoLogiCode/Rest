# Authentication

Supabase handles sign-up, sign-in, and sessions. This module checks the access token on every private request and returns the user it belongs to.

- `tokens.py`: verifies signature, issuer, audience, expiry, and role. Tokens signed with the project's asymmetric keys are checked against its published keys. A shared-secret token is accepted only when `SUPABASE_JWT_SECRET` is set.
- `dependencies.py`: `CurrentUser`, the route dependency. It is the only source of a user's identity.

The project's anon and service keys are refused: only a signed-in user's token is accepted.
