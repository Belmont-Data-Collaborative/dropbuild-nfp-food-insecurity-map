# NFP Food Insecurity Map

An interactive food insecurity mapping tool for the **Nashville Food Project (NFP)** and **Belmont University's BDAIC**. Displays choropleth maps of the **Nashville-Davidson-Murfreesboro-Franklin Metropolitan Statistical Area** (14 Tennessee counties) at census-tract and ZIP code level, overlaying NFP partner locations with Census ACS, CDC PLACES, and USDA Food Access Research Atlas (LILA) indicators.

Designed for non-technical NFP staff, city policymakers, and foundation funders — enabling data-informed decisions about where food need is concentrated and where NFP should expand its partner network.

This is a **multi-page Streamlit app**: a Home landing page, an interactive Map page, and an About the Data page documenting sources, vintage, and methodology.

---

## Features

- **Multi-page app** — Home landing page, interactive Map, and About the Data documentation
- **Nashville MSA coverage** — 14-county OMB definition (~434 census tracts)
- **Multi-granularity** — toggle between Census Tract and ZIP Code views
- **9 data layers** — Median Income, Poverty Rate, Population, Diabetes, Hypertension, Obesity, plus USDA LILA designation, low-access population, and low-income/low-access population
- **County boundary overlay** — dashed lines for the 14 MSA counties, toggleable
- **Categorical layer support** — discrete two-tone rendering for binary LILA flags alongside continuous choropleth gradients
- **Pin markers** — NFP partner locations shown as colored pins with Font Awesome icons
- **Giving Matters integration ready** — pipeline + UI activate automatically once CFMT data is uploaded to S3 (currently disabled, no UI artifact)
- **LayerControl** — toggle data layers, partner markers, and county boundaries directly on the map
- **YAML-driven config** — add new layers by editing `project.yml` only
- **Data pipeline** — CLI-based pipeline processes Census, CDC, USDA LILA, and partner data into Parquet/GeoJSON; LILA includes a 2010→2020 tract crosswalk
- **Branded UI** — custom CSS theme, branded Home hero, polished sidebar
- **Local dev mode** — run fully offline with generated mock data, no AWS credentials needed
- **Cached rendering** — `st.cache_data` on map HTML keyed by selections for fast interactions

---

## Project Structure

```
nfp-food-insecurity-map/
├── app.py                          # Streamlit entry point — Home page
├── pages/
│   ├── 1_Map.py                    # Interactive map page
│   └── 2_About_the_Data.py         # Data sources, methodology, limitations
├── project.yml                     # YAML config — single source of truth
├── src/
│   ├── config.py                   # Environment-driven settings + message constants
│   ├── config_loader.py            # YAML config parser with accessor functions
│   ├── data_loader.py              # Parquet + GeoJSON loading, multi-granularity
│   ├── partner_loader.py           # Partner GeoJSON loading
│   ├── geocoder.py                 # Nominatim geocoding (used by pipeline)
│   ├── layer_manager.py            # Folium layer builders (choropleth, pins, county boundaries, Giving Matters)
│   └── map_builder.py              # Map assembly with LayerControl + cached HTML
├── pipeline/
│   ├── __main__.py                 # CLI entry point (python -m pipeline)
│   ├── load_source.py              # Generic S3/local data loader (MSA county-set filter)
│   ├── process_partners.py         # Partner geocoding + GeoJSON output
│   ├── process_usda_lila.py        # USDA LILA + 2010→2020 tract crosswalk
│   └── process_giving_matters.py   # Giving Matters loader (graceful skip when unavailable)
├── data/
│   ├── geo/                        # tracts, zipcodes, county_boundaries, msa_boundary (gitignored)
│   ├── choropleth/                 # Parquet data layers (generated, gitignored)
│   ├── points/                     # Partner + Giving Matters GeoJSON (generated, gitignored)
│   └── mock/                       # Mock data for local development
├── scripts/
│   ├── setup.sh                    # One-command setup
│   ├── process_geographic_data.py  # Downloads TIGER/Line shapefiles for the 14-county MSA
│   ├── download_lila_data.py       # Downloads USDA LILA xlsx and uploads CSV to S3
│   ├── download_tract_crosswalk.py # Downloads Census 2010↔2020 tract relationship file
│   ├── generate_mock_data.py       # Generates mock CSV data (incl. mock LILA + Giving Matters)
│   └── generate_mock_parquet.py    # Converts mock CSVs to Parquet
├── tests/
│   ├── unit/                       # Unit tests for each module
│   ├── integration/                # End-to-end pipeline tests
│   └── fixtures/                   # Sample data for tests
├── ASSUMPTIONS.md                  # Architectural decisions
├── requirements.txt                # Pinned Python dependencies
└── .env.example                    # Environment variable template
```

---

## Quick Start

### Prerequisites

- Python 3.11+

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set USE_MOCK_DATA=true for local dev

