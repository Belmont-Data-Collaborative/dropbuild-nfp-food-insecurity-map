# NFP Food Insecurity Map — Module Contract

**Contract Type**: moduleContract
**App ID**: nfp-food-insecurity-map
**Runtime**: streamlit (Python 3.11)

This is the SINGLE SOURCE OF TRUTH for all module interfaces. All teammates MUST use
the EXACT function names, signatures, constants, and exception classes defined here.

---

## Module Definitions

### src/config.py

**Purpose**: Single source of truth for all constants and configuration. Zero internal
imports (no imports from other src/ modules). No exception classes defined here.

**Private Functions**:

```python
def _get_secret(key: str, default: str | None = None) -> str | None:
    """Check os.environ.get(key) FIRST, then fall back to st.secrets.
    NEVER call st.secrets before checking os.environ — it crashes at import time."""
```

**Constants**:

| Name | Type | Source |
|------|------|--------|
| `AWS_BUCKET_NAME` | `str` | `_get_secret("AWS_BUCKET_NAME", "")` |
| `S3_PARTNERS_KEY` | `str` | `"nfp-mapping/nfp_partners.csv"` |
| `S3_CENSUS_KEY` | `str` | `"nfp-mapping/census_tract_data.csv"` |
| `S3_CDC_PLACES_KEY` | `str` | `"nfp-mapping/cdc_places_data.csv"` |
| `S3_GEOCODE_CACHE_KEY` | `str` | `"nfp-mapping/geocode_cache.csv"` |
| `PARTNERS_CSV_COLUMNS` | `list[str]` | `["partner_name", "address", "partner_type"]` |
| `CENSUS_CSV_COLUMNS` | `list[str]` | `["GEOID", "poverty_rate", "median_household_income", "data_vintage"]` |
| `CDC_PLACES_CSV_COLUMNS` | `list[str]` | `["GEOID", "DIABETES_CrudePrev", "data_vintage"]` |
| `PARTNER_TYPE_COLORS` | `dict[str, str]` | See below |
| `PARTNER_TYPE_LABELS` | `dict[str, str]` | See below |
| `FALLBACK_COLOR` | `str` | `"#CCCCCC"` |
| `CHOROPLETH_LAYERS` | `list[dict]` | See below |
| `DEFAULT_CHOROPLETH_LAYER` | `str` | `"median_income"` |
| `CDC_PLACES_INDICATOR_COLUMN` | `str` | `"DIABETES_CrudePrev"` |
| `DAVIDSON_CENTER` | `list[float]` | `[36.1627, -86.7816]` |
| `DEFAULT_ZOOM` | `int` | `11` |
| `GEOJSON_PATH` | `str` | `"data/shapefiles/davidson_county_tracts.geojson"` |
| `MOCK_DATA_DIR` | `str` | From env, default `"data/mock/"` |
| `USE_MOCK_DATA` | `bool` | From env, default `False` |
| `ERROR_DATA_LOAD` | `str` | `"Map data could not be loaded. Please refresh the page or contact BDAIC support."` |
| `ERROR_MISSING_COLUMN` | `str` | `"Partner data is missing required column: {column_name}. Please check the data file."` |
| `WARNING_GEOCODE_FAILURES` | `str` | `"{count} partner location(s) could not be mapped due to address lookup errors."` |
| `WARNING_NO_GEOID_MATCH` | `str` | `"No data could be matched to map boundaries. Please contact BDAIC support."` |

**PARTNER_TYPE_COLORS** (exact hex values):

```python
PARTNER_TYPE_COLORS = {
    "school_summer": "#E41A1C",
    "medical_health": "#377EB8",
    "transitional_housing": "#4DAF4A",
    "senior_services": "#984EA3",
    "community_development": "#FF7F00",
    "homeless_outreach": "#A65628",
    "workforce_development": "#F781BF",
    "after_school": "#999999",
}
```

**PARTNER_TYPE_LABELS** (plain-English display names):

```python
PARTNER_TYPE_LABELS = {
    "school_summer": "School & Summer Programs",
    "medical_health": "Medical & Health Services",
    "transitional_housing": "Transitional Housing",
    "senior_services": "Senior Services",
    "community_development": "Community Development",
    "homeless_outreach": "Homeless Outreach",
    "workforce_development": "Workforce Development",
    "after_school": "After-School Programs",
}
```

**CHOROPLETH_LAYERS** (list of layer config dicts):

```python
CHOROPLETH_LAYERS = [
    {
        "id": "poverty_rate",
        "display_name": "Poverty Rate (Census)",
        "csv_source": "census",
        "csv_column": "poverty_rate",
        "unit_label": "%",
        "format_string": "{value:.1f}%",
        "data_vintage_key": "data_vintage",
    },
    {
        "id": "median_income",
        "display_name": "Median Household Income (Census)",
        "csv_source": "census",
        "csv_column": "median_household_income",
        "unit_label": "$",
        "format_string": "${value:,.0f}",
        "data_vintage_key": "data_vintage",
    },
    {
        "id": "diabetes_prevalence",
        "display_name": "Diabetes Prevalence (CDC PLACES)",
        "csv_source": "cdc_places",
        "csv_column": "DIABETES_CrudePrev",
        "unit_label": "%",
        "format_string": "{value:.1f}%",
        "data_vintage_key": "data_vintage",
    },
]
```

