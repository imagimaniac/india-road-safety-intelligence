# Data sources (verified register)

The machine-readable registry is `config/sources.yaml`. A source is collectable
**only** when its `status` is `verified`. This file documents what was actually
used, what it contains, and how it is attributed.

## Verified & used

### 1. `morth-road-accidents-in-india` — MoRTH national series + narrative
- **Organization:** Ministry of Road Transport and Highways (Transport Research
  Wing), Government of India.
- **Artefact:** *Road Accidents in India 2022* (PDF, 236 pages, ~39 MB).
- **URL:** `https://morth.gov.in/backend/documents/uploaded/1755600426_RA_2022_30_Oct.pdf`
- **Access method:** `pdf_report` (direct download; the site landing pages are
  JavaScript-only, so the direct PDF URL is used).
- **What we extract:**
  - **Annexure 1** (`Road Accidents, Persons Killed and Injured: 1970–2022`):
    year, accidents, killed, injured, population (thousands), registered
    vehicles (thousands, older years), plus published rates.
  - **Preface/executive-summary narrative:** road-type split (NH/SH/Other) for
    accidents and fatalities, recorded factors (over-speeding, wrong-side), and
    road-user death shares (two-wheelers, pedestrians, car occupants).
- **Coverage:** national, 1970–2022 (published years: 1970, 1980, 1990, then
  every year 1994–2022). Population present throughout; vehicles exposure only
  for pre-2020 rows.
- **Known parsing hazards (handled):** the PDF contains decadal-chart and
  population tables whose rows also begin with a year. Annexure-1 parsing is
  bounded by its heading so a population value is never recorded as an accident
  count. The fatality-narrative regex requires the number to sit immediately
  before "were on … Highways" so the earlier accident figure is not captured.

### 2. `morth-state-wise-accidents` — state/UT accident totals
- **Organization:** MoRTH data republished on the data.opencity.in public-domain
  mirror.
- **URL:** `https://data.opencity.in/dataset/…/road-accidents-2024-states-road-accidents.csv`
- **Access method:** `bulk_download` (CSV, ~3 KB).
- **What we extract:** total accidents per state/UT, 2020–2024.
- **Note:** the single `All India` aggregate row is excluded so it is never
  mistaken for a state.

### 3. `global-ncap` — Global NCAP India crash-test results
- **Organization:** Global New Car Assessment Programme (Global NCAP).
- **Artefacts:** results page `https://www.globalncap.org/results` plus one
  fact-sheet PDF per tested model under `https://www.globalncap.org/s/*.pdf`.
- **Access method:** `structured_html` + PDF.
- **What we extract:** per tested model/variant — adult & child **occupant
  protection points**, the protocol maximum they are out of, bodyshell integrity
  (as stated), and explicitly listed safety equipment.
- **Deliberate design choice:** **star ratings are NOT parsed or published.**
  Only the objective protection points are used, and they are normalised only
  within the same stated protocol maximum. See `docs/research_methodology.md`.
- **Coverage:** as listed on the results page at build time.

## Registered but not used (yet)

| Slug | Status | Reason |
|---|---|---|
| `bharat-ncap` | `blocked` | `bharatncap.org` unreachable/times out from this environment. |
| `data-gov-in` | `pending_verification` | data.gov.in is Nuxt SSR; the state CSV is sourced via the opencity mirror instead. |
| `euro-ncap` | `pending_verification` | Not needed for the India-focused v1. |
| `peer-reviewed-research` | `pending_verification` | Candidate; not collected in v1. |
| `news-investigative` | `pending_verification` | Candidate; not collected in v1. |

## Licensing & attribution

- MoRTH publications are Government of India works; quoted with attribution and
  used for factual reporting.
- The opencity.in state dataset is published as **Public Domain**.
- Global NCAP results/fact sheets are quoted with attribution; only objective
  points are reproduced, not star ratings.
- Raw downloaded artefacts are kept under `data/raw/` which is **gitignored**;
  the repository ships code and derived aggregates, not bulk copyrighted data.
