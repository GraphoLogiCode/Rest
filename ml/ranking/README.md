# Recommendation ranking

Train only after the rules MVP collects consented, attributable usage outcomes. The first learned system should rank products that already passed eligibility rules. It should estimate reported usefulness, not diagnose skin or predict a future face.

## Model progression

| Stage | Method | Training needed? |
|---|---|---|
| MVP | Versioned rules and explicit preference matching | No |
| First experiment | Regularized logistic regression on tabular user/product features | Yes, labeled usage episodes |
| Challenger | CatBoost classifier for nonlinear interactions in tabular data | Same outcome data and held-out splits |
| Later, if justified | Learning-to-rank model grouped by recommendation request | Multiple comparable, observed candidate labels per request |

Logistic regression provides a simple classification baseline; CatBoost supports categorical features. Neither is pre-trained to understand Rest users. These are proposed choices to compare experimentally, not a claim that one will win. [scikit-learn logistic regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [CatBoost classifier](https://catboost.ai/docs/en/concepts/python-reference_catboostclassifier).

Skip collaborative filtering and deep neural networks initially: this small, new catalog will have sparse user histories. Product/profile features can support new users and new products without relying on learned user IDs.

## Define the target before fitting

For a first experiment in the cleanser/moisturizer pilot, define `helpful_and_tolerated_28d`:

- **1:** actual use confirmed, the 28-day follow-up window completed, helpfulness rated 4–5/5, and an explicit report of no irritation during that window.
- **0:** actual use confirmed and an explicit irritation report within the window, or a completed window with helpfulness rated 1–2/5.
- **Unknown / excluded:** no confirmed use, incomplete follow-up without an explicit negative event, neutral rating of 3, or missing information needed to assign the label.

This is a proposed study label, not a clinical endpoint. Report exclusions and response rates; filtering to decisive answers introduces selection bias. Record early negative events immediately, but in offline comparisons include an episode only once its whole scheduled window has elapsed at the dataset cutoff. This avoids comparing early negatives with positives that have not had time to mature.

Model output describes the labeled pilot population. It is not a universal probability of benefit. Keep reaction reports visible as a separate evaluation outcome; no model score overrides a known exclusion.

## Features available at recommendation time

Use category, verified ingredient presence/functions, known formulation facts, price/budget fit, self-reported skin concerns, explicit preferences, and routine summary. Ingredient presence does not establish concentration or formulation effectiveness. Add reviewed user–product match features rather than unrestricted health claims.

Use missing-value indicators and distinguish unknown allergies from explicitly reported none. Start without raw photos, face embeddings, sensitive free text, sleep/stress/social scores, or raw user IDs. Product IDs join records but should not dominate prediction; evaluate unseen formulations separately.

Never use later reactions, continuation, post-recommendation check-ins, or future catalog edits as input features. Historical aggregates must be computed from records available before the request, with the same computation used at serving time.

## Training procedure

1. **Export:** join consented episodes to the decision-time profile, routine, and product versions using the [data contract](../../data/schema/recommendations/README.md). Deduplicate episodes and reject generated/synthetic records from measured training and evaluation.
2. **Freeze labels:** apply the documented label version and outcome-window cutoff. Report users, episodes, products, positive/negative counts, follow-up completion, and exclusions.
3. **Split:** reserve disjoint user cohorts for train, validation, and final test. Also use chronological boundaries: training labels must have matured and been recorded before the validation prediction period; validation labels before the test period. Keep only rows meeting both the user and time constraints. If this leaves too little data, stay with rules. Avoid a random row split that puts the same user's episodes on both sides. [Cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html).
4. **Preprocess:** fit ingredient vocabularies, category encoders, imputation, and numeric scaling on training rows only. Encode unseen categories explicitly. Save the preprocessing pipeline with the model.
5. **Fit baselines:** train regularized logistic regression; compare a modest CatBoost configuration on the identical split. Use validation data for hyperparameters and stopping. Start on CPU; a small tabular experiment does not require a diffusion GPU job.
6. **Evaluate:** inspect precision–recall metrics, log loss, calibration, and results by product/category and relevant user groups. Use user-level uncertainty intervals. Compare against the rules baseline on recommendation quality, not just classifier accuracy.
7. **Freeze and test:** choose the model using validation results, then evaluate the untouched test cohort once. Save the model, feature/label versions, dataset manifest, split IDs, seed, package versions, and evaluation report.
8. **Roll out:** run in shadow mode, then a limited evaluated rollout after passing the [evaluation gates](../../evaluation/README.md). Keep hard rules and a rules-only fallback. Retrain when enough new mature outcomes justify it, with a new version and the same gates.

Training minimizes classification loss between the predicted score and observed labels. Serving applies the saved transformations to each eligible user–product pair and orders candidates by score. Keep score interpretation internal until calibration and population coverage support user-facing probabilities.

## When ranking-specific training becomes useful

A pairwise/listwise ranker needs meaningful comparisons within each request. In ordinary usage, a person may try only one candidate; that does not provide outcomes for the alternatives. Never label untried candidates as failures to manufacture ranking groups. CatBoost offers ranking objectives, but usable grouped labels must come first. [Ranking objectives](https://catboost.ai/docs/en/concepts/loss-functions-ranking).

Display position, exposure policy, and selective feedback bias the collected data. Log those factors. A small randomized comparison among already eligible candidates can support evaluation when appropriate; log actual assignment probabilities if used. Do not infer unbiased policy value from historical clicks alone.

There is no fixed sufficient sample count. Begin with a consented pilot; assess independent-user counts, outcome coverage, learning curves, and uncertainty. A large number of events from a few users is not a large independent training set. Do not promote a model just because a target row count was reached.

Sources reviewed October 11, 2026. No model has been trained in this repository.
