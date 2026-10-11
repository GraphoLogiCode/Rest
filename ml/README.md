# Machine Learning

Added after rules-based matching is in place and evaluated.

## Plans by responsibility

- [Recommendation ranking and training](ranking/README.md): start with rules, then compare tabular models using consented outcomes.
- [Suitability model](suitability-model/README.md): meaning and limits of the learned score.
- [Scenario visualization](scenario-visualization/README.md): summary of the InstantID/SDXL proposal; illustrative generation is separate from photo measurements and ranking.
- [Recommendation data contract](../data/schema/recommendations/README.md): what the app needs to record before training.

## Generated images

Ingredient data is not an input to image generation in the first version. "Contains ingredient X" in a prompt does not establish how a formulation affects a particular person; a product-conditioned outcome model would need longitudinal data (product usage, duration, formulation, baseline photos, user context).

Keep three outputs separate:

| Input | Output |
|---|---|
| Verified product data | Product shortlist + explanation |
| Actual dated photos | Observed progress comparison |
| Reference photo | Optional illustrative generated image, not evidence of what a product will do |
