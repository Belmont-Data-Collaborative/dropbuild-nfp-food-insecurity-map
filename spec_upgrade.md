# Upgrade Spec: Dropbuild NFP Food Insecurity Map (Streamlit Enhanced)

## Overview

**Goal**: Upgrade the existing `dropbuild-nfp-food-insecurity-map` Streamlit application in-place — keeping the Streamlit framework — while adding multi-granularity support, a proper S3 data pipeline, improved partner (pin-drop) data handling, a polished UI, and fixes for all identified security and best-practice violations.

**Working Directory**: `dropbuild-nfp-food-insecurity-map/` (checked out on a new development branch)

**Reference Application**: `bdaic-nfp-food-insecuirty-map/` — use this as a reference for its data pipeline, S3 integration patterns, and YAML-driven configuration. Do not convert to Flask. Read its files to understand patterns you'll adapt for Streamlit.

**AWS Access**: Full AWS credentials are available in the environment. The S3 bucket (`bdaic-public-transform`) and data paths match the BDAIC app's `project.yml`.

---

## Current State (What Exists)

The dropbuild app is a **Streamlit** application with:
- `app.py` — Single entry point with a monolithic `main()` function (cyclomatic complexity: 35)
- `src/config.py` — Hardcoded constants (partner colors, S3 paths, column names, choropleth layer definitions)
- `src/data_loader.py` — CSV loading from S3 with custom exceptions (`DataLoadError`, `DataSchemaError`)
- `src/geocoder.py` — Nominatim geocoding with S3 cache write-back (`GeocodingError`)
- `src/layer_manager.py` — Folium layer builders (choropleth, boundaries, CircleMarkers for partners)
- `src/map_builder.py` — Map assembly
- `data/shapefiles/davidson_county_tracts.geojson` — Census tract boundaries only (no ZIP codes)
- `data/mock/` — Mock CSV data for local development
- `tests/` — Unit and integration tests
- `scripts/` — Setup, shapefile import, mock data generation

**Key limitations to fix:**
- Single granularity (tract only — no ZIP code view)
- No data pipeline (data loaded directly from CSV in S3)
- Partner locations rendered as CircleMarkers (dots), not pin markers
- No `LayerControl` — user cannot toggle layers within the Folium map
- No geometry simplification (raw GeoJSON passed to Folium)
- Monolithic `main()` function is untestable
- No production/development config separation
- No tile attribution
- `.env` committed to version control
- Missing `.gitignore` patterns for sensitive files
- 7 broad `except Exception` blocks
- Export button says "Download as PNG" but delivers HTML

---

## Target State (What to Build)

An **enhanced Streamlit** application with:
- Census tract AND ZIP code granularity toggle
- Full S3 data pipeline (Census ACS + CDC PLACES) outputting Parquet files
- Proper partner data pipeline (S3 source → geocoding with cache → GeoJSON output)
- Pin markers (not dots) for partner locations
- `LayerControl` for toggling data layers and partner markers on the map
- Aggressive `st.cache_data` for built map HTML keyed by layer selections
- Polished UI: custom CSS theme, branded header, improved sidebar, better legend, loading states
- All security and best-practice violations resolved

---

## Phase 1: Configuration System

### 1.1 Create `project.yml`

Introduce a YAML configuration file as the single source of truth (adapted from the BDAIC pattern for Streamlit). This replaces hardcoded constants in `src/config.py`.

