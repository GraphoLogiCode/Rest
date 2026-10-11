# Recommendation Service

Combines rules and model output into explained suggestions.

## Pipeline

```text
Verified product database
          │
User goals, allergies, budget, current routine
          │
          ▼
Eligibility filters and warning checks    (rules/)
          │
          ▼
Rank eligible product candidates
          │
          ▼
Retrieve their verified records
          │
          ▼
Language model explains the shortlist     (explanations/)
```

- Product records feed this pipeline, not an image-generation model.
- For a small catalog, ordinary database queries are enough: no fine-tuning and no vector database.
- The backend validates what the model returns. Prompt instructions alone are not the safety mechanism.
