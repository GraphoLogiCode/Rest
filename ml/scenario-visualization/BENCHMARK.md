# Local feasibility result — October 11, 2026

**SDXL + IP-Adapter Plus Face runs successfully on this M5 Mac with 24 GB unified memory.** It is ready for a local illustration prototype. It has not been validated for exact identity preservation, skincare outcome prediction, mobile inference, or production serving.

## Measured results

Both runs used the public-domain reference documented in `reference-source.json`, the same face crop, seed 42, 20 denoising steps, guidance 5.0, adapter scale 0.7, fp16 generation, and Apple MPS. Each ran in its own process with a fresh model load, using local files and offline inference. No training was performed.

| Image size | Model load | Generation | Total | Sampled Metal driver maximum |
|---|---:|---:|---:|---:|
| 512 × 512 | 9.2 s | 13.2 s | 22.4 s | 10.8 GiB |
| 768 × 768 | 7.9 s | 18.2 s | 26.2 s | 14.0 GiB |

Process peak RSS was approximately 3.8–3.9 GiB. This overlaps with unified GPU memory accounting and must not be added to the Metal numbers. Driver allocation was sampled after loading and at generation steps; it may miss transient peaks. These are two single runs, not latency percentiles or a concurrency/load test.

The pinned model files total 10,317,104,924 bytes (about 9.6 GiB before filesystem/cache overhead). All selected files passed size verification and all six safetensors files passed SHA-256 verification. The first accelerated transfer stalled; the reproducible downloader uses standard HTTPS instead.

[Machine-readable results](benchmark-results.json), [pinned models](models.lock.json), [exact Python dependency versions](requirements.lock.txt).

## Visual inspection

### Follow-up: preserve everything outside a selected face region

The new recommended entry point is `run_face_edit.py`. It uses the same local weights through the SDXL inpainting pipeline, starting with the original face crop. A final masked composite restores exact original pixels outside the selected region; it does not regenerate the body or background.

The cheek-only test used `--face-box 145 10 325 190 --edit-box 178 116 208 139`, 512-pixel model input, strength 0.25, and 30 scheduled steps (7 actual denoising steps). It took **5.1 seconds** to generate after a **9.6-second** load. Sampled Metal driver allocation reached **11.0 GiB**.

Of 538 pixels selected in the original photo, 537 changed. **Zero pixels outside the mask changed.** Inspection showed the original framing, hair, expression, and surrounding face retained, with a subtle localized cheek edit. This verifies spatial preservation, not cosmetic benefit. The photo area in the saved PNG is checked separately from its added disclosure footer.

[Face-only comparison](.local/outputs/face-edit-cheek/face-comparison.png). Four automated tests also passed: exact preservation outside the mask, rejection of an out-of-face selection, rejection of empty/wrong-size masks, and invalid face-box rejection. These are manually selected regions; automatic face detection and a mask-painting UI are not implemented.

### Earlier full-portrait experiment

Both outputs were nonblank, recognizable portraits with broad similarity to the reference's hairstyle and facial appearance. They changed facial details, texture, framing, clothing, and background. The 768-pixel result has more visible detail, but is still a generated interpretation of the person. No numerical identity-accuracy claim is supported by these two examples.

The prompt requested natural texture, yet skin appearance still changed. This confirms that prompt wording alone does not preserve an observed skin condition. Do not display these images as evidence of improvement, use them as training outcome labels, or attribute their changes to products, sleep, stress, or social connection.

Local outputs (ignored by Git):

- [512-pixel comparison](.local/outputs/test-512/comparison.png)
- [768-pixel comparison](.local/outputs/test-768/comparison.png)

Each comparison labels the left image as the reference and the right as a generated scenario. The standalone generated image includes a visible non-prediction disclosure. These are test assets, not participant data or endorsement.

## What is ready and what comes next

| Item | Status |
|---|---|
| Model download and integrity checks | Completed |
| Apple GPU inference | Passed at 512 and 768 pixels |
| Reusable local command with custom reference support | Implemented in `run_local.py` |
| Offline execution and visible illustration labeling | Implemented |
| Real before/after photo comparison | Separate feature; generation is not a substitute |
| HTTP job API for the app | Not implemented by this experiment |
| Identity consistency across users and skin tones | Not evaluated |
| Concurrent requests, cancellation, retention, authentication | Not implemented |
| Mobile/on-device deployment | Not tested |

The frontend's current illustration client defines `POST /jobs` with `reference`, `scenario`, and `consent`, and polling with `GET /jobs/{id}`. A next integration step is a local job service that wraps this model behind that contract, processes one job at a time, reports failures, and serves labeled images. A persistent worker could avoid per-request reloads, but that improvement has not been benchmarked. Keep the service bound to localhost during development.

Map user-selected scenarios to explicit artistic settings, not promised health changes. The CLI currently takes a text prompt; no sleep/stress/social numeric encoder has been trained or implemented. The two runs establish only a technical starting point for optional illustrations.

See [setup and run commands](LOCAL_SETUP.md). Weights, photos, generated images, and the virtual environment remain in `.local/` or `.venv/`, outside Git. No application routes were changed and no model/data was uploaded.

## App integration check — October 11, 2026

A real browser uploaded the public-domain astronaut sample through the local
Rest journal, selected face `[145,10,325,190]` and cheek `[178,116,208,139]`, and
requested a subtle preview with gentle brightening. The SDXL worker completed
and the app displayed the original and labeled illustration in matching frames.
A separate comparison of the saved PNG found **538 changed pixels inside the
mask and zero outside**. Only the labeled output remained after processing;
the UI delete action then removed that output directory. Frontend production
build and five local API/region unit tests passed. This verifies integration and
pixel confinement on one sample, not identity quality across users or product
efficacy. UI screenshot is a local ignored artifact in
`output/playwright/face-preview.png`.
