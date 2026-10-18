# Limitations

> Status: active. Honest limitations are a deliverable, not an afterthought.

## Known structural limitations (confirmed or updated after collection)

1. **No model-level crash records.** India does not publish a dataset linking
   individual crashes to verified car models, occupants and injuries. Model-level
   risk rankings are therefore **not** defensible and are not published.
2. **No per-model exposure denominators.** Population and (partial) fleet
   registrations exist, but not vehicle-kilometres or per-model exposure. Raw
   counts are never presented as if they were risk.
3. **Cross-protocol non-comparability.** Bharat NCAP, Global NCAP and Euro NCAP
   differ in protocol, vehicles and equipment. Star ratings are not compared
   across programs. Within Global NCAP, the adult maximum changed (17 → 34
   points); we normalise only within a stated maximum and never publish a
   cross-era star ranking.
4. **Market/spec divergence.** Identically named models sold in different markets
   can differ in structure, restraints and safety equipment. Ratings transfer
   only when the spec matches.
5. **Recorded factor ≠ cause.** Police-recorded violations/conditions are
   recorded factors, not established causes in any individual crash.
6. **Under-reporting and definitional drift.** Accident statistics are subject to
   under-reporting and changing definitions across years and states.
7. **Selection bias in news.** News-based identification over-represents
   newsworthy crashes and is not reliable model-ID evidence on its own.
8. **Variant-specific crash tests.** A result applies to the tested variant and
   equipment; it does not generalise to all trims of a nameplate.

## Data gaps log

| Gap | Impact | Mitigation / current handling |
|---|---|---|
| Bharat NCAP portal unreachable from this environment | No Indian-protocol results in v1 | Source marked `blocked`; only collected once reachable |
| data.gov.in served as Nuxt SSR (not parseable via simple fetch) | Could not use as-is | State totals sourced from the opencity.in public-domain mirror |
| Annexure-1 registered-vehicles column truncated for 2020–2022 | No fleet exposure for recent years | Vehicles exposure stored only for years that carry the column; recent years use population |
| Global NCAP fact-sheet census capped by `--limit` | Partial model coverage | Raise/remove `--limit` to collect all listed tests |
| No per-model real-world outcomes | Model-level risk cannot be computed | Report states this explicitly; no ranking published |
