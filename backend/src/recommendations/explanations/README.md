# Explanations

Which ingredients drove each recommendation, why, and how certain it is.

## Language model contract

The model explains a shortlist the backend has already selected. It does not choose products.

Input: the user's skincare goal, budget, reported ingredient allergies, and routine preference, plus each eligible product's verified label, supported ingredient notes, and source IDs.

Constraints sent with every request:

- Use only supplied product facts
- Do not invent concentrations or clinical benefits
- Do not claim the product treats sleep or mental health
- State missing information
- Do not promise a future appearance

Output per product: `product_id`, `reason`, `label_cautions`, `uncertainties`, `supporting_source_ids`.

## Validation

The backend checks that every returned `product_id` exists and that every quoted fact has supporting data.

## Evidence records

Every statement an explanation may make is backed by an evidence record:

| Field | Holds |
|---|---|
| `source` | Where the finding comes from |
| `population` | Who was studied |
| `study_design` | How it was studied |
| `finding` | What was found |
| `limitations` | What the finding does not show |
| `permitted_wording` | The wording Rest may use |

An explanation uses the permitted wording and never assigns a cause the evidence does not support. For example:

> Your routine and reported stress changed during the same period. This comparison cannot determine which contributed to the change.