```yaml
project:
  name: "NFP Food Insecurity Map"
  slug: "nfp-food-insecurity-map"
  primary_org: "Nashville Food Project"
  secondary_org: "BDAIC"

geography:
  state_fips: "47"
  county_fips: "037"
  county_name: "Davidson County"
  state_name: "Tennessee"
  map_center: [36.1627, -86.7816]
  default_zoom: 11
  tiger_year: 2023

data_sources:
  census_acs:
    source_type: s3
    s3_bucket: bdaic-public-transform
    s3_prefix:
      tract: "nfp-mapping/census/acs/tract/"
      zip: "nfp-mapping/census/acs/zcta/"
    output_prefix: acs
    geoid_column: GEO_ID
    variables:
      - column: DP03_0062E
        display_name: "Median Household Income"
        colormap: YlGnBu
        legend_name: "Median Household Income ($)"
        format_str: "${:,.0f}"
        tooltip_alias: "Income"
        default_visible: true
      - column: DP03_0119PE
        display_name: "Poverty Rate"
        colormap: YlOrRd
        legend_name: "Poverty Rate (%)"
        format_str: "{:.1f}%"
        tooltip_alias: "Poverty"
        default_visible: false
      - column: DP05_0001E
        display_name: "Total Population"
        colormap: Blues
        legend_name: "Population"
        format_str: "{:,.0f}"
        tooltip_alias: "Population"
        default_visible: false

  health_lila:
    source_type: s3
    s3_bucket: bdaic-public-transform
    s3_prefix:
      tract: "nfp-mapping/health/cdc_places/tract/"
      zip: "nfp-mapping/health/cdc_places/zcta/"
    output_prefix: health_lila
    geoid_column: LocationID
    filters:
      - column: Data_Value_Type
        value: "Crude prevalence"
    variables:
      - column: DIABETES_CrudePrev
        display_name: "Diabetes Prevalence"
        colormap: YlOrRd
        legend_name: "Diabetes Prevalence (%)"
        format_str: "{:.1f}%"
        tooltip_alias: "Diabetes"
        default_visible: false
      - column: HIGHBP_CrudePrev
        display_name: "Hypertension Prevalence"
        colormap: Reds
        legend_name: "Hypertension Prevalence (%)"
        format_str: "{:.1f}%"
        tooltip_alias: "Hypertension"
        default_visible: false
      - column: OBESITY_CrudePrev
        display_name: "Obesity Prevalence"
        colormap: OrRd
        legend_name: "Obesity Prevalence (%)"
        format_str: "{:.1f}%"
        tooltip_alias: "Obesity"
        default_visible: false

partners:
  source_type: s3
  s3_bucket: bdaic-public-transform
  s3_key: "nfp-mapping/partners/nfp_partners.csv"
  geocode_cache_key: "nfp-mapping/partners/geocode_cache.csv"
  popup_fields:
    - partner_name
    - address
    - partner_type
  types:
    school_summer:
      label: "School & Summer Programs"
      color: "#E41A1C"
      icon: "graduation-cap"
    medical_health:
      label: "Medical & Health Services"
      color: "#377EB8"
      icon: "heartbeat"
    transitional_housing:
      label: "Transitional Housing"
      color: "#4DAF4A"
      icon: "home"
    senior_services:
      label: "Senior Services"
      color: "#984EA3"
      icon: "user"
    community_development:
      label: "Community Development"
      color: "#FF7F00"
      icon: "users"
    homeless_outreach:
      label: "Homeless Outreach"
      color: "#A65628"
      icon: "hand-holding-heart"
    workforce_development:
      label: "Workforce Development"
      color: "#F781BF"
      icon: "briefcase"
    after_school:
      label: "After-School Programs"
      color: "#999999"
      icon: "child"

map_display:
  tiles: cartodbpositron
  tile_attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  min_zoom: 10
  max_zoom: 16
  granularities:
    - id: tract
      label: "Census Tracts"
      geo_file: "data/geo/tracts.geojson"
    - id: zip
      label: "ZIP Codes"
      geo_file: "data/geo/zipcodes.geojson"
```

