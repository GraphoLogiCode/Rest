# Recommendation data contract

Proposed logical schema; migrations are not implemented. Collect the minimum data needed for the requested feature. Photos are unnecessary for the first recommendation model.

## Data to collect

| Entity | Minimum fields | Source and purpose |
|---|---|---|
| Product version | Product/variant ID, formulation version, category, full normalized and raw ingredients, label directions/warnings, market, price/currency/date, verification/source | Packaging or manufacturer records, manually verified; candidate facts |
| Ingredient evidence | Canonical ID, aliases, supported function, source, evidence limitations, review date | Reviewed ingredient references; matching and explanations, not automatic efficacy labels |
| Profile snapshot | Pseudonymous user ID, timestamp, self-reported skin type/concerns, reported ingredient exclusions, preferences, budget/currency | Onboarding and edits; record unknown separately from an explicit empty answer |
| Routine / usage episode | Episode ID, product version, start/stop dates, use frequency, other products, stop reason | User-confirmed usage; a purchase or click is not proof of use |
| Decision request | Request ID/time, profile/routine snapshot IDs, eligible candidates, exclusions, catalog/rule/model versions | Backend; reproduce what was knowable when recommendations were made |
| Impression / action | Event ID, request ID, product version, timestamp, visible position, event type | App; distinguish shown, opened, saved, dismissed, and started-use |
| Outcome | Episode ID, request attribution if known, observation and ingestion times, follow-up window, helpfulness rating, reported irritation, goal-change report, continuation/stop reason | Structured follow-up; evidence of reported experience rather than clinical effectiveness |
| Optional check-in | Timestamp, sleep/stress/social scale values and scale version, missing flags | Voluntary context; initially excluded from product ranking features |
| Consent record | User ID, scope, notice version, grant/revocation time | Separate service use, model training, photo storage, and generation choices |

Existing [product schema](../products/README.md) and [source policy](../../sources/README.md) remain the foundation. Add stable formulation versions and source-history records before collecting training outcomes. A reformulation must not silently inherit outcomes for the old formula.

## Training row

One row represents one attributed **user–product usage episode**, anchored to the recommendation time. Repeated follow-ups update the episode's label window rather than creating duplicate independent examples. Episodes without a traceable recommendation belong in a separate analysis dataset.

```json
{
  "episode_id": "example_episode_001",
  "request_id": "example_request_001",
  "user_id": "pseudonymous_example",
  "product_version_id": "example_product_v1",
  "feature_cutoff": "2026-08-01T12:00:00Z",
  "features": {
    "skin_type": "dry",
    "requested_category": "moisturizer",
    "budget_fit": true,
    "texture_preference_match": null,
    "routine_product_count": 2
  },
  "outcome": {
    "observed_at": "2026-08-29T12:00:00Z",
    "recorded_at": "2026-08-29T12:05:00Z",
    "window_complete": true,
    "helpfulness_1_to_5": 4,
    "reported_irritation": false,
    "label_helpful_and_tolerated": 1
  },
  "training_consent": true,
  "synthetic_example": true
}
```

This is an illustrative contract, not collected data or a training fixture. Actual exports must include schema/label versions and a snapshot of consent eligibility. Check current revocation status again when exporting or retraining.

## Collection and label rules

- For the initial cleanser/moisturizer pilot, propose an early tolerability check and a 28-day usefulness follow-up. These are product-research windows, not clinical timelines or instructions to keep using an irritating product.
- Preserve individual outcome fields. Compute labels in the training pipeline using a versioned definition, never from client-supplied label values.
- No follow-up means unknown. Not shown, not purchased, and not clicked do not mean the product failed.
- Record actual use, missed use, other routine changes, and why someone stopped. Budget-related stopping is different from a reaction report.
- Keep event time and ingestion time so late submissions cannot leak into historical features or simulated deployments.
- Use unique event IDs and stable episode IDs; reject impossible dates, invalid scales, duplicate events, and feedback for another user's episode.
- Catalog data supplies features. Public star ratings, marketing claims, generated portraits, and synthetic feedback do not supply reliable Rest outcome labels. No suitable longitudinal dataset has been established for this project yet.

Use pseudonymous IDs in model exports and keep identifying account data separately. Define retention for events and exports; remove revoked/deleted records from future datasets and track which model versions used them. Do not claim deleting a row automatically removes its influence from an already trained model.
