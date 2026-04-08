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
during data loading to improve map rendering performance. The tolerance is
configurable via `map_display.simplify_tolerance` in `project.yml`.

## A16: Nashville MSA Geographic Scope
The map covers the **Nashville-Davidson-Murfreesboro-Franklin Metropolitan
Statistical Area** as defined by the U.S. Office of Management and Budget —
14 Tennessee counties: Cannon, Cheatham, Davidson, Dickson, Hickman, Macon,
Maury, Robertson, Rutherford, Smith, Sumner, Trousdale, Williamson, and
Wilson. The county set lives in `project.yml` under `geography.msa_counties`
and is the single source of truth for pipeline filtering and the Home page
stats.

## A17: USDA LILA Data Vintage and 2010→2020 Crosswalk
USDA LILA data is published on **2019 ACS estimates with 2010 Census tract
boundaries**, while the rest of the map uses 2020 boundaries. The pipeline
applies the U.S. Census Bureau's official 2010-to-2020 Tract Relationship
File to convert LILA values onto 2020 tract geometries:

- Binary flags use **max() aggregation** (a 2020 tract inherits LILA if any
  contributing 2010 tract was flagged) — a conservative, planning-friendly
  approach.
- Population counts use **area-weighted apportionment** with `OPP_TRACT_10`
  and are returned as integers.
- Rates use **area-weighted means**.
- Tiny intersection slivers (`OPP_TRACT_10 < 0.01`) are filtered out.

LILA values on the map should be treated as modeled approximations on 2020
geography, not direct measurements. LILA is **tract-only** — the layer is
disabled in the sidebar at ZIP granularity with a tooltip pointing the user
back to the Census Tracts view.

## A18: Giving Matters Integration is Activation-Ready
The CFMT *Giving Matters* dataset has not yet been received. The pipeline
step (`pipeline/process_giving_matters.py`) and the sidebar / map render
path are wired but **deactivated**:

- `data_sources.giving_matters.enabled: false` in `project.yml`
- `process_giving_matters` returns `None` immediately when disabled, on
  `NoSuchKey`/`NoSuchBucket`/`404`, or when `required_columns` are missing
- The sidebar "Community Partners" section only renders when
  `data/points/giving_matters.geojson` exists
- The map renderer adds the Giving Matters layer only when both the file
  exists AND the user checks the sidebar checkbox

Activation requires only data + a config flip (no code changes). See the
README "Enabling Giving Matters" section.

## A19: County Boundaries Use Dashed Lines
The 14 MSA county boundaries are rendered as a separate `FeatureGroup` with
**dashed lines** (`dashArray: "5,5"`) and a transparent fill so they provide
geographic orientation without visually competing with tract-level
choropleth shading. The layer is on by default and toggleable via
LayerControl.

## A20: Categorical vs Continuous Layers
Layer rendering branches on `layer_type` in `project.yml`:

- **Continuous** (default) → branca `LinearColormap` with a gradient legend.
- **Categorical** → discrete two-tone palette (`#EEEEEE` for 0/Not LILA,
  `#B71C1C` for 1/LILA Tract) with discrete swatch legend entries.

`config_loader.get_layer_type()` and `get_layer_categories()` expose this to
the layer manager and the bottom-right legend builder, which renders both
gradient and swatch sections in a single combined Leaflet control.

## A21: Multi-Page Streamlit Structure
The application is a multi-page Streamlit app:

- `app.py` — Home page (cover/landing, project overview, dynamic stats bar,
  navigation cards, branding, "data last updated" footer)
- `pages/1_Map.py` — interactive Map page (all sidebar controls + map)
- `pages/2_About_the_Data.py` — methodology, vintage, limitations

The branded green-gradient hero lives only on Home; the Map page uses a
lighter header with a granularity-aware breadcrumb subtitle. Each page calls
`st.set_page_config(...)` as its first Streamlit call.