Adjust S3 paths to match the actual bucket structure (read the BDAIC app's `project.yml` for the real paths).

### 1.2 Create `src/config_loader.py`

YAML config parser providing accessor functions:
- `get_project()` → project metadata dict
- `get_geography()` → geography dict (FIPS, center, zoom)
- `get_data_sources()` → dict of data source configs
- `get_all_layer_configs()` → flattened list of all choropleth variable configs (across all sources)
- `get_partner_config()` → partner types, colors, icons, S3 paths
- `get_map_display()` → map display settings
- `get_granularities()` → list of granularity dicts

Cache the parsed YAML (load once). Support `PROJECT_CONFIG` env var to override the config file path.

### 1.3 Refactor `src/config.py`

Strip out all hardcoded constants that now live in `project.yml`:
- Remove `CHOROPLETH_LAYERS` dict
- Remove `PARTNER_TYPE_COLORS` and `PARTNER_TYPE_LABELS`
- Remove S3 paths and column name constants
- Keep only environment-driven settings: `USE_MOCK_DATA`, AWS credential loading, `APP_ENV`

Add environment-based config separation:
```python
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"
```

---

## Phase 2: Data Pipeline

### 2.1 Create `pipeline/` package

Model the pipeline after the BDAIC app's `pipeline/` (read its files for patterns), adapted for Streamlit.

#### `pipeline/__main__.py`

CLI entry point:
```
python -m pipeline                      # Run full pipeline
python -m pipeline --step geo           # Download geographic data only
python -m pipeline --step census_acs    # Process Census ACS only
python -m pipeline --step health_lila   # Process CDC PLACES only
python -m pipeline --step partners      # Process partner data only
python -m pipeline --inspect census_acs # Inspect a data source
```

#### `pipeline/load_source.py`

Generic S3/local data loader (model after BDAIC's `pipeline/load_source.py`):
- S3 prefix-based discovery (auto-find latest parquet/CSV under a prefix)
- S3 direct key loading
- Local path loading
- Per-granularity path resolution (tract vs. zip can have different S3 prefixes)
- Row-level filtering (e.g., CDC PLACES `Data_Value_Type == "Crude prevalence"`)
- GEOID normalization (11-character zero-fill)
- County-level filtering (FIPS prefix matching on GEOID)
- Census sentinel value replacement (negative values → NaN)
- Output to `data/choropleth/{prefix}_{granularity}_data.parquet`

### 2.2 Update `scripts/process_geographic_data.py`

Replace the current `scripts/import_shapefiles.py` with a script modeled after the BDAIC app's `scripts/process_geographic_data.py`. This must:
- Read geography config from `project.yml`
- Download TIGER/Line shapefiles from Census Bureau:
  - **Census tracts** — filtered to state FIPS, then county
  - **ZCTAs (ZIP code tabulation areas)** — all US, clipped to county boundary
  - **County boundary** — single polygon
- Save to `data/geo/` as GeoJSON: `tracts.geojson`, `zipcodes.geojson`, `county_boundary.geojson`
- Fix geometry issues from clipping with shapely

The old `scripts/import_shapefiles.py` should be removed after this replaces it.

### 2.3 Create `pipeline/process_partners.py`

Enhanced partner data pipeline combining the best of both apps:

**Flow:**
1. Load raw partner CSV from S3 (path from `project.yml`)
2. Validate required columns (partner_name, address, partner_type)
3. Load geocode cache from S3 (or local in mock mode)
4. Geocode uncached addresses via Nominatim (1 req/sec rate limit)
5. Validate geocoded coordinates fall within Davidson County bounding box
6. Write updated cache back to S3
7. Convert to GeoJSON and save to `data/points/partners.geojson`

**Carry over from current dropbuild:**
- Geocode caching with S3 write-back (from `src/geocoder.py`)
- Graceful blank/missing address handling
- `GeocodingError` exception
- Structured logging for per-address failures

**New enhancements:**
- Partner addresses loaded from S3, never hardcoded in source code (PII fix)
- Output as GeoJSON (not CSV) for direct Folium consumption
- Bounding box validation on coordinates
- Log summary: "Geocoded 28/30 partners (2 failed)" at INFO level

### 2.4 Update data directory structure

```
data/
├── geo/                     # Geographic boundaries (gitignored)
│   ├── tracts.geojson
│   ├── zipcodes.geojson
│   └── county_boundary.geojson
├── choropleth/              # Parquet data layers (gitignored)
│   ├── acs_tract_data.parquet
│   ├── acs_zipcode_data.parquet
│   ├── health_lila_tract_data.parquet
│   └── health_lila_zipcode_data.parquet
├── points/                  # Point layers (gitignored)
│   └── partners.geojson
├── mock/                    # Mock data (tracked in git — needed for local dev)
│   ├── mock_nfp_partners.csv
│   ├── mock_census_tract_data.csv
│   ├── mock_cdc_places_data.csv
│   └── mock_geocode_cache.csv
└── geocode_cache.csv        # Local geocode cache (gitignored)
```

---

## Phase 3: Data Loading Layer

### 3.1 Refactor `src/data_loader.py`

Replace the current CSV-based loading with Parquet loading from the pipeline output. Add multi-granularity support.

```python
@st.cache_data(ttl=3600)
def load_geodata(granularity: str) -> gpd.GeoDataFrame:
    """Load and merge geographic boundaries with all choropleth data for a granularity.

    Args:
        granularity: 'tract' or 'zip'

    Returns:
        Merged GeoDataFrame with all metric columns.
    """
    # 1. Load GeoJSON boundaries from data/geo/
    # 2. Simplify geometries: gdf.geometry.simplify(0.001, preserve_topology=True)
    # 3. Normalize GEOIDs to 11-char zero-fill
    # 4. For each data source in config, load its parquet and merge on GEOID
    # 5. Add formatted display columns using format_str from config
    # 6. Return merged GeoDataFrame
```

Key changes from current implementation:
- Loads **Parquet** files (from pipeline output), not raw CSVs
- Supports both `tract` and `zip` granularity
- **Applies geometry simplification** (currently missing — flagged in best practices)
- Merges ALL data sources (Census + CDC PLACES), not just one at a time
- Adds pre-formatted display columns for tooltips

### 3.2 Create `src/partner_loader.py`

New module for loading partner GeoJSON data:

```python
@st.cache_data(ttl=3600)
def load_partners() -> gpd.GeoDataFrame:
    """Load partner locations from GeoJSON (pipeline output).

    Returns:
        GeoDataFrame with partner_name, partner_type, geometry columns.
    """
    # Load from data/points/partners.geojson (output of pipeline/process_partners.py)
    # In mock mode, fall back to data/mock/ CSVs
```

This replaces the current pattern of loading CSV + geocoding at app runtime. Partners are now pre-geocoded by the pipeline.

### 3.3 Remove runtime geocoding from `app.py`

The current `app.py` calls `geocode_partners()` on every session start. Remove this. Partner geocoding now happens in the pipeline (`python -m pipeline --step partners`), and the app loads the pre-built GeoJSON.

Keep `src/geocoder.py` for the pipeline to import, but the Streamlit app should never call it directly.

---

## Phase 4: Map Building — Pins, LayerControl, Multi-Granularity

### 4.1 Refactor `src/layer_manager.py`

#### Convert CircleMarkers to Pin Markers

Replace `folium.CircleMarker` with `folium.Marker` using `folium.Icon`:

```python
def build_partner_markers(
    partners_gdf: gpd.GeoDataFrame,
    partner_config: dict,
) -> folium.FeatureGroup:
    """Build pin markers for partner locations.

    Returns a FeatureGroup containing Marker objects with Font Awesome icons.
    """
    fg = folium.FeatureGroup(name="NFP Partners", show=True)

    for _, row in partners_gdf.iterrows():
        partner_type = row.get("partner_type", "unknown")
        type_cfg = partner_config["types"].get(partner_type, {})
        color = type_cfg.get("color", "#CCCCCC")
        icon_name = type_cfg.get("icon", "map-marker")
        label = type_cfg.get("label", partner_type)

        popup_html = f"""
        <div style="min-width: 200px;">
            <strong>{row['partner_name']}</strong><br>
            <em>{label}</em><br>
            {row.get('address', '')}
        </div>
        """

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row["partner_name"],
            icon=folium.Icon(
                color="white",
                icon_color=color,
                icon=icon_name,
                prefix="fa",
            ),
        ).add_to(fg)

    return fg
```

**Note on `folium.Icon` color**: The `color` parameter controls the pin body color (limited preset values: red, blue, green, purple, orange, etc.). The `icon_color` parameter controls the icon glyph color inside the pin. To get full hex color control, consider using `folium.plugins.BeautifyIcon` or `folium.DivIcon` with custom HTML. Read Folium's documentation and test which approach gives the best visual result with the 8 partner type colors. If `BeautifyIcon` is available and gives better results, use it. The key requirement is that each partner type is visually distinguishable by color.

#### Add choropleth layers as named FeatureGroups

Each choropleth variable should be a separate `FeatureGroup` with a `name` parameter so `LayerControl` can toggle them:

```python
def build_choropleth_layer(
    gdf: gpd.GeoDataFrame,
    layer_config: dict,
) -> tuple[folium.FeatureGroup, branca.colormap.LinearColormap]:
    """Build a single choropleth layer as a toggleable FeatureGroup."""
    fg = folium.FeatureGroup(
        name=layer_config["display_name"],
        show=layer_config.get("default_visible", False),
    )
    # ... style function, GeoJson, tooltip, popup ...
    return fg, colormap
```

#### Fix dead code in `build_choropleth_layer`

The current implementation constructs a `GeoJson` object twice — the first is immediately overwritten. Remove the first construction entirely (AI recommendation, Dropbuild Important #5).

### 4.2 Refactor `src/map_builder.py`

Update to support multi-granularity and `LayerControl`:

```python
@st.cache_data(ttl=3600)
def build_map_html(
    granularity: str,
    show_partners: bool,
    selected_layers: list[str],
) -> str:
    """Build a complete Folium map and return its HTML string.

    Cached by granularity + layer selection combination.
    """
    geo = get_geography()
    map_cfg = get_map_display()

    m = folium.Map(
        location=geo["map_center"],
        zoom_start=geo["default_zoom"],
        tiles=map_cfg["tiles"],
        attr=map_cfg["tile_attribution"],  # Fix: explicit attribution
        min_zoom=map_cfg["min_zoom"],
        max_zoom=map_cfg["max_zoom"],
    )

    # Load merged geodata for this granularity
    gdf = load_geodata(granularity)

    # Add choropleth layers (each as a toggleable FeatureGroup)
    colormaps = {}
    for layer_cfg in get_all_layer_configs():
        if layer_cfg["column"] in selected_layers or layer_cfg.get("default_visible"):
            fg, cmap = build_choropleth_layer(gdf, layer_cfg)
            fg.add_to(m)
            colormaps[layer_cfg["display_name"]] = cmap

    # Add partner markers if enabled
    if show_partners:
        partners_gdf = load_partners()
        partner_fg = build_partner_markers(partners_gdf, get_partner_config())
        partner_fg.add_to(m)

    # Add LayerControl (previously missing)
    folium.LayerControl(collapsed=False).add_to(m)

    # Add active colormaps as legend
    for name, cmap in colormaps.items():
        cmap.caption = name
        cmap.add_to(m)

    return m._repr_html_()
```

**Key**: The function returns an HTML string, and `@st.cache_data` caches it keyed by `(granularity, show_partners, tuple(selected_layers))`. This means repeated interactions with the same settings serve instantly from cache.

---

## Phase 5: Streamlit UI — Polished Layout

### 5.1 Refactor `app.py` — Break Up `main()`

The monolithic `main()` (complexity 35) must be decomposed into testable functions:

```python
def main():
    _configure_page()
    _inject_custom_css()
    _render_header()

    # Sidebar
    granularity, show_partners, selected_layers = _render_sidebar()

    # Map
    _render_map(granularity, show_partners, selected_layers)

    # Footer
    _render_data_sources()
```

Each extracted function should be independently testable.

### 5.2 Page Config + Custom CSS

```python
def _configure_page():
    st.set_page_config(
        page_title="NFP Food Insecurity Map",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

def _inject_custom_css():
    st.markdown("""
    <style>
    /* Branded header bar */
    .main-header {
        background: linear-gradient(135deg, #2E7D32, #1B5E20);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .main-header h1 { margin: 0; font-size: 1.6rem; }
    .main-header p { margin: 0.25rem 0 0; opacity: 0.9; font-size: 0.9rem; }

    /* Sidebar section headers */
    .sidebar-section {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin: 1.2rem 0 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #eee;
    }

    /* Partner legend items */
    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 0.85rem;
    }
    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
        border: 1px solid rgba(0,0,0,0.15);
    }

    /* Map container — maximize height */
    iframe {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }

    /* Data source badges */
    .source-badge {
        display: inline-block;
        background: #f0f2f6;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        color: #555;
        margin: 2px;
    }

    /* Loading state */
    .loading-overlay {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 500px;
        color: #888;
        font-size: 1.1rem;
    }
    </style>
    """, unsafe_allow_html=True)
```

Refine and expand this CSS as you build. The goal is a clean, professional look — not raw Streamlit defaults. Test the visual output and iterate on the styling.

### 5.3 Branded Header

```python
def _render_header():
    project = get_project()
    st.markdown(f"""
    <div class="main-header">
        <h1>{project['name']}</h1>
        <p>{project['primary_org']} &middot; {project['secondary_org']} &middot; Davidson County, TN</p>
    </div>
    """, unsafe_allow_html=True)
```

### 5.4 Sidebar — Reorganized

Structure the sidebar into clear sections:

```python
def _render_sidebar() -> tuple[str, bool, list[str]]:
    with st.sidebar:
        # --- Geographic Level ---
        st.markdown('<div class="sidebar-section">Geographic Level</div>', unsafe_allow_html=True)
        granularities = get_granularities()
        granularity = st.radio(
            "Select geographic level",
            options=[g["id"] for g in granularities],
            format_func=lambda x: next(g["label"] for g in granularities if g["id"] == x),
            horizontal=True,
            label_visibility="collapsed",
        )

        # --- Data Layers ---
        st.markdown('<div class="sidebar-section">Data Layers</div>', unsafe_allow_html=True)
        all_layers = get_all_layer_configs()
        selected_layers = []
        for layer in all_layers:
            if st.checkbox(
                layer["display_name"],
                value=layer.get("default_visible", False),
                key=f"layer_{layer['column']}",
            ):
                selected_layers.append(layer["column"])

        # --- Partner Locations ---
        st.markdown('<div class="sidebar-section">Partner Locations</div>', unsafe_allow_html=True)
        show_partners = st.checkbox("Show NFP Partners", value=True)

        if show_partners:
            _render_partner_legend()

        # --- Data Sources ---
        st.markdown('<div class="sidebar-section">Data Sources</div>', unsafe_allow_html=True)
        _render_data_freshness()

    return granularity, show_partners, selected_layers
```

### 5.5 Partner Legend (Improved)

Replace the current inline HTML with cleaner styled legend:

```python
def _render_partner_legend():
    partner_cfg = get_partner_config()
    for type_key, type_info in partner_cfg["types"].items():
        st.markdown(
            f'<div class="legend-item">'
            f'<span class="legend-dot" style="background-color: {type_info["color"]};"></span>'
            f'{type_info["label"]}'
            f'</div>',
            unsafe_allow_html=True,
        )
```

### 5.6 Map Rendering with Loading State

```python
def _render_map(granularity: str, show_partners: bool, selected_layers: list[str]):
    with st.spinner("Building map..."):
        map_html = build_map_html(granularity, show_partners, selected_layers)

    st.components.v1.html(map_html, height=700, scrolling=False)
```

Using `st.components.v1.html` with the cached HTML string gives better performance than `st_folium` for pre-built maps. If `st_folium` provides needed interactivity (like click callbacks), use it instead — but for display-only maps, `components.html` avoids the `streamlit-folium` rendering overhead.

### 5.7 Data Sources Footer

```python
def _render_data_freshness():
    sources = [
        ("Census ACS", "American Community Survey 2020-2024 5-Year Estimates"),
        ("CDC PLACES", "CDC PLACES 2024 Model-Based Estimates"),
        ("Partners", "Nashville Food Project Partner Directory"),
    ]
    for name, desc in sources:
        st.markdown(f'<span class="source-badge">{name}</span> {desc}', unsafe_allow_html=True)
```

### 5.8 Fix Export Button

The current export button says "Download Map as PNG" but delivers HTML. Fix this:

```python
# Option A: Honest label
st.download_button(
    label="⬇ Download Map as HTML",
    data=map_html,
    file_name="nfp_food_insecurity_map.html",
    mime="text/html",
)
```

If actual PNG export is desired, investigate using `selenium` or `playwright` for headless screenshot of the Folium HTML, or add a `scripts/generate_static_maps.py` (see Phase 7).

---

## Phase 6: Security + Best Practice Fixes

All items from the AI recommendations report and comparison report for the dropbuild.

### 6.1 CRITICAL: Remove `.env` from Version Control

```bash
git rm --cached .env
```

Ensure `.env` is in `.gitignore`. The new branch must not contain the `.env` file.

### 6.2 Comprehensive `.gitignore`

Add missing patterns (flagged in security audit):
```
.env
*.pem
*.key
credentials*
*.parquet
*.geojson
data/geo/
data/choropleth/
data/points/
data/geocode_cache.csv
maps/
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
```

Keep `data/mock/` and `data/shapefiles/.gitkeep` tracked.

### 6.3 Production/Development Config Separation

Add to `src/config.py` (flagged as missing in security audit):
```python
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"
LOG_LEVEL = logging.WARNING if IS_PRODUCTION else logging.INFO
```

In production mode: suppress verbose error messages, use WARNING log level, disable mock data.

### 6.4 Fix Broad `except Exception` Blocks

The code quality analysis found 7 broad except blocks. Replace each with specific exceptions:
- `except (FileNotFoundError, pd.errors.ParserError)` for file loading
- `except DataLoadError` for data pipeline errors
- `except GeocodingError` for geocoding failures
- Always log with `logger.exception()` to capture full tracebacks

### 6.5 Tile Attribution

Add explicit tile attribution (flagged as missing):
```python
folium.Map(
    ...
    tiles="cartodbpositron",
    attr='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
)
```

### 6.6 Geometry Simplification

Add to data loading (flagged as missing optimization):
```python
gdf["geometry"] = gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)
```

### 6.7 Color Scale Accessibility

Make colormaps configurable per-layer in `project.yml` (not hardcoded). Use colorblind-friendly defaults:
- Sequential positive (income, population): `YlGnBu` or `viridis`
- Sequential negative (poverty, disease): `YlOrRd`
- Validate choices against [ColorBrewer](https://colorbrewer2.org/)

### 6.8 Structured Logging Everywhere

The dropbuild already uses `logging` in `src/geocoder.py` — extend to ALL modules:
```python
import logging
logger = logging.getLogger(__name__)
```

Configure root logger in `app.py`:
```python
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
```

### 6.9 Type Hints and Docstrings

- Maintain the current 28.8% type hint coverage and push toward 80%+
- Add `from __future__ import annotations` to all modules
- Add Google-style docstrings to all public functions and classes
- Target: every function in `src/`, `pipeline/`, and extracted `app.py` functions

### 6.10 Security Headers (Streamlit)

Streamlit doesn't expose response headers directly. Add a note in README that in production, a reverse proxy (nginx, Cloudflare) should set:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Content-Security-Policy`
- `Strict-Transport-Security`

If deploying behind nginx, provide a sample config snippet in the README.

### 6.11 Update `.env.example`

```
APP_ENV=development
USE_MOCK_DATA=false
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET_NAME=bdaic-public-transform
PROJECT_CONFIG=project.yml
```

---

## Phase 7: Optional Enhancements

These are lower priority but should be included if time allows.

### 7.1 Static PNG Export Script

Create `scripts/generate_static_maps.py` modeled after the BDAIC app's `app/map_builder/static_export.py`:
- 300 DPI PNG export via matplotlib + geopandas
- Iterate through configured export layers
- Overlay partner pins on static maps
- Add title, colorbar, attribution text
- Save to `maps/static/`

### 7.2 CI/CD

Create `.github/workflows/ci.yml`:
- Trigger on push and pull_request
- Python 3.11
- Install dependencies
- `USE_MOCK_DATA=true pytest tests/ -v`
- `flake8 src/ pipeline/ scripts/`

### 7.3 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.headless=true"]
```

---

## Phase 8: Testing

### 8.1 Update Existing Tests

All existing tests in `tests/` must be updated to work with the new architecture:
- Tests that import from `src/config.py` need to handle YAML-loaded values
- Tests that mock S3 CSV loading need to mock Parquet loading instead
- Integration tests should verify the full pipeline → map flow

### 8.2 New Tests

Add tests for new functionality:
- **test_config_loader.py**: YAML parsing, all accessor functions, missing config handling
- **test_pipeline.py**: Pipeline CLI, source loading, GEOID filtering, parquet output
- **test_partner_loader.py**: GeoJSON loading, mock mode fallback
- **test_granularity.py**: Both tract and zip granularity produce valid maps
- Update **test_layer_manager.py**: Verify `folium.Marker` (pins) instead of `CircleMarker` (dots), verify `FeatureGroup` names set correctly for LayerControl

### 8.3 Test with Real AWS

Since full AWS access is available, include at least one integration test that verifies:
- Pipeline can connect to S3 and discover files
- Parquet files are produced with expected columns
- Partner geocoding produces valid GeoJSON

---

## Phase 9: Cleanup + Documentation

### 9.1 Remove Obsolete Files

- `scripts/import_shapefiles.py` → replaced by `scripts/process_geographic_data.py`
- `spec.json` and `build-state.json` → Dropbuild build metadata, no longer needed
- `CLAUDE.md` → Dropbuild-specific build instructions, no longer applicable
- `data/shapefiles/` → replaced by `data/geo/`

### 9.2 Update `requirements.txt`

Remove Streamlit-specific packages that are no longer needed (if any), and add:
- `PyYAML` (for project.yml)
- `pyarrow` (for Parquet support)
- `s3fs` (for S3 file access, if not already present)
- `matplotlib` (for static PNG export, if Phase 7 is included)

Keep all pins as `==`. Run `pip freeze` to get exact versions.

### 9.3 Update `README.md`

Comprehensive documentation:
- Project overview and purpose
- Quick start: `pip install -r requirements.txt`, configure `.env`, run pipeline, run app
- Data pipeline usage (`python -m pipeline`)
- Configuration guide (`project.yml` sections)
- Adding new data layers (YAML-only changes)
- Mock data mode for local development
- Deployment notes (Streamlit Cloud, Docker, reverse proxy for security headers)
- Architecture overview

### 9.4 Update `ASSUMPTIONS.md`

Add new architectural decisions:
- YAML config adopted for extensibility (add layers without code changes)
- Pipeline produces Parquet files (columnar, compressed, fast reads)
- Geocoding happens in pipeline, not at app runtime
- Pins replace dots for partner markers (better UX and visual hierarchy)
- `st.cache_data` keyed by `(granularity, layers)` for performance
- `LayerControl` added for in-map layer toggling

### 9.5 Update `CONTRACT.md`

Document all module interfaces with updated function signatures, parameters, return types, and exceptions.

---

## Verification Checklist

### Pipeline Verification
- [ ] `python -m pipeline --step geo` produces `data/geo/tracts.geojson`, `zipcodes.geojson`, `county_boundary.geojson`
- [ ] `python -m pipeline --step census_acs` produces tract + zip parquet files in `data/choropleth/`
- [ ] `python -m pipeline --step health_lila` produces tract + zip parquet files in `data/choropleth/`
- [ ] `python -m pipeline --step partners` produces `data/points/partners.geojson`
- [ ] `python -m pipeline` runs all steps end-to-end

### App Verification
- [ ] `streamlit run app.py` starts without errors
- [ ] Branded header renders with project name and org names
- [ ] Granularity toggle switches between Census Tract and ZIP Code views
- [ ] All 6 choropleth layers (income, poverty, population, diabetes, hypertension, obesity) are available
- [ ] Checking/unchecking data layer checkboxes updates the map
- [ ] Partner locations appear as **pin markers** (not dots)
- [ ] Each partner type has a distinct colored pin
- [ ] Clicking a partner pin shows popup with name, type, address
- [ ] `LayerControl` appears on the map and toggles layers
- [ ] Legend displays colormaps for active layers
- [ ] Partner legend in sidebar shows all 8 types with colored indicators
- [ ] Map loads quickly on repeated interactions (cache working)
- [ ] Export button label matches actual output format
- [ ] Data sources section shows accurate vintage information

### Security Verification
- [ ] `.env` is NOT in the git repository
- [ ] `.gitignore` includes `*.pem`, `*.key`, `credentials*`, `*.parquet`, `*.geojson`
- [ ] No PII (partner addresses) in any Python source file
- [ ] No hardcoded `DEBUG = True` anywhere
- [ ] All dependencies pinned with `==`
- [ ] No bare `except:` or unnecessary `except Exception` blocks
- [ ] Tile attribution is explicit in the map
- [ ] `APP_ENV` / `IS_PRODUCTION` config separation works

### Quality Verification
- [ ] `pytest tests/ -v` — all tests pass
- [ ] `flake8 src/ pipeline/ scripts/` — no lint errors
- [ ] No `print()` statements in application code (only `logging`)
- [ ] Type hints on all public functions
- [ ] Docstrings on all public functions and classes
- [ ] `project.yml` is the single source of truth — no hardcoded layer definitions in Python
- [ ] Adding a new choropleth layer requires only a `project.yml` edit
- [ ] Mock data mode still works (`USE_MOCK_DATA=true streamlit run app.py`)

---

## Key Principles

1. **Read the BDAIC app for patterns.** Before implementing any pipeline or data component, read the corresponding file in `../bdaic-nfp-food-insecuirty-map/`. Understand its patterns, then adapt for Streamlit.

2. **Stay Streamlit.** This is NOT a Flask conversion. Keep Streamlit as the framework. Adapt BDAIC's data pipeline and configuration patterns, not its web framework.

3. **YAML is the single source of truth.** Layer definitions, partner types, colors, S3 paths — all in `project.yml`. Python code should read config, not define it.

4. **Pipeline before app.** Data processing happens in the pipeline CLI. The Streamlit app only reads pre-built Parquet and GeoJSON files. No runtime geocoding, no runtime CSV parsing from S3.

5. **Cache aggressively.** Use `@st.cache_data` on `build_map_html()`, `load_geodata()`, and `load_partners()`. The map HTML string should be cached by `(granularity, show_partners, selected_layers)`.

6. **Pins, not dots.** Partner markers must be `folium.Marker` with `folium.Icon` (or `BeautifyIcon`), not `CircleMarker`.

7. **Log, don't print.** Every module uses `logging.getLogger(__name__)`.

8. **Pin dependencies.** Every package uses `==`.

9. **No secrets in code.** Environment variables for credentials, S3 for partner data, `.gitignore` for everything sensitive.
