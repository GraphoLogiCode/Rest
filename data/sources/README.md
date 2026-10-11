# Data sources

Ingestion and verification of product and ingredient data (e.g., EU CosIng, Open Beauty Facts).

## MVP catalog

Hand-curate about 20–30 products in a few categories (cleansers, moisturizers). Add acne treatments only when their full label directions and warnings can be preserved.

A product qualifies when it has:

- An identifiable name, variant, and market
- A complete ingredient list from the packaging or manufacturer
- Directions and warnings
- A recorded source and verification date
- Price and package size, if cost will be compared

## Sources

- Packaging and manufacturer information are the primary source.
- DailyMed for U.S. OTC acne treatment labels: active ingredient concentration, purpose, uses, warnings, directions, inactive ingredients ([example label](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7441981a-654d-4f18-be21-66c863ee6d6f)). It is not a catalog of ordinary cosmetics.
- Advertising claims and customer reviews are never the primary source for ingredient effectiveness.

## Flow

Parse → normalize → manually verify → product database. A record stays `pending` until it is verified.

Pending records waiting for verification are in [candidates/](candidates/README.md).
