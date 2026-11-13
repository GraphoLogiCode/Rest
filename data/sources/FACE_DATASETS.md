# Face and skin dataset review — 2026-10-11

No dataset checked here establishes before/after outcomes for Rest's 27 catalog
products. Product preference matching can run without face training data. Keep
research images separate from real user progress and AI illustrations.

| Source | Available data | Fit for Rest | Reuse status |
| --- | --- | --- | --- |
| [Google SCIN](https://github.com/google-research-datasets/scin) | More than 10,000 consented dermatology images with condition, symptom and skin-tone annotations; not a product treatment series | Candidate for research evaluation across varied skin images; no product-effect training labels | Custom [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE), not a generic CC license. Preserve attribution/license and modification notices; re-identification is prohibited. Privacy/publicity rights are not licensed. Official README links the download bucket and demo notebook. |
| [Han et al. facial erythema supplement](https://data.mendeley.com/datasets/4bbzbmywrm/1) | Repository describes three patients at baseline, week 2 and week 12 | A small paired clinical example to investigate, not a training set or evidence for our products | Repository lists CC BY 4.0. Full images, associated treatment protocol and participant display consent have not been reviewed. Do not publish faces in Rest until those are resolved. |
| [Goldberg et al. laser study supplement](https://data.mendeley.com/datasets/998kjx97m3/1) | Two supplementary figures and legends in one PDF | Clinical laser-treatment examples; no basis for attributing results to moisturizers or cleansers | Repository lists CC BY 4.0 and requests manuscript citation. Image contents and participant display rights still need review. |
| [Bae cold-plasma acne trial](https://datadryad.org/dataset/doi:10.5061/dryad.12jm63z3t) | 40 participants, baseline/week 6/week 10; sebum measurement screenshots and fluorescence images | Longitudinal measurement research, not ordinary face photos for a before/after slider. Both groups also used adapalene and received physician cleansing | Download is about 478 MB. Individual-file licensing/display review not completed. No download needed for the current face demo. |

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) permits sharing and
adaptation, including commercially, subject to attribution and its other terms.
It does not automatically grant privacy/publicity rights or justify a claim
about a different treatment. A repository license and consent to advertise an
identifiable person's results are different checks.

## Implementation decision

No face images were downloaded, added to the app, or used to train a model in
this review. For the hackathon, use a volunteer's own consistently captured,
dated photos with permission to display them. Label those as observed progress
with the actual routine and elapsed time; they do not establish causation.
Keep any generated preview labeled as an illustration, without implying a
predicted product outcome. A public clinical example must preserve its actual
treatment, attribution and limitations, and must not be presented as a Rest result.

For future training, collect consenting users' same-person dated images,
capture-quality checks, exact product/formulation, actual usage, other routine
changes, helpfulness/irritation reports and optional context. Separate training
consent from app use. Split evaluation by user and later time period. Existing
public skin datasets can supplement vision evaluation; they cannot supply the
missing longitudinal product outcomes.
