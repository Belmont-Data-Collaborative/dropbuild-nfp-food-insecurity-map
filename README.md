# NFP Food Insecurity Map

An interactive food insecurity mapping tool for the **Nashville Food Project (NFP)** and **Belmont University's BDAIC**. Displays a choropleth map of Davidson County, Tennessee at census-tract level, overlaying NFP partner locations with Census ACS poverty/income data and CDC PLACES health indicators.

Designed for non-technical NFP staff, city policymakers, and foundation funders — enabling data-informed decisions about where food need is concentrated and where NFP should expand its partner network.

---

## Features

- **Census-tract choropleth** — switch between poverty rate, median household income, and CDC PLACES diabetes prevalence
- **NFP partner markers** — geocoded partner locations color-coded by partner type (8 categories)
- **Clickable popups** — tract-level data values and partner organization details on click
- **Sidebar controls** — toggle partner layer, switch data layers, download map, view data freshness
- **Local dev mode** — run fully offline with generated mock data, no AWS credentials needed
- **Geocode cache** — Nominatim results cached to CSV to avoid redundant API calls

---

## Project Structure

```
nfp-food-insecurity-map/
├── app.py                          # Streamlit entry point
├── src/
│   ├── config.py                   # All constants (colors, S3 paths, layer definitions)
│   ├── data_loader.py              # S3 / local CSV loading + GEOID normalization
│   ├── geocoder.py                 # Nominatim geocoding with cache
│   ├── layer_manager.py            # Folium layer construction
│   └── map_builder.py              # Map assembly
├── data/
│   ├── shapefiles/                 # Davidson County census tract GeoJSON (generated)
│   └── mock/                       # Mock CSVs for local development (generated)
├── scripts/
│   ├── setup.sh                    # One-command setup script
│   ├── import_shapefiles.py        # Downloads + filters TIGER/Line tract shapefile
│   └── generate_mock_data.py       # Generates mock partner + census + CDC data
├── tests/
│   ├── unit/                       # Unit tests for each src/ module
│   ├── integration/                # End-to-end pipeline tests
│   └── fixtures/                   # Sample CSVs for tests
├── docs/spec.md                    # Full feature specification
├── ASSUMPTIONS.md                  # Architectural decisions and deviations
├── requirements.txt                # Pinned Python dependencies
└── .env.example                    # Environment variable template
```

---

## Setup

### Prerequisites

- Python 3.11+
- Git

### One-command setup (recommended)

```bash
bash scripts/setup.sh
```

This creates a `.venv`, installs dependencies, downloads the Davidson County shapefile from the US Census Bureau, and generates mock data for local development.

### Manual setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download Davidson County census tract boundaries
python scripts/import_shapefiles.py

# Generate mock data for local development
python scripts/generate_mock_data.py
```

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Production only | AWS credentials for S3 access |
| `AWS_SECRET_ACCESS_KEY` | Production only | AWS credentials for S3 access |
| `AWS_DEFAULT_REGION` | Production only | AWS region (default: `us-east-1`) |
| `AWS_BUCKET_NAME` | Production only | S3 bucket containing the NFP data CSVs |
| `USE_MOCK_DATA` | No | Set to `true` to load from `data/mock/` instead of S3 |
| `MOCK_DATA_DIR` | No | Path to mock data directory (default: `data/mock/`) |

For **local development**, set `USE_MOCK_DATA=true` — no AWS credentials needed.

---

## Running

```bash
source .venv/bin/activate
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

---

## Data Sources

| Layer | Source | Vintage |
|---|---|---|
| Census tract boundaries | US Census TIGER/Line 2020 | 2020 |
| Poverty rate | ACS 5-Year Estimates | 2022 |
| Median household income | ACS 5-Year Estimates | 2022 |
| Diabetes prevalence | CDC PLACES | 2022 |
| NFP partner locations | Nashville Food Project (via S3) | Current |

Production data CSVs are stored in S3 at `s3://<AWS_BUCKET_NAME>/nfp-mapping/`.

---

## Testing

```bash
source .venv/bin/activate
pytest
```

Run with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

Test layout:
- `tests/unit/` — unit tests for `config`, `data_loader`, `geocoder`, `layer_manager`
- `tests/integration/test_full_pipeline.py` — CSV load → GEOID normalization → map object construction
- `tests/fixtures/` — sample CSVs used by tests

---

## Deployment

This app is designed for **Streamlit Community Cloud**.

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set `app.py` as the entry point.
4. Add AWS credentials and `AWS_BUCKET_NAME` as secrets in the Streamlit Cloud dashboard.
5. Leave `USE_MOCK_DATA` unset (or `false`) for production.