---

### src/data_loader.py

**Purpose**: Data loading from S3 or local mock files. Handles CSV loading, schema
validation, and GEOID normalization.

**Exceptions defined here**:
- `DataLoadError(Exception)` — raised when data cannot be loaded (S3 error, file missing)
- `DataSchemaError(Exception)` — raised when loaded data is missing required columns

**Functions**:

```python
@st.cache_resource
def get_s3_client() -> boto3.client:
    """Create and cache a boto3 S3 client."""

@st.cache_data
def load_csv_from_s3(bucket: str, key: str) -> pd.DataFrame:
    """Load a CSV from S3 into a DataFrame. Raises DataLoadError on failure."""

@st.cache_data
def load_csv_from_file(path: str) -> pd.DataFrame:
    """Load a CSV from local disk into a DataFrame. Raises DataLoadError on failure."""

@st.cache_data
def load_partners_data() -> pd.DataFrame:
    """Load partners CSV (from S3 or mock). Validates required columns.
    Raises DataLoadError, DataSchemaError."""

@st.cache_data
def load_census_data() -> pd.DataFrame:
    """Load census CSV (from S3 or mock). Normalizes GEOID with zfill(11).
    Raises DataLoadError, DataSchemaError."""

@st.cache_data
def load_cdc_places_data() -> pd.DataFrame:
    """Load CDC PLACES CSV (from S3 or mock). Normalizes GEOID with zfill(11).
    Raises DataLoadError, DataSchemaError."""

@st.cache_data
def load_geojson() -> dict:
    """Load GeoJSON from disk. Normalizes feature GEOID properties to 11 chars.
    Raises DataLoadError if file is missing."""
```

---

### src/geocoder.py

**Purpose**: Geocoding partner addresses using Nominatim with caching.

**Exceptions defined here**:
- `GeocodingError(Exception)` — for fatal initialization errors only. NEVER raised for
  individual address failures.

**Functions**:

```python
@st.cache_resource
def get_nominatim_geolocator() -> Nominatim:
    """Create and cache a Nominatim geolocator instance."""

@st.cache_data
def load_geocode_cache(bucket: str | None = None) -> pd.DataFrame:
    """Load geocode cache from S3 or local mock file.
    Returns empty DataFrame if cache does not exist."""

@st.cache_data
def geocode_partners(partners_df: pd.DataFrame) -> pd.DataFrame:
    """Geocode partner addresses. Returns DataFrame with columns:
    partner_name, address, latitude, longitude, geocode_status.

    - Checks cache first for each address.
    - Calls Nominatim for uncached addresses (max 1 req/sec).
    - Appends ', Davidson County, TN, USA' to each address query.
    - NEVER raises for individual address failures — sets NaN for lat/lon
      and 'failed' for geocode_status.
    - Writes updated cache to S3 (skipped in mock mode).
    - S3 write failures are logged to console only — app continues."""
```

---

### src/layer_manager.py

**Purpose**: Constructs Folium map layers (GeoJSON boundaries, choropleth, markers).

**Exceptions defined here**: None.

**Functions**:

```python
def build_tract_boundaries_layer(geojson: dict) -> folium.GeoJson:
    """Build a Folium GeoJSON layer for census tract boundaries.
    Returns a single GeoJson object (NOT a tuple)."""

def build_choropleth_layer(
    geojson: dict,
    df: pd.DataFrame,
    layer_config: dict,
) -> tuple[folium.GeoJson, branca.colormap.LinearColormap]:
    """Build a choropleth GeoJSON layer with YlOrRd color scale.
    Returns a 2-tuple: (GeoJson layer, LinearColormap legend).

    - Lighter = lower value, darker/redder = higher value.
    - Tracts missing from df render in neutral gray #EEEEEE.
    - Popup shows: 'Census Tract [number]', formatted value, data vintage.
    - When no data: popup shows 'Data not available for this tract.'"""

def build_partner_markers(geocoded_df: pd.DataFrame) -> list[folium.CircleMarker]:
    """Build CircleMarker objects for geocoded partners.
    Returns a list of CircleMarker objects.

    - Colors from config.PARTNER_TYPE_COLORS.
    - Unrecognized types use config.FALLBACK_COLOR with label 'Unknown Type'.
    - Popup: organization name, display label (from PARTNER_TYPE_LABELS), 'Nashville Food Project Partner'.
    - Console warning for unrecognized partner_type values."""
```

---

### src/map_builder.py

**Purpose**: Assembles all layers into a single Folium map.

**Exceptions defined here**: None.

**Functions**:

```python
def build_map(
    geojson: dict,
    census_df: pd.DataFrame | None,
    cdc_df: pd.DataFrame | None,
    geocoded_df: pd.DataFrame | None,
    selected_layer_id: str | None,
    show_partners: bool,
) -> folium.Map:
    """Build the complete Folium map.

    - Centered on config.DAVIDSON_CENTER at config.DEFAULT_ZOOM.
    - Always includes tract boundary layer.
    - Adds choropleth layer if selected_layer_id is not None.
    - Adds partner markers if show_partners is True and geocoded_df is provided.
    - Adds legend colormap to bottom-right if choropleth is active.
    - Returns a folium.Map object."""
```

