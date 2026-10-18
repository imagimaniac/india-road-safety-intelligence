# Architecture

A small, deterministic pipeline that turns **registry-gated public sources** into
a **single self-contained HTML report**. Nothing in the report is invented: every
figure traces to a stored record with provenance.

## Data flow

```
config/sources.yaml ──► Registry (gate: only `verified` sources collectable)
                                │
                collect/*.py ───┤  fetch (pubic HTTP, polite) + parse → Collection
                                │
                store.py ───────┤  ingest: JSON-schema validate + content-hash dedupe
                                │        into grouped tables (by evidence type)
                                │
                analysis/*.py ──┤  pure functions: rows → charts/tables data
                                │
                report/*.py ────┤  inline-SVG charts + HTML assembly
                                ▼
                    reports/*.html  (one file, offline)
```

## Modules (`src/india_road_safety/`)

| Module | Responsibility |
|---|---|
| `config.py` | Discover project root, load `config/settings.yaml` into `Settings`. |
| `registry.py` | Load + validate `config/sources.yaml`; block non-verified sources. |
| `models.py` | Pydantic models grouped by evidence type; `None` = not reported. |
| `schema.py` | JSON-schema validation (`schemas/*.json`) at ingest boundaries. |
| `normalize.py` | Parsing helpers (ints/floats with Indian digit grouping), content hashing. |
| `http.py` | Polite fetcher: retry/backoff, timeouts, rate limiting, secret redaction. Injectable. |
| `store.py` | SQLite with versioned additive migrations, append-only tables, run log. |
| `pdf.py` | Best-effort PDF text extraction (shared). |
| `collect/base.py` | `Collection` container + `ingest` (validate, dedupe, write). |
| `collect/morth.py` | MoRTH national series, preface narrative, state-wise CSV. |
| `collect/gncap.py` | Global NCAP results page + fact-sheet PDFs (points, not stars). |
| `analysis/accident.py` | National trend, exposure-adjusted rates, road type, road user, risk factors, states. |
| `analysis/vehicles.py` | Crash-test table with protocol-normalised protection, bodyshell, equipment. |
| `report/svg.py` | Dependency-free inline-SVG primitives (line/bar/grouped-bar/hbar/donut). |
| `report/html.py` | Assembles the self-contained HTML report from an analysis context. |
| `pipeline.py` | Wires config + registry + fetcher + store + report together. |
| `cli.py` | `irsi sources|collect|report|all`. |

## Storage model

Tables are grouped by **evidence type** and never merged: `sources`,
`documents`, `provenance`, `accident_records`, `exposures`, `crash_tests`,
`recalls`, vehicle tables, and a `run_log`. Schema changes only via versioned,
additive migrations (`SCHEMA_VERSION`). Fact tables dedupe by a content hash so
re-running collection is idempotent.

## Running

```bash
# read the registry
python -m india_road_safety.cli sources

# collect verified sources (Global NCAP fact sheets capped; omit --limit for all)
PYTHONPATH=src python -m india_road_safety.cli all --limit 40

# or step-by-step
PYTHONPATH=src python -m india_road_safety.cli collect --source morth-road-accidents-in-india
PYTHONPATH=src python -m india_road_safety.cli report
```

With `pip install -e .` the same is available as `irsi …`.

## Testing

```bash
python -m pytest            # all offline; network is never hit
```

Parsers are pure functions tested on fixtures; the full pipeline is exercised
with a `FakeFetcher` (`tests/test_pipeline.py`).
