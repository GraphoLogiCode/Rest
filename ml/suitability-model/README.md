# Suitability model

Estimate reported helpfulness and tolerance from verified product facts, a self-reported skin profile, preferences, and the routine known at recommendation time. Later observed outcomes supply training labels, not inference-time inputs.

The initial model is a tabular classifier used to rank eligible products. Its score is not a diagnosis, a causal treatment effect, or a guarantee of tolerance. Explicit exclusions stay in backend rules regardless of score. Optional sleep, mental, and social check-ins are excluded from the first product-ranking model.

See the [training protocol](../ranking/README.md) for labels, features, model choices, and evaluation.
