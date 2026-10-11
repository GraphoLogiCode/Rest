# Recommendation engine: build plan

Status: proposed design for the Rest skincare app. The repository currently contains a documentation scaffold; this document does not claim a running service or a trained model.

## What to build first

Recommend a short list of products for an explicitly requested category and goal, with evidence-backed reasons, budget fit, and relevant label cautions. Start with the existing plan for 20–30 manually verified products. A relational database and deterministic rules are sufficient for this catalog.

Use three separate components:

1. **Eligibility rules:** enforce catalog verification, explicit user constraints, reported ingredient exclusions, and applicable label restrictions.
2. **Ranking:** order eligible candidates by explicit preferences initially; later compare a learned model against that baseline.
3. **Explanations:** render reasons from verified facts and rule results. Templates are sufficient initially; an optional language model follows the existing [explanation contract](explanations/README.md).

```text
Profile + requested category + routine + preferences
                         |
Verified catalog -> eligibility rules -> candidate ranking
                                             |
                                  verified reasons + cautions
                                             |
                                    shortlist shown in app
                                             |
                         impressions -> usage -> follow-up feedback
                                             |
                                offline training and evaluation
```

Generated images have no role in eligibility, scoring, or training labels. Sleep, stress, and social check-ins remain optional context for reminders and user-chosen routine simplicity; they do not establish ingredient needs.

## Rules and ranking without training

Use exact product variants and formulation versions. Normalize ingredient aliases against reviewed mappings. A missing ingredient list cannot pass an allergy screen. A reported allergy match excludes a product, but the absence of a match is not a guarantee of tolerance.

Require a known price in the requested currency when enforcing a hard budget. Return a missing-information state when required profile information is absent. Apply only reviewed, sourced label restrictions and compatibility rules; do not invent universal ingredient conflict lists.

For eligible products, use a transparent, versioned ordering:

1. Match the requested category and documented goal relevance.
2. Match explicit preferences, such as texture and desired routine complexity.
3. Prefer affordability using a consistent comparison basis.
4. Break ties by stable product ID.

Treat an unknown preference match as unknown rather than false. Display only reasons supported by records. Return fewer results, including none, if too few products qualify; never relax a hard constraint to fill the list. Do not describe a rule score as a probability that a product will work.

## Proposed service contract

These endpoints describe future implementation, not existing routes.

| Operation | Request | Response / behavior |
|---|---|---|
| `POST /recommendations` | Authenticated profile reference, category, goal, budget, preferences | Request ID, catalog/rules/model versions, ranked product IDs, reasons, cautions, missing information |
| `POST /recommendation-events` | Request ID, product ID, displayed position, event type, event ID | Idempotent acknowledgement; verify the product belonged to that request |
| `POST /usage-episodes` | Product version, actual start date, initial routine snapshot | Usage episode ID |
| `POST /outcomes` | Usage episode ID, observation time, helpfulness, reaction report, continuation/stop reason | Saved structured feedback; missing answers stay missing |

Resolve user identity from authentication. Enforce ownership of profiles, requests, episodes, and feedback. Use the server's feature snapshot at recommendation time instead of trusting client-supplied features or eligibility results.

Log a recommendation response separately from a confirmed visible impression. Capture all eligible candidates and exclusion reason codes in an access-controlled decision record; this makes later evaluation auditable. Never put raw photos or sensitive free text in recommendation event logs.

## Build sequence

| Stage | Deliverable | Completion evidence |
|---|---|---|
| 1. Catalog and profile | Versioned product records, consent, goals, budget, routine | Verified catalog; missing data represented explicitly |
| 2. Rules MVP | Filtering, stable ranking, explanation templates | Constraint tests pass, including empty-result cases |
| 3. Feedback collection | Display events, actual usage, structured follow-ups | Events join to the correct request and product version; duplicates rejected |
| 4. Offline model | Feature export, baseline comparison, saved model | [Training protocol](../../../ml/ranking/README.md) and held-out evaluation completed |
| 5. Controlled rollout | Model serving behind the same eligibility rules | Better user usefulness with acceptable reaction-report and constraint metrics; rollback available |

Keep database migrations under `data/migrations/`, serving code here, training code under `ml/ranking/`, and evaluation reports under `evaluation/`. Reuse one feature specification for training and serving. If model loading or feature validation fails, use the rules baseline.

Read next: [data contract](../../../data/schema/recommendations/README.md), [model training](../../../ml/ranking/README.md), [evaluation](../../../evaluation/README.md).
