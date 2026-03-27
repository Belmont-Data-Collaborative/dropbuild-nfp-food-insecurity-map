# Assumptions & Architectural Decisions

## A1: Map Export Format
The export button delivers an interactive HTML file, not a static PNG.
PNG export requires a headless browser, which is not available in pure Streamlit.
The HTML file is fully interactive and offline-viewable.

## A2: Geocoding Rate Limiting
Nominatim's usage policy requires max 1 request per second. We enforce this with
`time.sleep(1)` between uncached geocoding requests. Geocoding now happens in the
pipeline (`python -m pipeline --step partners`), not at app runtime.

## A3: Geocoding Failure Handling
Individual geocoding failures are handled silently by setting latitude/longitude
to NaN. The pipeline logs a summary ("Geocoded 28/30 partners (2 failed)").
No exceptions are raised for individual address failures.

## A4: GEOID Normalization
All GEOID values across Census, CDC PLACES, and GeoJSON data are normalized to
11 characters using `str.zfill(11)`. This applies in both the pipeline and the
data loading layer.

## A5: YAML Config as Source of Truth
`project.yml` is the single source of truth for layer definitions, partner types,
colors, icons, S3 paths, and geographic settings. Adding a new choropleth layer
requires only a YAML edit — no Python changes needed.

## A6: Environment-Driven Config Separation
`src/config.py` retains only environment-driven settings (`APP_ENV`, `USE_MOCK_DATA`,
AWS credentials) and user-facing message constants. All layer/partner/geography
config is in `project.yml`, accessed via `src/config_loader.py`.

## A7: Exception Ownership
Custom exceptions are defined in the module that raises them:
- `DataLoadError`, `DataSchemaError` in `src/data_loader.py`
- `GeocodingError` in `src/geocoder.py` and `pipeline/process_partners.py`

## A8: Script Independence
Scripts in `scripts/` and `pipeline/` are standalone. Scripts do NOT import from
`src/` modules (which import Streamlit). The pipeline reads `project.yml` directly.

## A9: Configurable Color Scales
Each choropleth layer has its own colormap defined in `project.yml`. Defaults are
colorblind-friendly: YlGnBu for income/population, YlOrRd for poverty/disease.

## A10: Pipeline Before App
Data processing happens in the pipeline CLI (`python -m pipeline`). The Streamlit
app only reads pre-built Parquet and GeoJSON files. No runtime geocoding, no
runtime CSV parsing from S3.

## A11: Multi-Granularity
The app supports Census Tract and ZIP Code granularity, toggled via a radio button.
Both use the same pipeline and data loading patterns.

## A12: Pins Replace Dots
Partner markers use `folium.Marker` with `folium.Icon` (Font Awesome) instead of
`CircleMarker`. Each partner type has a distinct colored pin with a relevant icon.

## A13: LayerControl
All choropleth layers and partner markers are wrapped in named `FeatureGroup`
objects, enabling Folium's built-in `LayerControl` for in-map toggling.

## A14: Cached Map HTML
`build_map_html()` is cached with `@st.cache_data` keyed by
`(granularity, show_partners, tuple(selected_layers))`. Repeated interactions
with the same settings serve instantly from cache.

## A15: Geometry Simplification
GeoJSON geometries are simplified with `simplify(0.001, preserve_topology=True)`
during data loading to improve map rendering performance.
