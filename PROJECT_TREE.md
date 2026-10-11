# Rest — Project Tree

```
Rest
│
├── 1. Project Purpose
│   ├── Help users make informed skincare product choices
│   ├── Show skin changes over time with before-and-after comparisons
│   ├── Build confidence through understanding, not judging appearance
│   └── Use sleep, mental, and social well-being as context for decisions
│
├── 2. Product & Ingredient Data
│   ├── Product catalog (type, brand, price, full ingredient list)
│   ├── Ingredient knowledge base
│   │   ├── What each ingredient does
│   │   ├── Known irritants and allergens
│   │   └── Pore-clogging risk and conflicting combinations
│   └── Data sources and verification
│
├── 3. User Skin Profile & Routine
│   ├── Skin type, concerns, goals
│   ├── Sensitivities and allergies
│   ├── Preferences and budget
│   ├── Current routine (products, start/stop dates)
│   └── Reaction log
│
├── 4. Before-and-After Visualization
│   ├── Guided photo capture (lighting, angle, distance checks)
│   ├── Photo alignment and color correction
│   ├── Side-by-side and slider comparisons
│   ├── Timeline linked to routine changes
│   ├── Optional measurements (redness, texture, blemish count)
│   └── Optional AI scenario illustration, labeled as non-predictive
│
├── 5. Well-Being Context (friend's research)
│   ├── Sleep: duration, quality
│   ├── Mental: stress, mood
│   ├── Social: connection, confidence in social situations
│   └── Records context alongside routine changes
│       (observational data alone cannot isolate lifestyle or product effects)
│
├── 6. Decision Support & Model
│   ├── Rules-based ingredient matching first
│   ├── Log impressions, actual usage, and structured outcome feedback
│   ├── ML later: rank eligible products from profile, product, and routine features
│   ├── Train against reported outcomes; optional well-being context stays separate initially
│   ├── Explain each recommendation (which ingredients, why)
│   ├── Show uncertainty and limitations
│   └── User feedback improves the model
│
├── 7. Technical Architecture
│   ├── Frontend: product search, routine tracker, photo compare, check-ins, dashboard
│   ├── Backend: auth, product/ingredient API, routine and photo API, check-in API, recommendation service
│   ├── Data: product database, user profiles, encrypted photos, check-in history
│   └── ML: ingredient model, image analysis, recommendation ranking
│
├── 8. Privacy & Boundaries
│   ├── Photos are opt-in, encrypted, deletable by the user
│   ├── Not a medical diagnosis; suggest seeing a dermatologist for skin conditions
│   ├── No beauty or attractiveness scores
│   └── No claims that patterns prove causation
│
└── 9. Evaluation
    ├── Recommendation quality vs. user-reported outcomes
    ├── Photo comparison consistency
    ├── User understanding and confidence
    └── Continued use
```
