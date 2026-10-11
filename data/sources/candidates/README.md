# Candidate product records

27 unverified product records gathered on 2026-10-11, staged for the [verification flow](../README.md). Every record is `pending`. None has been checked against packaging, so none may be shown to users or used for an allergy screen yet.

| File | Category | Records | Source |
|---|---|---|---|
| [cleansers.json](cleansers.json) | `cleanser` | 6 | Manufacturer pages |
| [moisturizers.json](moisturizers.json) | `moisturizer` | 6 | Manufacturer pages |
| [serums.json](serums.json) | `serum` | 5 | Manufacturer pages |
| [sunscreens.json](sunscreens.json) | `sunscreen` | 5 | DailyMed labels (OTC drugs) |
| [face-masks.json](face-masks.json) | `face_mask` | 5 | Manufacturer pages |

## How the records were gathered

Each record comes from one page, named in `source_url`. Pages were read by an automated reader, so ingredient lists are machine transcriptions: compare each one to the packaging during verification. A value the page did not show is `null` or empty and is named in the record's `staging.missing` list. Nothing is estimated.

## Record shape

Each record has every field of the [product schema](../../schema/products/README.md), in the schema's order and with its fixed values, plus one `staging` object that is not part of the schema:

| `staging` field | Holds |
|---|---|
| `source_type`, `retrieved_at` | `manufacturer_page` or `dailymed_label`, and the retrieval date |
| `label_uses` | The "Uses" section of an OTC drug label |
| `manufacturer_stated_concentrations` | Percentages the manufacturer advertises for a cosmetic. Claims, not label facts |
| `price_note` | Why a price has no package size, or what else the source showed |
| `missing` | Schema fields the source did not supply |
| `notes` | Source contradictions and open questions |

Schema fields that are empty in every record:

- `directions_raw` and `warnings_raw`: reserved for exact label text, which has to be transcribed from the packaging.
- `texture`: not collected.
- `formulation_version.version_id`, `barcode`, and `lot`: assigned or read from the package at verification.

`ingredient_list_raw` is the source's list in source order, re-joined with commas. `ingredients_normalized` is only lowercased and trimmed. Aliases are not resolved: water alone appears under 9 spellings across these records.

## Coverage

| Field | Records with it (of 27) |
|---|---|
| Ingredient list | 25 |
| Price tied to a package size | 5 |
| Price with no size given | 11 |
| No price | 11 |
| Formulation version | 5 (DailyMed label version and NDC codes; no barcode or lot) |
| Exact label directions and warnings | 0 |
| Skin types mapped to the fixed list | 20 |
| Texture | 0 |

## Known limits

- La Roche-Posay, Neutrogena, and Kiehl's product pages refuse automated access, so those brands appear only through DailyMed sunscreen labels.
- The Ordinary shows its full ingredient list behind an interactive control. Two of its five records have no ingredient list.
- Several sources contradict themselves. Each case is recorded in that record's `staging.notes`.
- 12 of the 27 records are in the cleanser and moisturizer pilot categories. Serums, sunscreens, and masks are outside the pilot the [recommendation design](../../../backend/src/recommendations/DESIGN.md) describes.
