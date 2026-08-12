# J-REIT Underwriting Benchmark

[日本語 README](README.md)

An application that collects and normalizes property-level data from J-REIT securities reports (有価証券報告書) and other disclosures, and lets you search Comparable Properties and compare/aggregate underwriting metrics such as occupancy (OCC), rent per tsubo, and Cap Rate.

Currently in Phase 1 (PoC) foundation-building. 12 target issuers are configured (see [Target REITs](#target-reits)), but the actual extraction pipeline will first be built end-to-end for a single issuer — Nippon Building Fund Inc. (8951) — before being rolled out to the rest.

## Setup

### 1. Virtual environment

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your API key.

```bash
cp .env.example .env
```

`.env` contents:

```
EDINET_API_KEY=your_api_key_here
DATABASE_PATH=data/jreit.db
```

- Get an EDINET API key at https://api.edinet-fsa.go.jp/
- `.env` is excluded from Git (see `.gitignore`). **Never hardcode the actual key value in code or documentation.**

(Adding an external lookup API such as Gemini, for nearest-station distance and building grade, is under consideration. A `GEMINI_API_KEY` entry will be added here if/when it's introduced.)

## Initialize the database

```bash
python -m src.database.database
```

Creates the SQLite schema (jreit_master, properties, property_metrics, source_records) at `data/jreit.db`.

## Load target REITs

Target issuers are managed in `config/poc_targets.yaml`. After editing it, apply changes to the DB with:

```bash
python -m src.database.seed
```

(Existing `reit_code` rows are skipped, so this is safe to re-run.)

### Target REITs

| Securities code | Name | EDINET code |
|---|---|---|
| 8951 | Nippon Building Fund Inc. | E13206 |
| 8952 | Japan Real Estate Investment Corporation | E13205 |
| 8958 | Global One Real Estate Investment Corp. | E13678 |
| 8975 | Ichigo Office REIT Investment Corporation | E14150 |
| 8976 | Daiwa Office Investment Corporation | E14197 |
| 3290 | One REIT, Inc. | E27884 |
| 8972 | KDX Realty Investment Corporation | E14109 |
| 8955 | Japan Prime Realty Investment Corporation | E13448 |
| 8966 | Heiwa Real Estate REIT, Inc. | E14005 |
| 8977 | Hankyu Hanshin REIT, Inc. | E14207 |
| 3462 | Nomura Real Estate Master Fund, Inc. | E31931 |
| 3451 | Tosei Reit Investment Corporation | E30997 |

EDINET codes were verified by cross-checking fudosandb.jp's per-issuer pages (matching the URL against the REIT name shown on that page). They have not yet been independently re-verified against EDINET's own official code list.

## Searching for and downloading EDINET documents

```bash
python -m src.edinet.api
```

Prints the number of documents submitted to EDINET on a given date (connectivity check).

```bash
python -m src.edinet.documents E13206 --start 2026-02-01 --end 2026-04-30
```

Searches for securities reports (有価証券報告書) filed by the given EDINET code within a date range and downloads the most recent match to `data/raw/documents/`. EDINET has no API to search by company name/code directly, so this works by fetching each date's document list and filtering. Already-downloaded `docID`s are not re-fetched.

Files are saved as `{docID}_type{N}.{zip|pdf}` (type=1: XBRL package zip, type=2: PDF).

## Running tests

```bash
pytest
```

## Data model overview

- `jreit_master` — J-REIT master list (issuer, sponsor, EDINET code, etc.)
- `properties` — property attributes (asset type, address, nearest station, walking distance, year built, etc.)
- `property_metrics` — period-level operating/financial metrics (OCC, rent per tsubo, NOI, cap rate variants)
- `source_records` — field-level audit trail tracking source, extraction method, confidence, and validation status

Cap rate variants (`acquisition_cap_rate` / `appraisal_cap_rate` / `noi_yield`) are kept in separate columns and never conflated. OCC is range-checked to 0-100%; when a source document's own definition differs from the standard one used here, it's preserved in `occupancy_rate_definition`.

### Annualizing semi-annual vs. annual reporting

J-REITs report on different cycles — some every 6 months (semi-annual), a few once a year. Before comparing properties across issuers, `annualize_metrics()` in `src/extraction/normalizer.py` aligns each property's metrics to a trailing 12 months.

- If the most recent record already covers a full year (`period_type="annual"`), it's used as-is.
- If the two most recent records are consecutive 6-month periods, they're combined:
  - **NOI** (money earned/spent over the period) → **summed** across the two halves.
  - **occupancy_rate / rent_per_tsubo / cap rate variants** (a ratio or point-in-time unit price) → **averaged**.
- If a value is missing on either half, the combined value is `None` rather than guessed (recorded in `missing_fields`).
- If two consecutive periods aren't available, no annualized figure is produced — never guessed.

The `period_type` / `period_end_date` columns on `property_metrics` drive this logic.

## Data source findings (important)

Parsing Nippon Building Fund's actual disclosures surfaced where each field really comes from. The (not-yet-implemented) extraction code in `src/extraction/property_parser.py` is designed around these findings.

| Field | Source | Notes |
|---|---|---|
| Address, land area, zoning, building structure, total floor area, construction date | Securities report (EDINET) | Found in a per-property key-value table |
| Acquisition price, book value, appraisal value, appraiser, investment ratio | Securities report (EDINET) | Found in a portfolio summary table (uses rowspan for region grouping) |
| Occupancy rate, leasable area, leased area, period rental revenue, tenant count | Securities report (EDINET) | Found in a separate portfolio performance table; must be joined to the above by property name |
| **Property-level NOI** | Each REIT's own IR site (e.g. NBF's "Data by Property" Excel file, sheet `個別物件の収益状況`) | Not on EDINET. File format/location is very likely issuer-specific |
| **Cap rate** (appraisal NOI yield, etc.) | Not directly disclosed anywhere found so far. Computed as (annualized NOI) ÷ (acquisition price or appraisal value) | Plan: tag as `extraction_method="computed"` and record the source NOI/price values in `source_records` |
| Nearest station, walking minutes, building grade | Not found in either the securities report or the asset management report | Considering an external lookup (e.g. a search-grounded LLM API such as Gemini) as a supplementary source. Even if obtained, `confidence` should be set low and clearly distinguished from officially disclosed data |

The iXBRL/PDF securities report text is broken up by inline tags, so naive keyword search misses real matches (this actually happened — "nearest station" initially looked absent when it was really just a false negative from raw-text search). Extraction code must parse the HTML structure (e.g. with BeautifulSoup) and work at the `<table>` level, not via plain-text keyword search.

## Directory structure

```
├── app/                  # Streamlit UI (Phase 4)
├── config/
│   └── poc_targets.yaml  # Target REIT list (12 issuers)
├── data/
│   ├── raw/
│   │   └── documents/    # Raw files fetched from EDINET/IR sites (not in Git)
│   ├── processed/        # Processed data
│   └── jreit.db          # SQLite DB (not in Git)
├── notebooks/            # Exploratory analysis / extraction prototyping
├── src/
│   ├── config.py         # Config file loader
│   ├── edinet/
│   │   ├── api.py        # documents.json (submission list) client
│   │   └── documents.py  # Search/download documents by issuer + date range
│   ├── extraction/
│   │   └── normalizer.py # Semi-annual -> annual conversion (property_parser.py not yet implemented)
│   ├── database/         # ORM models, DB connection, seeding
│   └── analytics/        # Comparable search & statistics (Phase 5)
└── tests/                # pytest
```

## Development phases

1. **PoC** (in progress): 12 target issuers configured. Build "EDINET fetch → property DB → search → average/median" end-to-end for Nippon Building Fund first, then roll out to the rest.
2. **Pipeline**: Automate EDINET fetching, extraction, normalization, and validation (including fetching NOI data from each REIT's IR site).
3. **Scale**: Expand to all J-REITs.
4. **Application**: Streamlit UI, export, charts.
5. **Advanced**: Comparable benchmarking, cap rate sensitivity, attribute enrichment via external APIs (e.g. Gemini).

## Disclaimer

This application does not make investment decisions automatically — it's a tool to support Comparable / Underwriting analysis using public information. Because Cap Rate, rent, OCC, and similar figures can be defined differently across source documents, the database preserves each value's definition, source, and period alongside the number itself. In particular, note that Cap Rate is in most cases a computed value rather than a figure directly disclosed by the issuer.
