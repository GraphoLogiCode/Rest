# Local portrait experiment

This experiment uses **SDXL base 1.0 + IP-Adapter Plus Face SDXL ViT-H**. It is separate from recommendation training, skin analysis, and factual before/after comparison. It generates a new portrait conditioned on a reference image; it does not predict future appearance or health.

## Reproduce

From the repository root, use an ARM64 Python 3.12 environment:

```sh
python3.12 -m venv ml/scenario-visualization/.venv
ml/scenario-visualization/.venv/bin/python -m pip install -r ml/scenario-visualization/requirements.lock.txt
ml/scenario-visualization/.venv/bin/python ml/scenario-visualization/download_models.py
```

The downloader invokes `hf download` for exact repository revisions from `models.lock.json`, downloads about 10.3 GB, and verifies file sizes and available LFS SHA-256 checksums. It selects safetensors weights, with no remote Python execution. Keep the isolated environment and `.local/` assets untracked.

## Recommended: edit only a selected face region

Use masked editing to keep the same person, pose, framing, and background. The model receives the original face crop and edits a mask; the result is then composited back into the original. Every pixel outside the mask is preserved exactly in the saved PNG image area (a disclosure footer is added below it). Identity can still change **inside** the selected mask; keep eyes, mouth, and facial boundaries unselected when they should remain unchanged.

Run the supplied public-domain reference after downloading it as described below. These coordinates are specific to that sample, not a general face detector:

```sh
ml/scenario-visualization/.venv/bin/python ml/scenario-visualization/run_face_edit.py \
  --face-box 145 10 325 190 --edit-box 178 116 208 139
```

`--face-box LEFT TOP RIGHT BOTTOM` selects a square face context region in original-image pixels. `--edit-box` selects an ellipse within that face box. Both use right/bottom-exclusive coordinates after EXIF orientation. The prototype requires manual selection; it does not automatically detect or segment a face.

For a custom photo, supply an original-size PNG mask with white over the area to edit and black everywhere else. Replace the example face coordinates with the actual square selection for your image:

```sh
ml/scenario-visualization/.venv/bin/python ml/scenario-visualization/run_face_edit.py \
  --reference /absolute/path/to/photo.png \
  --face-box 100 100 500 500 --mask /absolute/path/to/mask.png \
  --strength 0.25 --steps 30
```

Strength controls how much the selected region can change. The default is conservative (0.25); at 30 scheduled steps this performs 7 actual denoising steps. Feathering is constrained to stay inside the mask. The mask must be nonempty and fully inside the chosen face box. Outputs include `face-comparison.png`, a labeled full-photo `illustration.png`, masks, a reference copy, and metrics with an outside-mask pixel check. The edit remains an illustration, not a product outcome prediction.

GPU access requires running outside a sandbox that hides Metal devices. The face-edit runner requires MPS and fails clearly when unavailable. It does not disable Apple's GPU memory limits.

The earlier full-portrait experiment remains available as `run_local.py`; it can regenerate pose/clothing/background and is not the recommended path for localized edits. Its `--device cpu` option is only a slower debugging fallback.

Inference uses local files and sets Hugging Face/Transformers offline mode. It does not upload photos or save face embeddings. It saves a reference copy, a labeled illustration, a comparison sheet, and a JSON timing/memory report inside a new timestamped `.local/outputs/` directory. Delete that whole run directory to remove its reference copy and output; the original input is untouched. This is a local development script, not an implemented encrypted storage or consent system.

Outputs carry an embedded disclosure. The comparison is labeled **reference / generated scenario**, not before / after. The default prompt requests natural texture and an ordinary setting; prompt instructions cannot guarantee identity or prevent unwanted appearance changes.

## Reference sample provenance

The test uses the scikit-image NASA astronaut sample, documented as public domain. It is a software test fixture, not a Rest participant, endorsement, training record, or outcome observation.

```sh
mkdir -p ml/scenario-visualization/.local/reference
curl -fL https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png \
  -o ml/scenario-visualization/.local/reference/astronaut.png
```

[Sample documentation](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.astronaut).

## Interpretation of the benchmark

- Generation time includes encoding, denoising, and decoding; model load time is reported separately.
- Process peak RSS and sampled Metal driver/tensor allocations are different measures. They overlap on unified memory and must not be added together. The sampled Metal maximum is not a guaranteed whole-run peak.
- One reference and seed establish only a local smoke test. They do not establish identity accuracy, demographic consistency, mobile compatibility, or production capacity.
- A successful local run supports a development prototype. Production still needs a consented image-quality evaluation, request limits, secure image handling/deletion, content controls, and a measured deployment environment.
- Real before/after comparison must continue to use real dated photographs. Do not connect product ingredients or well-being scores to predicted skin improvement.

## Licenses and upstream references

