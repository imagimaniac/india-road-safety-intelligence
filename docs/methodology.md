# Methodology

> Status: active. This is the *plan and design*; the substantive results and
> findings live in `docs/research_methodology.md`. Every metric here is
> implemented and covered by tests.

## 1. Research questions

- **A (context):** patterns, trends and contributing factors in Indian road
  accidents — exposure, road type, user category, time, severity.
- **B (primary):** relative safety of passenger cars, manufacturers and models
  sold in India, from reliable evidence.

## 2. Evidence pipeline

```
Source acquisition (registry-gated)
        │  official APIs / bulk downloads / permitted scraping
        ▼
Evidence & data-quality layer
        │  dedupe · provenance · vehicle identification · confidence · missingness
        ├──────────────► 3A Accident intelligence (trends, states, roads, time, severity)
        └──────────────► 3B Vehicle safety (models, generations, crash tests, recalls, real-world)
        ▼
Research report (self-contained HTML, inline SVG, evidence-linked findings)
```

## 3. The four questions that must not be conflated

| Question | Evidence needed | What it can establish |
|---|---|---|
| Which cars perform better in standardized crashes? | Comparable, model-specific crash tests | Performance under defined test conditions |
| Which cars have worse real-world outcomes? | Reliable crash records with model ID + severity | Observed outcomes in the available records |
| Which cars have lower accident/fatality risk? | Comparable exposure denominators + circumstances | More defensible risk estimates, subject to confounding |
| What do these cars weigh / carry / equip? | Specs, equipment, structural data | Design context, not outcome |

## 4. Data quality controls

- Duplicate detection and cautious, auditable record linkage.
- Consistent geographic identifiers; unit/date/category validation.
- Auditable vehicle-name alias table with confidence scores.
- Separate fields for **observed facts**, **extracted claims**, and **analyst
  interpretations**.
- Reconciliation of aggregates against published official totals where
  definitions match; differences documented, not hidden.
- AI/LLMs (if used) only for extraction/classification/entity-resolution, always
  retaining source references and confidence; critical claims verified against
  the original document.

## 5. Statistical methods (where data permits)

Descriptive statistics, trend and YoY analysis, state-level analysis, temporal
heatmaps, cross-tabulations by vehicle class / collision type / severity,
uncertainty and sensitivity analysis, exposure-adjusted comparisons, and
cohort comparisons by generation. Appropriate simple methods over complex models.
No causal claims from observational correlation.

## 6. Reproducibility

- Deterministic core; network injectable; raw/interim/processed separated.
- A single report-build command: `python -m india_road_safety.cli all`
  (collection), then re-render with `… report`.
- Research cutoff date stamped at build time (`study.cutoff_policy`).
