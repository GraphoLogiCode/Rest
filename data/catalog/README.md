# Reviewed product catalog

`products.json` is the only catalog loaded by the API. The 2026-10-11 review
checked all 27 candidates and published nine manufacturer records. Five cleansers
and moisturizers can enter preference matching; three serums and one mask are
available for browsing only. Eighteen remain unpublished for the specific gaps
in `VERIFICATION.md` and `verification-audit.json`. This is not a claim that all
27 are verified. Original staging files are retained unchanged.

A reviewer must check the exact formulation and label against the existing
verification workflow before adding a record. The runtime schema is
`backend/src/catalog/service.py`. It requires a verified date, formula version,
ingredient list, reviewed directions, source URL and reviewed warnings. An empty
warnings string means the reviewer verified there were no label warnings; null
means unknown and cannot be published without a reviewed warning summary.
Exact transcriptions use `directions_raw`/`warnings_raw`; faithful summaries use
`directions_summary`/`warnings_summary` and require
`review.text_representation: reviewed_summary`. Never put paraphrases in raw fields.
Prices may be null; supplied prices must
include a package size, currency, source and checked date.

These reviews use manufacturer pages and selected official back-label images, not purchased physical packages. Formula IDs
are Rest's dated ingredient-snapshot hashes, explicitly marked
`manufacturer_web_snapshot`; they are not manufacturer version or lot numbers.
Users must compare their package ingredients. Unknown warning text was not
replaced with an empty string. Two INKEY prices were verified against explicit
package sizes; all other package prices remain unknown. No efficacy evidence or
training outcomes were inferred from marketing claims or photographs.

Keep manufacturer claims distinct from reviewed evidence. Optional `goal_evidence`
entries contain `goal`, `statement`, `source_url`, and `review_status: reviewed`.
Do not copy marketing claims into this field. Unsupported goals return no match.
Catalog content is hashed with its declared version for reproducible decisions.
Invalid records or duplicate IDs fail loading rather than weakening the gate.

Run `python backend/scripts/catalog_report.py` to see candidate gaps. Set
`REST_CATALOG_PATH` to another reviewed JSON file for deployment/testing. The AWS
Compose setup mounts this directory read-only; restart the API after a reviewed
catalog update. Test fixtures use synthetic products and are never served by the
normal app.

Optional `image` metadata records the official HTTPS packaging photo URL, alt text,
manufacturer source page and checked date. The nine current product images were
selected from their manufacturer pages on 2026-10-11. Images are remotely hosted;
the preview card shows a fallback if a source becomes unavailable. Image inclusion
does not add efficacy evidence or alter recommendation matching.
