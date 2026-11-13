# Well-Being Context

Friend's research area. Used to separate lifestyle effects from product effects.

## Use in recommendations

The three pillars personalize the experience. They do not produce ingredient matches; product matching comes from the user's skincare concern and product history.

| Input | Use |
|---|---|
| Sleep and schedule | Adapt check-in timing and routine reminders |
| Self-reported stress | Offer a simpler routine if the user prefers less complexity |
| Social connection and confidence | Let the user define personal goals without judging appearance |

- Do: "You said you prefer a short routine and have a $20 budget. This product fits those preferences."
- Don't: "Your stress score means you need this chemical ingredient."

A preference-based recommendation is not a medically supported treatment recommendation.

Whether context improves product ranking is tested as a research comparison before it is used; see the [training protocol](../../../ml/ranking/README.md#testing-whether-well-being-context-helps).

## Summaries

`GET /v1/summary?period=week|month` returns counts, a sleep average, and how many days have a check-in. The wording is fixed in `summary.py` and never states a cause. `POST /v1/insights/{id}/feedback` records whether a summary was useful.