---

### app.py (Streamlit Entrypoint)

**Purpose**: Thin Streamlit entry point. Orchestrates data loading, geocoding, map
building, and sidebar UI. No business logic — delegates to src/ modules.

**Critical Patterns**:
1. `from __future__ import annotations` — FIRST LINE.
2. `from dotenv import load_dotenv` then `load_dotenv()` — BEFORE any src/ imports.
3. First Streamlit call in `main()` MUST be `st.set_page_config()`.
4. Import exceptions from the module that defines them:
   - `from src.data_loader import DataLoadError, DataSchemaError`
   - `from src.geocoder import GeocodingError`
5. Import constants from config:
   - `from src.config import ERROR_DATA_LOAD, WARNING_GEOCODE_FAILURES, ...`

---

## Shared Constants (exact import names)

All imported from `src.config`:

- `config.AWS_BUCKET_NAME`
- `config.S3_PARTNERS_KEY`
- `config.S3_CENSUS_KEY`
- `config.S3_CDC_PLACES_KEY`
- `config.S3_GEOCODE_CACHE_KEY`
- `config.PARTNERS_CSV_COLUMNS`
- `config.CENSUS_CSV_COLUMNS`
- `config.CDC_PLACES_CSV_COLUMNS`
- `config.PARTNER_TYPE_COLORS`
- `config.PARTNER_TYPE_LABELS`
- `config.FALLBACK_COLOR`
- `config.CHOROPLETH_LAYERS`
- `config.DEFAULT_CHOROPLETH_LAYER`
- `config.CDC_PLACES_INDICATOR_COLUMN`
- `config.DAVIDSON_CENTER`
- `config.DEFAULT_ZOOM`
- `config.GEOJSON_PATH`
- `config.MOCK_DATA_DIR`
- `config.USE_MOCK_DATA`
- `config.ERROR_DATA_LOAD`
- `config.ERROR_MISSING_COLUMN`
- `config.WARNING_GEOCODE_FAILURES`
- `config.WARNING_NO_GEOID_MATCH`

---

## Exception Classes (and where they are defined)

| Exception | Defined In | Imported By |
|-----------|-----------|-------------|
| `DataLoadError` | `src/data_loader.py` | `app.py` |
| `DataSchemaError` | `src/data_loader.py` | `app.py` |
| `GeocodingError` | `src/geocoder.py` | `app.py` |

**NEVER import exceptions from `src/config.py`** — config.py defines constants only.

---

## Data Flow

```
app.py
  |
  |-- load_partners_data() --> pd.DataFrame (from src.data_loader)
  |     |
  |     +-- geocode_partners(partners_df) --> pd.DataFrame (from src.geocoder)
  |           |
  |           +-- build_partner_markers(geocoded_df) --> list[CircleMarker] (from src.layer_manager)
  |
  |-- load_census_data() --> pd.DataFrame (from src.data_loader)
  |-- load_cdc_places_data() --> pd.DataFrame (from src.data_loader)
  |-- load_geojson() --> dict (from src.data_loader)
  |     |
  |     +-- build_tract_boundaries_layer(geojson) --> GeoJson (from src.layer_manager)
  |     +-- build_choropleth_layer(geojson, df, config) --> (GeoJson, Colormap) (from src.layer_manager)
  |
  +-- build_map(geojson, census_df, cdc_df, geocoded_df, layer_id, show_partners) --> Map (from src.map_builder)
       |
       +-- st_folium(map, returned_objects=[]) --> render in Streamlit
```

---

## Sidebar Layout (exact order)

1. `st.title('Nashville Food Project — Food Insecurity Map')` + 2-sentence description
2. `st.divider()`
3. `st.subheader('Data Layers')` + checkbox + selectbox
4. `st.divider()`
5. `st.subheader('Partner Type Legend')` + colored HTML swatches
6. `st.divider()`
7. `st.subheader('Export')` + download button (HTML export, labeled '⬇ Download Map as PNG')
8. `st.divider()`
9. `st.subheader('Data Sources')` + data freshness notice

---

## Scripts (standalone — NO src/ imports)

### scripts/import_shapefiles.py
- Downloads Census TIGER/Line TN tract shapefile
- Filters to Davidson County FIPS 037
- Asserts 200-300 rows
- Reprojects to EPSG:4326
- Retains GEOID/NAME/NAMELSAD/geometry
- Zero-pads GEOID to 11 chars
- Writes to data/shapefiles/davidson_county_tracts.geojson
- Supports --output PATH flag

### scripts/generate_mock_data.py
- Reads GEOIDs from data/shapefiles/davidson_county_tracts.geojson
- Generates mock_nfp_partners.csv, mock_census_tract_data.csv, mock_cdc_places_data.csv
- Supports --seed and --output-dir flags
- Byte-identical output for same seed

### scripts/setup.sh
- Creates .venv, installs requirements, runs both scripts above
