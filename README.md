# Rest

A skincare decision-support app that helps people feel more confident. It uses product and ingredient data to help users make informed product choices, shows before-and-after comparisons so users can see how their skin changes and evaluate their routines, and takes sleep, mental, and social well-being into account so lifestyle effects aren't mistaken for product effects.

See [`PROJECT_TREE.md`](PROJECT_TREE.md) for the full concept tree.

## Repository layout

```
rest/
├── PROJECT_TREE.md              # Concept tree (sections 1–9)
│
├── frontend/                    # 7. Frontend
│   └── src/
│       ├── screens/
│       │   ├── onboarding/          # 3. Skin profile, sensitivities, budget
│       │   ├── products/            # 2. Search, ingredient breakdown
│       │   ├── routine/             # 3. Current routine, reaction log
│       │   ├── photos/              # 4. Guided capture
│       │   ├── compare/             # 4. Before-and-after views, timeline
│       │   ├── check-in/            # 5. Well-being context
│       │   │   ├── sleep/
│       │   │   ├── mental/
│       │   │   └── social/
│       │   ├── recommendations/     # 6. Explained suggestions + feedback
│       │   ├── dashboard/
│       │   └── settings/privacy/    # 8. Photo opt-in, data deletion
│       ├── components/
│       └── services/
│
├── backend/                     # 7. Backend
│   └── src/
│       ├── auth/
│       ├── api/
│       │   ├── products/            # Product & ingredient API
│       │   ├── profile/
│       │   ├── routine/
│       │   ├── photos/
│       │   └── checkins/
│       ├── ingredients/             # 2. Ingredient knowledge base
│       ├── visualization/           # 4. Before-and-after pipeline
│       │   ├── capture-checks/
│       │   ├── alignment/
│       │   └── comparison/
│       ├── context/                 # 5. Well-being context
│       │   ├── sleep/
│       │   ├── mental/
│       │   └── social/
│       ├── recommendations/         # 6. Decision support
│       │   ├── rules/
│       │   ├── explanations/
│       │   └── feedback/
│       └── privacy/                 # 8. Consent, encryption, deletion
│
├── data/                        # 2 & 7. Data
│   ├── sources/                     # Ingestion and verification
│   ├── schema/
│   │   ├── products/
│   │   ├── ingredients/
│   │   ├── users/
│   │   ├── routines/
│   │   ├── photos/
│   │   └── checkins/
│   └── migrations/
│
├── ml/                          # 6 & 7. Machine Learning
│   ├── ingredient-model/
│   ├── suitability-model/
│   ├── image-analysis/
│   └── ranking/
│
└── evaluation/                  # 9. Evaluation
```

Each directory has a `README.md` describing its scope.

## Product boundaries

- Photos are opt-in, encrypted, and deletable by the user.
- Not a medical diagnosis; users are pointed to a dermatologist for skin conditions.
- No beauty or attractiveness scores.
- Observed patterns are never presented as proof of causation.
