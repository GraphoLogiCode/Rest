# Machine Learning

Added after rules-based matching is in place and evaluated.

## Generated images

Ingredient data is not an input to image generation in the first version. "Contains ingredient X" in a prompt does not establish how a formulation affects a particular person; a product-conditioned outcome model would need longitudinal data (product usage, duration, formulation, baseline photos, user context).

Keep three outputs separate:

| Input | Output |
|---|---|
| Verified product data | Product shortlist + explanation |
| Actual dated photos | Observed progress comparison |
| Reference photo | Optional illustrative generated image, not evidence of what a product will do |
