# NFP Food Insecurity Map

An interactive food insecurity mapping tool for the **Nashville Food Project (NFP)** and **Belmont University's BDAIC**. Displays choropleth maps of Davidson County, Tennessee at census-tract and ZIP code level, overlaying NFP partner locations with Census ACS and CDC PLACES health indicators.

Designed for non-technical NFP staff, city policymakers, and foundation funders — enabling data-informed decisions about where food need is concentrated and where NFP should expand its partner network.

---

## Features

- **Multi-granularity** — toggle between Census Tract and ZIP Code views
- **6 data layers** — Median Income, Poverty Rate, Population, Diabetes, Hypertension, Obesity
- **Pin markers** — partner locations shown as colored pins with Font Awesome icons
- **LayerControl** — toggle data layers and partner markers directly on the map
- **YAML-driven config** — add new layers by editing `project.yml` only
- **Data pipeline** — CLI-based pipeline processes Census, CDC, and partner data into Parquet/GeoJSON
- **Branded UI** — custom CSS theme, branded header, polished sidebar
- **Local dev mode** — run fully offline with generated mock data, no AWS credentials needed
- **Cached rendering** — `st.cache_data` on map HTML keyed by selections for fast interactions

---

## Project Structure

```
nfp-food-insecurity-map/
├── app.py                          # Streamlit entry point
├── project.yml                     # YAML config — single source of truth
├── src/
│   ├── config.py                   # Environment-driven settings + message constants
│   ├── config_loader.py            # YAML config parser with accessor functions
│   ├── data_loader.py              # Parquet + GeoJSON loading, multi-granularity
│   ├── partner_loader.py           # Partner GeoJSON loading
│   ├── geocoder.py                 # Nominatim geocoding (used by pipeline)
│   ├── layer_manager.py            # Folium layer builders (choropleth, pins, boundaries)
│   └── map_builder.py              # Map assembly with LayerControl + cached HTML
├── pipeline/
│   ├── __main__.py                 # CLI entry point (python -m pipeline)
│   ├── load_source.py              # Generic S3/local data loader
│   └── process_partners.py         # Partner geocoding + GeoJSON output
├── data/
│   ├── geo/                        # Geographic boundaries (generated, gitignored)
│   ├── choropleth/                 # Parquet data layers (generated, gitignored)
│   ├── points/                     # Partner GeoJSON (generated, gitignored)
│   └── mock/                       # Mock data for local development
├── scripts/
│   ├── setup.sh                    # One-command setup
│   ├── process_geographic_data.py  # Downloads TIGER/Line shapefiles
│   ├── generate_mock_data.py       # Generates mock CSV data
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
python -m pipeline --step geo            # Download geographic boundaries
python -m pipeline --step census_acs     # Process Census ACS data
python -m pipeline --step health_lila    # Process CDC PLACES data
python -m pipeline --step partners       # Geocode partner locations

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
| Census tracts / ZCTAs | US Census TIGER/Line | Geographic boundaries |
| Median Household Income | ACS 5-Year Estimates | Census economic data |
| Poverty Rate | ACS 5-Year Estimates | Census economic data |
| Total Population | ACS 5-Year Estimates | Census demographic data |
| Diabetes Prevalence | CDC PLACES | Health indicator |
| Hypertension Prevalence | CDC PLACES | Health indicator |
| Obesity Prevalence | CDC PLACES | Health indicator |
| NFP Partners | Nashville Food Project | Partner locations (S3) |

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
