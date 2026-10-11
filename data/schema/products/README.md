# Products

Type, brand, price, full ingredient list.

## Record shape

Proposed schema (placeholder values, not a real product):

```json
{
  "product_id": "rest_product_001",
  "name": "Example Moisturizer",
  "market": "US",
  "category": "moisturizer",
  "ingredient_list_raw": "Water, Glycerin, ...",
  "ingredients_normalized": ["water", "glycerin"],
  "active_ingredients": [],
  "directions_raw": "Exact verified label text",
  "warnings_raw": "Exact verified label text",
  "price": { "amount": null, "currency": "USD", "checked_at": null },
  "source_url": null,
  "verified_at": null,
  "verification_status": "pending"
}
```

## Rules

- Keep `ingredient_list_raw` alongside `ingredients_normalized` so parsing errors can be audited.
- `directions_raw` and `warnings_raw` hold the exact label text.
- Never estimate a concentration: an undisclosed one is `null`. U.S. cosmetic labels list ingredients in descending order of predominance, with ordering exceptions at 1% or less, so list position does not give a percentage ([FDA cosmetics labeling guide](https://www.fda.gov/cosmetics/cosmetics-labeling-regulations/cosmetics-labeling-guide)).
- Keep four kinds of information separate, never merged into one "effectiveness score":
  - Label facts: what the product contains and says
  - Ingredient evidence: supported information about an ingredient
  - Marketing claims: what the manufacturer advertises
  - User feedback: what a particular user experienced
