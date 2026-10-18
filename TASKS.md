# TASKS

Milestone tracker for the India Road Safety Intelligence build. Status legend:
`[x]` done and verified · `[~]` in progress · `[ ]` not started · `[!]` blocked.

## Milestones

- [x] **M0 — Audit & scope.** Read-only audit of `~/Projects`; approved phase-2
      decisions (adapt patterns, single self-contained HTML, national + state
      focus, latest-available cutoff).
- [x] **M1 — Config, registry, schemas.** `config.py`, `registry.py`,
      `schema.py`, `schemas/*.json`; tests.
- [x] **M2 — Collectors & parsers.** `collect/{base,morth,gncap}.py`;
      deterministic, fixture-tested parsers.
- [x] **M3 — Analysis.** `analysis/{accident,vehicles}.py` (trends, exposure,
      road-type, road-user, risk factors, states, crash-test normalisation).
- [x] **M4 — Report.** `report/{svg,html}.py` — self-contained HTML + inline SVG.
- [x] **M5 — Pipeline & CLI.** `pipeline.py`, `cli.py` (`sources|collect|report|all`).
- [x] **M6 — Live end-to-end run.** Real MoRTH PDF + state CSV + Global NCAP
      fact sheets collected; report generated.
- [x] **M7 — Documentation & hardening.** Docs finalised; suite green.
- [~] **M8 — Expansion.** Global NCAP full census done (79/79 tests).
      Remaining: Bharat NCAP (blocked), Euro NCAP, recalls, data.gov.in.

## Verified behaviour

- Accessing collection for a non-verified source raises `SourceNotVerified`
  (see `test_pipeline.py::test_collect_blocks_unverified`).
- Re-ingesting the same collection is idempotent (content-hash dedupe).
- `None` (not `0`) is used for any unavailable value end-to-end.
- The report is a single file with no `<script>`, no external CSS/JS, and no
  loaded network resources (source links are citations only).

## Known issues / follow-ups

- [~] Bharat NCAP site is unreachable from this environment → marked `blocked`.
- [x] MoRTH landing pages are JS-only → use the direct PDF URL instead.
- [x] The PDF contains multiple year-leading tables; Annexure 1 parsing is
      bounded by heading to avoid reading population/vehicle values as counts.
- [x] Global NCAP fact-sheet coverage now collected in full (79/79 listed tests,
      no `--limit` cap); the crash-test table in the report shows all of them.
## Enhancement wave (approved) — completed
- [x] Report polish: TOC/nav, data export (data-URI CSV/JSON), print CSS, dark mode, Okabe-Ito palette.
- [x] Equipment vs protection contrast (honest no-contrast finding, within protocol era).
- [x] Evidence grading (5 dimensions): primary_source, corroboration, recency, completeness, identification_confidence; recorded per source.
- [x] Extended MoRTH tables: T1.5 collision types, T7.3 time-of-day, T3.3 safety devices, T7.2 month-wise (each with Total-row guard).
- [x] Schema v2 + label column on accident_records; migrations + model/schema updates.
- [x] CI workflow (.github/workflows/ci.yaml) + Makefile.
- [x] HTTP retry for transient IncompleteRead; retry logs recorded.
