# Optional scenario visualization

Summary of the supplied InstantID notes, organized separately from product ranking and actual photo analysis. This is a proposed research feature, not an implemented or validated appearance predictor.

## What the feature does

Keep three experiences distinct:

| Experience | Inputs | Output |
|---|---|---|
| Product recommendations | Verified catalog, skin profile, preferences, routine, feedback | Explained product shortlist |
| Actual progress | Real dated photos and check-ins | Observed changes over time |
| Optional scenario illustration | Reference photo and a user-selected scenario | Clearly labeled generated portrait or scene |

The proposed illustration stack is **InstantID with an SDXL backbone**: identity conditioning from a reference face, with image-to-image editing and compatible spatial controls where needed. Start from the official implementation and test compatibility rather than assuming arbitrary pipelines can be combined. InstantID already uses face landmarks and an identity-specific ControlNet; additional spatial ControlNets are optional. [Official implementation](https://github.com/instantX-research/InstantID), [Diffusers image-to-image guide](https://huggingface.co/docs/diffusers/en/using-diffusers/img2img).

## How the three well-being inputs fit

Voluntary sleep, stress/mood, and social-connection check-ins use documented app scales, not clinical measurements. For an initial experiment, translate a selected scenario into explicit artistic instructions, such as a calm setting or an activity the user chose. This needs inference with existing models, not custom training.

Do not equate better sleep with erased under-eye features, better mental health with smiling, or social connection with clearer skin. Preserve facial proportions and natural skin texture. Do not pass product ingredients as if they predict a future face.

Show this label alongside every generated result:

> AI-generated illustration—not a prediction of your appearance or health.

Keep original photos unchanged and store generated assets separately. Obtain separate consent for generation and for training; protect and delete derived face embeddings along with associated user assets.

## What custom training would require

A research model relating check-ins to later appearance would require consented repeated photos, consistent capture conditions, time intervals, repeated check-ins, routine/product usage, and relevant context. Split evaluation by person and time. Synthetic before/after pairs do not establish real outcomes, and observational associations do not demonstrate that a lifestyle change caused an appearance change.

This dataset and validation work are outside the recommendation MVP. Prioritize real photo comparison and useful product recommendations first.

## Implementation constraint found during source review

The InstantID repository distinguishes its Apache-licensed code from research-only released checkpoints and noncommercial InsightFace face models. Treat this stack as a research candidate; resolve checkpoint and dependency permissions or select appropriately licensed components before commercial integration. [Repository disclaimer](https://github.com/instantX-research/InstantID#disclaimer).

Sources reviewed October 11, 2026.
