# Frontend services

`storage.ts` stores check-ins and routines locally. `illustration.ts` is the proposed boundary for the other agent's SDXL + IP-Adapter Plus Face worker. **An HTTP implementation is not yet included.**

## Proposed illustration API

Set `VITE_ILLUSTRATION_API_URL` to an absolute HTTP(S) base URL, for example `http://127.0.0.1:8000`. Leave it unset to show the unavailable state. Local development servers should allow the frontend's exact origin via CORS.

### POST /jobs

Multipart form fields:

| Field | Value |
| --- | --- |
| `reference` | JPEG, PNG, or WebP file, maximum 10 MB on the client |
| `scenario` | Selected artistic scene text |
| `consent` | Literal string `true` after explicit user opt-in |

Return a successful HTTP response containing the job object below. Server must independently validate size, type, consent, and authorized access. Do not trust client validation.

### GET /jobs/{id}

Return the current job object. Client polls every two seconds while queued/running and stops waiting after ten minutes or when the view unmounts. Aborting the browser request does **not** cancel server work. The backend will need a cancellation/retention policy before production.

```json
{
  "id": "job-123",
  "status": "running",
  "progress": 35
}
```

`status`: `queued`, `running`, `completed`, or `failed`. `progress` is optional, real measurable progress from 0–100. Omit it for unknown progress; the interface uses an indeterminate indicator.

For `completed`, include `imageUrl`, an absolute HTTP(S) URL or path relative to the API base. It should point to the separately stored generated asset. For `failed`, the UI displays a generic retry message, rather than potentially sensitive service error details.

```json
{
  "id": "job-123",
  "status": "completed",
  "imageUrl": "/outputs/job-123.png"
}
```

Reference photos are not sent until the user has a reference image, selects a scene, checks generation consent, and presses Create illustration. UI scenes describe artistic settings rather than health or appearance improvements. Generated results remain separate from real before/after photos and carry: “AI-generated illustration—not a prediction of your appearance or health.”

Production integration still needs authentication, ownership checks, storage/transport protection, upload limits, retention and deletion (including embeddings), rate limits, backend cancellation, and explicit training consent if training is ever introduced. Never expose model-service credentials in frontend environment variables.
