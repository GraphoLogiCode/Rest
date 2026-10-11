# Evaluation

- Recommendation quality vs. user-reported outcomes
- Photo comparison consistency
- User understanding and confidence
- Continued use

## Recommendation release gates

These are proposed acceptance criteria; no evaluation has been run yet.

| Area | Check |
|---|---|
| Rules | No known hard-constraint violations in reviewed cases; test reported exclusions, unknown ingredient lists, missing prices/currency, missing profile data, and empty candidate sets |
| Explanations | Every stated product fact traces to the selected verified record; no invented benefits or concentrations |
| Data integrity | Events are deduplicated, outcomes join to the correct user/episode/formulation, and features predate the decision |
| Offline model | Compare rules and learned scoring on held-out users and later periods; report label coverage, precision–recall metrics, log loss, calibration, and user-level uncertainty |
| Ranking quality | Use blinded preference judgments or sufficiently observed candidate outcomes; report top-k usefulness and NDCG only where comparable relevance labels actually exist |
| Coverage | Inspect categories, new users, new formulations, and self-reported skin-profile groups; suppress strong claims where samples are sparse |
| Online usefulness | Compare helpfulness, reported irritation, follow-up completion, and dismissals with rules; clicks alone do not establish success |
| Operations | Model failures fall back to rules; versioned artifacts allow rollback; consent revocations affect future exports |

Historical logs do not reveal what would have happened with untried products. Report this limitation in every offline comparison. Before a prospective pilot, specify its primary outcome, duration, sample-size rationale, allowable reaction-report difference, and stopping criteria. A model ships only if the comparison supports improved usefulness without worse constraint compliance or unacceptable reaction-report outcomes. Thresholds are project decisions to document before examining test results.

## Evidence about Rest itself

Test the app, not only the model:

- Do users understand their product choices better?
- Do they find the recommendations useful?
- Can they read their progress without mistaking an association for a cause?

A prospective comparison can measure the app's benefit. Observational histories alone cannot prove a product's effect.

## Image features

Assess real-photo comparison for alignment and capture consistency. Evaluate optional generated illustrations separately for identity preservation, unwanted changes, and whether users understand the limitation label. Never treat a realistic generated image as evidence of product effectiveness or well-being improvement.

Related: [training protocol](../ml/ranking/README.md), [illustration proposal](../ml/scenario-visualization/README.md).
