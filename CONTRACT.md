# NFP Food Insecurity Map — Module Contract

**App ID**: nfp-food-insecurity-map
**Runtime**: streamlit (Python 3.11)

---

## Configuration Modules

### project.yml
Single source of truth for all layer definitions, partner types, colors, icons,
S3 paths, geographic settings, and map display options.

### src/config_loader.py
YAML config parser. Zero internal state — loads `project.yml` once and caches.

```python
def get_project() -> dict[str, Any]
def get_geography() -> dict[str, Any]
def get_data_sources() -> dict[str, Any]
def get_all_layer_configs() -> list[dict[str, Any]]
def get_partner_config() -> dict[str, Any]
def get_map_display() -> dict[str, Any]
def get_granularities() -> list[dict[str, Any]]
def reload_config() -> dict[str, Any]
```

### src/config.py
Environment-driven settings only. No layer definitions, no partner types.

**Constants**: `APP_ENV`, `IS_PRODUCTION`, `LOG_LEVEL`, `AWS_BUCKET_NAME`,
`USE_MOCK_DATA`, `MOCK_DATA_DIR`, `ERROR_DATA_LOAD`, `ERROR_MISSING_COLUMN`,
`WARNING_GEOCODE_FAILURES`, `WARNING_NO_GEOID_MATCH`.

---

## Data Loading Modules

### src/data_loader.py
Loads Parquet + GeoJSON. Multi-granularity support.

**Exceptions**: `DataLoadError`, `DataSchemaError`

```python
@st.cache_data(ttl=3600)
def load_geodata(granularity: str) -> gpd.GeoDataFrame

@st.cache_data(ttl=3600)
def load_geojson_dict(granularity: str) -> dict
```

### src/partner_loader.py
Loads pre-built partner GeoJSON from pipeline output.

```python
@st.cache_data(ttl=3600)
def load_partners() -> gpd.GeoDataFrame
```

### src/geocoder.py
Nominatim geocoding — used by pipeline, not by app directly.

**Exceptions**: `GeocodingError`

```python
@st.cache_data
def geocode_partners(partners_df: pd.DataFrame) -> pd.DataFrame
```

---

## Map Modules

### src/layer_manager.py
Builds Folium layers as named FeatureGroups.

```python
def build_partner_markers(
    partners_gdf: gpd.GeoDataFrame,
    partner_config: dict[str, Any],
) -> folium.FeatureGroup

def build_choropleth_layer(
    gdf: gpd.GeoDataFrame,
    layer_config: dict[str, Any],
) -> tuple[folium.FeatureGroup, branca.colormap.LinearColormap]

def build_boundary_layer(
    gdf: gpd.GeoDataFrame,
) -> folium.FeatureGroup
```

### src/map_builder.py
Assembles all layers into cached HTML.

```python
@st.cache_data(ttl=3600)
def build_map_html(
    granularity: str,
    show_partners: bool,
    selected_layers: tuple[str, ...],
) -> str
```

---

## Pipeline Modules

### pipeline/__main__.py
CLI entry point: `python -m pipeline [--step NAME] [--inspect NAME]`

### pipeline/load_source.py
Generic S3/local data loader with GEOID normalization and Parquet output.

```python
def process_data_source(source_key, source_config, geography, granularity) -> pd.DataFrame | None
```

### pipeline/process_partners.py
Partner geocoding pipeline: CSV → geocode → GeoJSON.

```python
def run(partner_config, use_mock, mock_dir) -> None
```

---

## App Entry Point

### app.py
Decomposed `main()` calling:

```python
def _configure_page() -> None
def _inject_custom_css() -> None
def _render_header() -> None
def _render_sidebar() -> tuple[str, bool, list[str]]
def _render_map(granularity, show_partners, selected_layers) -> None
def _render_partner_legend() -> None
def _render_data_freshness() -> None
```

---

## Data Flow

```
project.yml
    ↓
config_loader.py (accessor functions)
    ↓
pipeline/ (CLI: python -m pipeline)
    ├── load_source.py → data/choropleth/*.parquet
    ├── process_partners.py → data/points/partners.geojson
    └── process_geographic_data.py → data/geo/*.geojson
    ↓
app.py (Streamlit)
    ├── data_loader.load_geodata(granularity) → GeoDataFrame
    ├── partner_loader.load_partners() → GeoDataFrame
    ├── layer_manager.build_choropleth_layer() → FeatureGroup
    ├── layer_manager.build_partner_markers() → FeatureGroup
    ├── map_builder.build_map_html() → cached HTML string
    └── st.components.v1.html(map_html)
```