# Generate mock data
python scripts/generate_mock_data.py
python scripts/generate_mock_parquet.py

# Run the app
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

---

## Data Pipeline

The pipeline processes raw data from S3 into optimized Parquet and GeoJSON files.

```bash
# Run full pipeline
python -m pipeline

# Run individual steps
python -m pipeline --step geo             # Download geographic boundaries (MSA-wide)
python -m pipeline --step census_acs      # Process Census ACS data
python -m pipeline --step health_lila     # Process CDC PLACES data
python -m pipeline --step usda_lila       # Process USDA LILA + 2010→2020 tract crosswalk
python -m pipeline --step giving_matters  # Process Giving Matters (graceful skip when disabled)
python -m pipeline --step partners        # Geocode partner locations

# One-time uploads to S3 (run when source data refreshes)
python scripts/download_lila_data.py        # USDA Food Access Research Atlas
python scripts/download_tract_crosswalk.py  # Census 2010↔2020 tract relationship file

# Inspect processed data
python -m pipeline --inspect census_acs
```

In mock mode (`USE_MOCK_DATA=true`), the partner pipeline uses local CSV files.

---

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | No | `development` (default) or `production` |
| `USE_MOCK_DATA` | No | `true` for local dev, `false` for production |
| `MOCK_DATA_DIR` | No | Path to mock data (default: `data/mock/`) |
| `AWS_ACCESS_KEY_ID` | Production | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | Production | AWS credentials for S3 |
| `AWS_DEFAULT_REGION` | No | AWS region (default: `us-east-1`) |
| `AWS_BUCKET_NAME` | Production | S3 bucket name |
| `PROJECT_CONFIG` | No | Path to config file (default: `project.yml`) |

### Adding New Data Layers

Edit `project.yml` — no Python changes needed:

```yaml
data_sources:
  census_acs:
    variables:
      - column: NEW_COLUMN_NAME
        display_name: "New Layer Name"
        colormap: YlGnBu
        format_str: "{:.1f}%"
        default_visible: false
```

---

## Data Sources

| Layer | Source | Description |
|---|---|---|
| Census tracts / ZCTAs / county boundaries / MSA outline | US Census TIGER/Line | Geographic boundaries (14-county Nashville MSA) |
| Median Household Income | ACS 2020–2024 5-Year Estimates | Census economic data |
| Poverty Rate | ACS 2020–2024 5-Year Estimates | Census economic data |
| Total Population | ACS 2020–2024 5-Year Estimates | Census demographic data |
| Diabetes Prevalence | CDC PLACES 2024 | Health indicator (model-based) |
| Hypertension Prevalence | CDC PLACES 2024 | Health indicator (model-based) |
| Obesity Prevalence | CDC PLACES 2024 | Health indicator (model-based) |
| LILA Designation (1 & 10 mi) | USDA Food Access Research Atlas (2019, 2010 boundaries → converted to 2020 via Census relationship file) | Binary low-income/low-access flag, tract only |
| Low Access Population (1 mi) | USDA Food Access Research Atlas | Area-weighted apportionment to 2020 tracts |
| Low Income, Low Access Population (1 mi) | USDA Food Access Research Atlas | Area-weighted apportionment to 2020 tracts |
| NFP Partners | Nashville Food Project | Partner locations (S3) |
| Giving Matters (when available) | Community Foundation of Middle Tennessee | Nonprofit point data — currently pending CFMT data receipt |

---

## Enabling Giving Matters (when CFMT data arrives)

The pipeline and UI for the Community Foundation of Middle Tennessee's *Giving Matters* dataset are wired and ready. To activate it:

1. Upload the CFMT CSV to `s3://bdaic-public-transform/nfp-mapping/partners/giving_matters.csv`.
2. In `project.yml`, under `data_sources.giving_matters`, set `enabled: true` and fill in `required_columns` with the actual schema (`name_column`, `address_column`, `category_column`).
3. Run `python -m pipeline --step giving_matters` — this writes `data/points/giving_matters.geojson`.
4. Reload the Streamlit app. A new "Community Partners" section automatically appears in the sidebar with a `Show Giving Matters Partners` checkbox; selecting it renders cyan circle markers (distinct from NFP partner pins) on the Map page.

No code changes are required.

---

## Testing

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

---

## Deployment

### Streamlit Community Cloud

1. Push to GitHub
2. Connect at [share.streamlit.io](https://share.streamlit.io)
3. Set `app.py` as entry point
4. Add AWS credentials as secrets
5. Set `APP_ENV=production` and `USE_MOCK_DATA=false`

### Docker

```bash
docker build -t nfp-map .
docker run -p 8501:8501 --env-file .env nfp-map
```

### Security Headers (Production)

Streamlit doesn't expose HTTP response headers. In production, use a reverse proxy
(nginx, Cloudflare) to set security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Content-Security-Policy`
- `Strict-Transport-Security`
