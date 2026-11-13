# Check-in API

Sleep, mental, and social context check-ins.

- `POST /v1/checkins`: one per user and local date; a duplicate returns 409 with the existing id.
- `PATCH /v1/checkins/{id}`: edits values. The date cannot change.
- `GET /v1/checkins?from=&to=`: the caller's history, newest first.

Writes need the caller's `service` consent. Scale ranges and their current frontend labels are in the [backend design](../../../DESIGN.md#check-in-scales-version-checkinv1).
