# Sources

> Status: active. The machine-readable registry lives in `config/sources.yaml`;
> this file documents the human-readable register and attributions.
> **See `docs/data_sources.md` for the verified sources actually used.**

## Verification protocol

For each source, confirm and record:

- Organization and canonical URL / API endpoint.
- Access method (official_api | bulk_download | pdf_report | structured_html |
  permitted_scraping | manual_only).
- Data type and relevant fields.
- Geographic and temporal coverage.
- Update frequency (if known).
- Publication date and retrieval timestamp.
- Licence, terms, access restrictions, attribution requirements.
- Reliability assessment and known gaps/biases/limitations.

A source is usable only when `status: verified` in `config/sources.yaml`.

## Register (current status)

| id | Organization | Type | Status |
|---|---|---|---|
| morth-road-accidents-in-india | MoRTH, Government of India | accident_stats | **verified** |
| morth-state-wise-accidents | MoRTH via data.opencity.in | accident_stats | **verified** |
| global-ncap | Global NCAP | crash_test | **verified** |
| data-gov-in | Open Government Data Platform India | accident_stats | pending_verification |
| bharat-ncap | CIRT / Bharat NCAP | crash_test | **blocked** |
| euro-ncap | Euro NCAP | crash_test | pending_verification |
| peer-reviewed-research | Various | research | pending_verification |
| news-investigative | Various credible outlets | news | pending_verification |

## Code attribution

Reusable patterns are adapted from the author's other local projects (kept
self-contained here; no databases, secrets or datasets imported):

- HTTP politeness / retry-backoff / redaction, normalizers, dedupe-by-content-hash,
  SQLite versioned migrations, and sample-only report framing:
  `~/Projects/unified-job-portal-automation`.
- Source registry with permitted-use/licence, `None`-not-zero rule, evidence
  scoring, and report/LLM schema validation: `~/Projects/investment-research`.
- Assumed/Cited/Derived traceability and self-contained HTML report style:
  `~/Projects/pune-mobility-location-intelligence`.
- Source registry + schema + raw/processed separation:
  `~/Projects/india-strategy-data`.
