# Products

Type, brand, price, full ingredient list.

## Record shape

Proposed schema (placeholder values, not a real product):

```json
{
  "product_id": "rest_product_001",
  "name": "Example Moisturizer",
  "brand": "Example Brand",
  "market": "US",
  "category": "moisturizer",
  "secondary_categories": [],
  "regulatory_class": "cosmetic",
  "texture": "cream",
  "package_sizes": [{ "value": 50, "unit": "ml" }],
  "formulation_version": {
    "version_id": "v1",
    "barcode": null,
    "lot": null,
    "label_version": null,
    "label_date": null,
    "dailymed_setid": null,
    "ndc": []
  },
  "ingredient_list_raw": "Water, Glycerin, ...",
  "ingredients_normalized": ["water", "glycerin"],
  "active_ingredients": [],
  "directions_raw": "Exact verified label text",
  "warnings_raw": "Exact verified label text",
  "usage_summary": null,
  "warnings_summary": [],
  "compatibility_restrictions": [],
  "manufacturer_claims": {
    "benefits": [],
    "skin_types": [],
    "skin_types_raw": []
  },
  "price": {
    "amount": null,
    "currency": "USD",
    "package_size": { "value": null, "unit": null },
    "checked_at": null,
    "source_url": null
  },
  "source_url": null,
  "verified_at": null,
  "verification_status": "pending"
}
```

## Fixed values

| Field | Allowed values |
|---|---|
| `category`, `secondary_categories` | `cleanser`, `moisturizer`, `serum`, `sunscreen`, `face_mask` |
| `regulatory_class` | `cosmetic`, `otc_drug` |
| `texture` | `balm`, `clay`, `cream`, `foam`, `gel`, `liquid`, `lotion`, `oil`, `powder`, or `null` |
| `unit` in `package_sizes` and `price.package_size` | `ml`, `g`, `fl oz`, `oz`, `lb`, as printed on the package |
| `manufacturer_claims.skin_types` | `dry`, `normal`, `combination`, `oily` |
| `review_status` in `compatibility_restrictions` | `pending`, `reviewed` |

The `texture` list is a starting point; extend it when the catalog needs another value.

## Rules

### Identity and version

- `secondary_categories` is for a product sold for two purposes, such as a moisturizer with SPF.
- An `otc_drug` record takes its `active_ingredients` and their concentrations from the Drug Facts label.
- A change to the ingredient list or to an active's strength is a new `version_id`. `product_id` plus `version_id` is the `product_version_id` in the [recommendation data contract](../recommendations/README.md), so outcomes recorded for one formula never carry over to another.
- `barcode` and `lot` come from the package that was verified. `label_version`, `label_date`, `dailymed_setid`, and `ndc` apply to OTC drugs listed in DailyMed.
- `texture` is `null` when the label does not name one.

### Ingredients and label text

- Keep `ingredient_list_raw` alongside `ingredients_normalized` so parsing errors can be audited.
- `directions_raw` and `warnings_raw` hold the exact label text.
- `usage_summary` and `warnings_summary` are paraphrases. They never stand in for the raw fields.
- Each `compatibility_restrictions` entry is `{ "statement", "source_url", "review_status" }`. Only a `reviewed` entry may drive a rule.

### Price

- `price.package_size` names the size the price is for. A price with no size cannot be compared with another product's.
- `price.source_url` is where the price was read, which can differ from the product's `source_url`.
- Unit price is computed, never stored. Compare volume with volume and weight with weight.

### Manufacturer claims

- `manufacturer_claims` holds what the manufacturer advertises. It is not an input to goal matching or ranking; goal relevance comes from [ingredient evidence](../ingredients/README.md).
- `skin_types_raw` keeps the source wording. `skin_types` maps it to the fixed list: "all skin types" becomes all four values, a range such as "normal to dry" becomes its two ends, and wording that is not a skin type, such as "sensitive", stays in `skin_types_raw` only.

### Evidence boundaries

- Never estimate a concentration: an undisclosed one is `null`. U.S. cosmetic labels list ingredients in descending order of predominance, with ordering exceptions at 1% or less, so list position does not give a percentage ([FDA cosmetics labeling guide](https://www.fda.gov/cosmetics/cosmetics-labeling-regulations/cosmetics-labeling-guide)).
- Keep four kinds of information separate, never merged into one "effectiveness score":
  - Label facts: what the product contains and says
  - Ingredient evidence: supported information about an ingredient
  - Marketing claims: what the manufacturer advertises
  - User feedback: what a particular user experienced
