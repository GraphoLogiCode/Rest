# Profile API

Skin type, concerns, goals, sensitivities, preferences, budget.

- `GET /v1/me`: the caller's profile, created with defaults on first use.
- `PATCH /v1/me`: changes only the fields sent. `null` clears a nullable field.

Set `timezone` early: check-in dates and summary periods follow it.
