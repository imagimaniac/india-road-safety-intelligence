# India Road Safety Intelligence

Evidence-driven research on road accidents in India, with the primary analytical
objective of understanding the relative safety of passenger cars, manufacturers,
and specific models sold in India — connecting **independently assessed
crashworthiness** to **real-world outcomes** where credible evidence exists.

> **Status: working end-to-end (v1).** The pipeline collects verified public
> sources (MoRTH national + state statistics, Global NCAP crash tests) and builds
> a single self-contained HTML report. See `TASKS.md` for milestone status and
> `reports/india-road-safety-report.html` for the output.

## Research questions

- **A (context):** What are the patterns, trends and contributing factors in road
  accidents in India? (exposure, roads, users, time, severity)
- **B (primary):** What can reliable evidence tell us about the relative safety of
  passenger cars, manufacturers and specific models sold in India?

## What this project will — and will not — claim

The report will keep four distinct concepts separate:

1. Laboratory crash-test performance (comparable tests only).
2. Safety equipment and structural design.
3. Observed real-world crash outcomes (where model-level records exist).
4. Estimated risk per unit of exposure.

If credible model-level **exposure** data is unavailable (likely in India), this
project will **not** publish a definitive "safest cars" ranking. It will present
the tested crashworthiness, equipment, recalls and documented investigations that
do exist, with an explicit evidence grade and the missing denominators named.

## Principles

- **Provenance first.** Every number traces to a registered source.
- **No fabrication.** Unavailable = `None`, never `0`.
- **No premature causation.** Recorded violations are recorded factors, not proof
  of cause in any individual crash.
- **Separate evidence types.** Accident counts, news claims and crash-test scores
  are different observations and are never merged into one table.
- **Polite and lawful collection.** Official APIs and bulk downloads first; respect
  robots, terms, rate limits; no CAPTCHA/auth bypass, no stealth scraping.

## Layout

```
config/      settings.yaml, sources.yaml (registry), vehicles/ (alias tables)
src/india_road_safety/
  http.py       polite HTTP (retry/backoff/timeout/redaction; injectable)
  normalize.py  deterministic normalizers + content hashing
  store.py      SQLite, versioned migrations, append-only, provenance
  models.py     pydantic domain models (None = not reported)
  registry.py   loads + validates config/sources.yaml
  schema.py     JSON-schema validation (schemas/*.json)
  pdf.py        PDF text extraction
  collect/      source collectors (morth, gncap) + ingest
  analysis/     trends, exposure rates, road type/user, crash-test normalisation
  report/       svg.py + html.py -> self-contained HTML (inline SVG)
  pipeline.py   wires config + registry + fetcher + store + report
  cli.py        `irsi sources|collect|report|all`
data/raw      original snapshots (gitignored)
data/interim  SQLite DB + partial parses (gitignored)
data/processed  normalized, analysis-ready
schemas/      JSON schemas per evidence type
docs/         methodology, research_methodology, data_sources, sources,
              assumptions-log, limitations, architecture
tests/        unit + integration (mocked) tests
```

## Usage

```bash
cd ~/Projects/india-road-safety-intelligence
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .            # optional: enables the `irsi` command

# see the source register and verification status
python -m india_road_safety.cli sources

# collect verified sources and write the report (Network required)
PYTHONPATH=src python -m india_road_safety.cli all --limit 40

# tests (offline; network is never hit)
python -m pytest
```

## Roadmap (see TASKS.md)

1. Scaffold + config.
2. Reusable core (`http`, `normalize`, `store`, `models`).
3. Source registry loader + JSON schemas.
4. Collectors + analysis + self-contained HTML report (vertical slice).
5. Live end-to-end run (MoRTH + Global NCAP) → `reports/`.
6. Full docs; optional expansion (Bharat NCAP, Euro NCAP, recalls) as sources
   become available.
