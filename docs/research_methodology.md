# Research methodology & findings

This is the substantive research document. It states the questions, the evidence
discipline, what was actually found, and — importantly — what the data does
**not** support.

## 1. Questions

- **A (context):** What do India's official road-accident statistics show about
  trends, exposure, road types, road-user categories and recorded factors?
- **B (primary):** What can reliable evidence say about the relative crash
  safety of passenger cars sold in India?

## 2. Evidence discipline

Four kinds of statement are kept strictly separate and never blended into one
ranking:

1. **Official statistics** — aggregate counts published by MoRTH.
2. **Crash-test assessments** — model/variant test results (points).
3. **Design/equipment facts** — bodyshell integrity, listed safety equipment.
4. **Derived indicators** — rates computed from published numerators and
   denominators (e.g. deaths per lakh population).

Two hard rules:

- **A recorded factor is not a cause.** "Over speeding" is the factor police
  recorded for an accident, not proof that speed caused that specific crash.
- **Crash-test points are comparable only within one protocol era.** No
  cross-protocol, cross-year or cross-market star comparison is published.

## 3. What the official statistics show (MoRTH, *Road Accidents in India 2022*)

- **Scale:** 4,61,312 road accidents, 1,68,491 deaths and 4,43,366 injuries in
  2022 — up sharply year-on-year (+11.9% accidents, +9.4% deaths vs 2021, which
  was itself a COVID-depressed base).
- **Exposure-adjusted:** deaths per 100,000 population ≈ **12.25** in 2022
  (from 1,68,491 deaths and a population of ~1.3756 billion), up from ≈11.3 in
  2021. The *rate* rose, not just the count.
- **Road type (2022):** National Highways carried 32.9% of accidents
  (1,51,997) but **36.2% of deaths** (61,038); State Highways 23.1% / 24.3%;
  Other Roads 43.9% / 39.4%. Highways are over-represented in fatalities
  relative to their network length.
- **Road users who die:** two-wheeler riders ≈ **44.5%**, pedestrians ≈
  **19.5%**, and car/taxi/van/LMV occupants ≈ **12.5%**. Any passenger-car
  safety story sits inside a two-wheeler-dominated fatality picture.
- **Recorded factors:** over-speeding accounted for ≈72.3% of accidents and
  ≈71.2% of deaths; wrong-side driving ≈4.9% of accidents (recorded, not
  proven cause).

## 4. What the crash-test evidence shows (Global NCAP)

- The current Global NCAP India protocol scores **adult occupant protection out
  of 34.00** and **child occupant protection out of 49.00**; an earlier era used
  **17.00** for adult. We store the raw points and the stated maximum, and
  compute a within-protocol percentage.
- Across the collected tests, results span the full range — from near-maximum
  adult protection (e.g. ~33.7/34) down to **0.00/34** for some base variants
  tested with minimal airbag fitment. Bodyshell integrity ranges from *stable*
  to *unstable*.
- **Why points, not stars:** the adult maximum changed across the period we
  cover, and star bands are defined per protocol. Publishing a star ranking
  across eras would be an apples-to-oranges comparison. Points normalised within
  a stated maximum are auditable; a cross-era star table is not.

## 5. Exposure evidence (partial)

The Annexure-1 table carries registered-vehicle counts (thousands) for
pre-2020 years and population for all years. This supports:
- **deaths per lakh population** (full series), and
- a **partial** vehicle-registration series.

It does **not** provide vehicle-kilometres or per-model exposure, so it cannot
support model-level risk rates. Population vehicles the whole fleet, not cars
alone.

## 6. What this project does NOT claim

- **No "safest car in India" ranking.** That needs per-model exposure and
  real-world model-linked crash outcomes, which are not available here.
- **No cross-protocol star comparison.** See §2 and §4.
- **No causal claims** from recorded factors or from observational correlation.
- **No tag of a specific model as unsafe** from a news mention or a single
  variant's result; results are variant- and equipment-specific.

## 7. Reproducibility

- Deterministic parsing and content-hash dedupe make re-runs idempotent.
- The report is rebuilt from the store with one command; the research cutoff is
  stamped at build time (`study.cutoff_policy = latest_available_at_build`).
- Every figure in the HTML report is generated from stored records that carry a
  source slug and content hash.
