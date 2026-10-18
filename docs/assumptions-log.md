# Assumptions & Parameters Log

> Traceability framework adapted from
> `~/Projects/pune-mobility-location-intelligence/docs/assumptions-log.md`.
>
> Every parameter used in analysis or in the report must appear here with a
> **Status** of `A` (Assumed), `C` (Cited) or `D` (Derived), a rationale, a
> source/reference, a range where relevant, and a validation plan.

> Status: active. Parameters below are those actually used in analysis/report.

| Parameter | Value | Status (A/C/D) | Rationale | Source/Ref | Retrieved | Range (min/def/max) | Sensitivity | Validation plan |
|---|---|---|---|---|---|---|---|---|
| Population unit | thousands | C | MoRTH Annexure 1 states population in thousands | MoRTH *Road Accidents in India 2022* | 2026-10-17 | — | — | Cross-check against a known year (2021 ≈ 11.3 per lakh) |
| Deaths per lakh population | `fatalities / population_thousand × 100` | D | Standard exposed-rate normalisation | derived | — | — | Low | Reproduce 2021≈11.3 and 2022≈12.25 |
| Crash-test protocol maxima | adult 17 or 34; child 49 | C | The maximum printed on each Global NCAP fact sheet | Global NCAP fact sheets | 2026-10-17 | per fact sheet | High (defines normalisation) | Assert the printed `max.` value equals the stored maximum |
| Normalised protection | `points / stated_max × 100` | D | Within-protocol comparability only | derived | — | 0–100% | High | Never compare across differing maxima |
| Research cutoff | latest available at build | C | Report stamped at build time | `study.cutoff_policy` | — | — | — | Timestamp shown in report header |

## Rules

- An **Assumed** parameter is a hypothesis, always shown with a range in the
  report; never hard-code a point estimate as fact.
- A **Cited** parameter must carry a URL and a retrieval date.
- A **Derived** parameter must describe the computation and its inputs.
- If a value is unknown, it stays `None` (not reported) — never `0`.