The IP-Adapter model card lists Apache-2.0. SDXL uses CreativeML Open RAIL++-M; retain its license and follow its use restrictions. Check the full dependency stack before commercial distribution. This implementation uses CLIP image conditioning, not the separate InsightFace-dependent FaceID model family.

- [SDXL model and license](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
- [IP-Adapter model variants](https://huggingface.co/h94/IP-Adapter)
- [Diffusers IP-Adapter integration](https://huggingface.co/docs/diffusers/en/using-diffusers/ip_adapter)
- [Apple MPS guidance](https://huggingface.co/docs/diffusers/optimization/mps)

## App photo preview (local development)

From the repository root, start the loopback GPU service:

```sh
ml/scenario-visualization/.venv/bin/python ml/scenario-visualization/local_api.py
```

In another terminal:

```sh
npm --prefix frontend run dev -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173, choose the photo journal and **AI illustration**.
Upload a JPG/PNG/WebP, frame a square around the face, then select an oval over
skin. Coordinate fields support keyboard selection. Confirm the regions and
consent before generating. Gentle brightening applies a small tone curve only
inside the selection. It is an artistic lighting effect, not a simulation of
skincare efficacy. Product notes are never passed to the model. Both preview
images retain the original framing; downloads include a burned-in disclosure.

The Vite same-origin `/illustration-api` proxy connects to 127.0.0.1:8766.
The browser normalizes uploads to at most 1,024 pixels on the longest side and
strips metadata. The API validates images and regions, runs one local inference
at a time, and rejects results if pixels outside the mask changed. Inputs and
intermediates are removed after processing; session-owned outputs expire after
30 minutes, on service shutdown, or on explicit deletion. Closing the editor
requests deletion on a best-effort basis. A hard crash may leave temporary files
until the next service startup. No training consent or training collection is
implied by preview consent.

This is a loopback development service, not the authenticated Rest production
backend. Public deployment requires integration with that backend's identity,
consent, storage/deletion controls, rate limiting and a GPU worker. Do not expose
the development service or Vite server publicly. The model is not a validated
product-outcome predictor. Real progress uses two real dated photos.

Checks:

```sh
ml/scenario-visualization/.venv/bin/python -m unittest discover -s ml/scenario-visualization -p 'test_*.py'
npm --prefix frontend run build
```

## Authenticated integration verification — October 11, 2026

The frontend now supports the authenticated backend when `VITE_REST_API_URL`,
`VITE_SUPABASE_URL`, and `VITE_SUPABASE_PUBLISHABLE_KEY` are configured. Production
builds refuse to silently fall back to the local development preview service.
The private worker credentials belong only on the backend and worker.

`backend/tests/test_face_preview_contract.py` exercises the real API, signed test
JWTs, private worker API and persistent job queue with a simulated image renderer.
It verifies consent, ownership of status/download/delete, idempotent submission,
input cleanup and deletion on consent revocation. It also verifies rejection of
unsupported sleep, mood, stress, connection, ingredients and product inputs.
These are not generative model features. The app explains this in the preview.
This test does not benchmark CUDA or establish any product-outcome accuracy.

Deployment target: AWS us-east-2. An AWS STS identity check succeeded, but EC2
inventory and GPU quota checks were denied by IAM (`ec2:DescribeInstances` and
`servicequotas:GetServiceQuota`). No AWS resource was created by these checks.
An authorized deployment role, backend HTTPS URL, Supabase configuration and
GPU capacity/budget are still needed before declaring the service live.

## Phone preview with the Mac model

Use this temporary development mode only on a trusted Wi-Fi network. The Mac must
remain awake, with the backend (port 8000), model and Vite processes running.
It runs the installed SDXL + IP-Adapter model on MPS; AWS credits are not used.

From this model directory, substitute the Mac's current Wi-Fi address:

```sh
REST_PREVIEW_ORIGINS="http://MAC_WIFI_IP:5175,http://127.0.0.1:5175,http://localhost:5175" .venv/bin/python local_api.py
```

From `frontend`, run `npm run dev:phone-model`, then open
`http://MAC_WIFI_IP:5175/#journal` on the phone and select **AI preview**.
Select an optional product, upload a photo, frame the face and small edit region,
then confirm photo processing and create the preview. The product is shown as a
reference card and is never used to predict skin changes.

`REST_PREVIEW_ORIGINS` adds only exact HTTP(S) localhost or unicast-IP origins with
explicit ports. No wildcard or arbitrary DNS names are accepted. Some networks
assign globally routable IPs, so private address classification is not required;
this setting is an origin allowlist, not a network firewall or authentication.
The model itself remains bound to loopback and is reached through Vite's
same-origin proxy. Do not port-forward these development services or publish them
to the internet. Update the exact origin and restart the model if Wi-Fi changes.
Use the authenticated HTTPS AWS backend for public deployment.
