# Rest

An app that helps users reflect on their overall well-being by bringing **sleep**, **mental well-being**, and **social well-being** together, and turning self-reported check-ins into understandable, personalized insights.

See [`PROJECT_TREE.md`](PROJECT_TREE.md) for the full concept tree.

## Repository layout

```
rest/
├── PROJECT_TREE.md              # Concept tree (sections 1–8)
│
├── frontend/                    # 6. Frontend
│   └── src/
│       ├── screens/
│       │   ├── onboarding/          # 3. Goals, sharing choices, check-in preferences
│       │   ├── check-in/            # 3. Daily Check-In
│       │   │   ├── sleep/
│       │   │   ├── mood-stress/
│       │   │   └── social/
│       │   ├── dashboard/           # 3. Overview, combined timeline, goal progress
│       │   ├── weekly-reflection/   # 3. Summaries users confirm or correct
│       │   ├── insights/            # 4. Suggestions + explanations + feedback
│       │   ├── skin/                # 5. Optional skin and product features
│       │   └── settings/privacy/    # 7. Privacy controls, data deletion
│       ├── components/
│       └── services/
│
├── backend/                     # 6. Backend
│   └── src/
│       ├── auth/                    # Authentication
│       ├── api/                     # Check-in, profile, reflection APIs
│       │   ├── profile/
│       │   ├── checkins/
│       │   └── reflections/
│       ├── pillars/                 # 2. Three Core Pillars
│       │   ├── sleep/
│       │   ├── mental/
│       │   └── social/
│       ├── insights/                # 4. Insight generation
│       │   ├── rules/
│       │   ├── cross-pillar/
│       │   ├── suggestions/
│       │   └── feedback/
│       ├── skin/                    # 5. Optional
│       │   ├── photos/
│       │   ├── ingredients/
│       │   └── products/
│       └── privacy/                 # 7. Consent, data use, deletion
│
├── data/                        # 6. Data Storage
│   ├── schema/
│   │   ├── users/                   # Preferences and goals
│   │   ├── checkins/                # Check-in history
│   │   └── skin/                    # Optional photo and product records
│   └── migrations/
│
├── ml/                          # 6. Optional Machine Learning
│   ├── longitudinal/
│   ├── skin-image/
│   └── recommendation-ranking/
│
└── evaluation/                  # 8. Evaluation
```

Each directory has a `README.md` describing its scope.

## Product boundaries

- Sensitive inputs are optional.
- Users control deletion of their data.
- Data use is explained clearly.
- No mental-health diagnosis from photos.
- Observed patterns are never presented as proof of causation.
