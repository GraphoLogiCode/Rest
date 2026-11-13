# Privacy

Consent records, data-use explanations, photo encryption, user-controlled deletion.

- `GET /v1/consents`, `PUT /v1/consents/{type}`, `DELETE /v1/consents/{type}`: consent history, grant, revoke. Types: `service`, `model_training`, `photo_storage`, `illustration`.
- `POST /v1/export`: everything stored about the caller.
- `DELETE /v1/account`: deletes the caller's stored data. It does not remove the sign-in identity yet.
- `consent.py`: `require_consent`, a route dependency that refuses a request without an active consent.
