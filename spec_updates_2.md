# Spec Update 2: Nashville MSA Expansion + Multi-Page App + New Data Sources

## Overview

**Goal**: Expand the NFP Food Insecurity Mapping Tool from a Davidson County single-page Streamlit app to a Nashville MSA multi-page application with additional data layers (USDA LILA, Giving Matters partner data) and a professional multi-page structure (cover page, map, about the data).

**Baseline**: This spec assumes `spec_updates_1.md` is fully implemented. The current app has: YAML-driven configuration (`project.yml`), a data pipeline producing Parquet files, multi-granularity support (tract + zip), pin markers for partners, LayerControl, polished UI with branded header, and all security/best-practice fixes applied.

**Target Codebase**: `dropbuild-nfp-food-insecurity-map/` (the Streamlit application). The Flask reference app (`bdaic-nfp-food-insecuirty-map/`) is deprecated and should not be referenced.

**What This Spec Does NOT Cover** (deferred to future specs):
- Composite scoring / food insecurity index
- Analytical tabular view (expansion opportunity scoring, actionable recommendations)
- Feeding America "Map the Meal Gap" modeled data (pending investigation by Tommy Strickler)
- Public-facing use cases (transit overlay, grocery store mapping, neighborhood boundaries)
- AI conversational interface

---

## Current State (Baseline After spec_updates_1)

The Streamlit app is a **single-page application** scoped to **Davidson County only**:
- `project.yml` — YAML configuration with geography, data sources, partner types, map display settings
- `pipeline/` — CLI data pipeline producing Parquet files for Census ACS and CDC PLACES data at tract and zip granularity, plus partner GeoJSON
- `src/` — Modular architecture: `config_loader.py`, `data_loader.py`, `partner_loader.py`, `layer_manager.py`, `map_builder.py`
- `app.py` — Single Streamlit page with sidebar controls, branded header, map rendering, partner legend, data sources footer
- Geography: Davidson County only (`state_fips: "47"`, `county_fips: "037"`)
- Data sources: Census ACS (income, poverty, population), CDC PLACES (diabetes, hypertension, obesity), NFP partner locations
- Granularity: Census tracts and ZIP codes within Davidson County

---

## Target State (After spec_updates_2)

A **multi-page Streamlit application** covering the **Nashville MSA (14-county OMB definition)** with:
- **Home page** — Cover/landing page with project overview, NFP branding, and navigation
- **Map page** — Expanded interactive map covering all MSA counties with existing + new data layers
- **About the Data page** — Methodology descriptions, data source documentation, vintage dates, limitations
- **USDA LILA data** — Low Income, Low Access indicators as new choropleth layer(s)
- **Giving Matters integration pattern** — Pipeline step ready to ingest nonprofit/partner point data from CFMT (schema TBD, graceful skip when data not yet available)
- **MSA-wide geography** — TIGER/Line boundaries for all 14 Nashville MSA counties at tract and zip granularity

---

## Phase 1: Geographic Expansion to Nashville MSA

### 1.1 Update `project.yml` Geography Configuration

Replace the single-county configuration with MSA-level geography:

```yaml
geography:
  state_fips: "47"
  msa_name: "Nashville-Davidson-Murfreesboro-Franklin"
  msa_counties:
    - fips: "015"
      name: "Cannon County"
    - fips: "021"
      name: "Cheatham County"
    - fips: "037"
      name: "Davidson County"
    - fips: "043"
      name: "Dickson County"
    - fips: "081"
      name: "Hickman County"
    - fips: "111"
      name: "Macon County"
    - fips: "119"
      name: "Maury County"
    - fips: "147"
      name: "Robertson County"
    - fips: "149"
      name: "Rutherford County"
    - fips: "159"
      name: "Smith County"
    - fips: "165"
      name: "Sumner County"
    - fips: "169"
      name: "Trousdale County"
    - fips: "187"
      name: "Williamson County"
    - fips: "189"
      name: "Wilson County"
  map_center: [36.05, -86.60]
  default_zoom: 9
  tiger_year: 2023
```

**Key changes:**
- Remove single `county_fips` field; replace with `msa_counties` array
- Adjust `map_center` to center on the MSA (slightly south-southwest of downtown Nashville to balance the 14-county extent)
- Reduce `default_zoom` from 11 to 9 to show the full MSA on initial load
- Keep `state_fips: "47"` (all counties are in Tennessee)

### 1.2 Update `scripts/process_geographic_data.py`

The current script downloads TIGER/Line data for a single county. Update to iterate over all MSA counties:

**Tracts:**
1. Download the Tennessee state-level tract shapefile (TIGER/Line `tl_2023_47_tract`)
2. Filter to tracts where the county FIPS portion of GEOID matches any county in `msa_counties`
3. Save to `data/geo/tracts.geojson`

**ZCTAs:**
1. Download the national ZCTA shapefile (as before)
2. Clip to the MSA boundary (union of all MSA county boundaries)
3. Save to `data/geo/zipcodes.geojson`

**County boundaries:**
1. Download the Tennessee county boundary shapefile
2. Filter to the 14 MSA counties
3. Save individual boundaries and a combined MSA boundary:
   - `data/geo/county_boundaries.geojson` — all 14 counties as separate features (for rendering county boundary lines on the map)
   - `data/geo/msa_boundary.geojson` — dissolved union of all 14 counties (for clipping ZCTAs)

**Updated `data/geo/` structure:**
```
data/geo/
├── tracts.geojson            # All census tracts in MSA (was: Davidson only)
├── zipcodes.geojson          # All ZCTAs clipped to MSA (was: Davidson only)
├── county_boundaries.geojson # 14 individual county boundaries (NEW)
└── msa_boundary.geojson      # Dissolved MSA outline (NEW)
```

### 1.3 Update `pipeline/load_source.py`

The current pipeline filters data by single county FIPS. Update to filter by a list of county FIPS codes:

- Read the `msa_counties` list from `project.yml`
- Build a set of full state+county FIPS prefixes: `{"47015", "47021", "47037", ...}`
- When filtering Census ACS and CDC PLACES data, use `GEOID.str[:5].isin(county_fips_set)` instead of `GEOID.str.startswith(state_fips + county_fips)`
- This change should be backward-compatible — if `msa_counties` is defined, use it; if only `county_fips` is present (legacy), fall back to single-county filtering

### 1.4 Update Map Display for MSA

**Add county boundary layer:**
Add a new non-data overlay layer that renders county boundaries on the map. This helps users orient themselves across the 14-county region:

```python
def build_county_boundaries_layer(county_gdf: gpd.GeoDataFrame) -> folium.FeatureGroup:
    """Render MSA county boundaries as a reference overlay."""
    fg = folium.FeatureGroup(name="County Boundaries", show=True)
    folium.GeoJson(
        county_gdf,
        style_function=lambda x: {
            "fillColor": "transparent",
            "color": "#333333",
            "weight": 2,
            "dashArray": "5,5",
        },
        tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["County:"]),
    ).add_to(fg)
    return fg
```

This layer should be on by default and toggleable via LayerControl. It renders as dashed lines so it doesn't visually compete with tract-level choropleth shading.

**Update map bounds:**
On initial load, fit the map to the MSA boundary extent rather than using a fixed center+zoom. Use `m.fit_bounds()` with the bounding box of the MSA boundary GeoJSON. Keep `map_center` and `default_zoom` as fallbacks.

### 1.5 Update Tract/ZIP Count Expectations

Davidson County has ~170 census tracts. The Nashville MSA has approximately 450-500 tracts. Verify that:
- Geometry simplification (from spec_updates_1) keeps the GeoJSON payload manageable at MSA scale
- Tooltip rendering doesn't slow down with 3x more features
- The choropleth color scale bins work across the broader data range

Add a `simplify_tolerance` config to `project.yml` under `map_display`:
```yaml
map_display:
  simplify_tolerance: 0.001  # Adjustable; increase if MSA-scale rendering is slow
```

---

## Phase 2: USDA LILA Data Integration

### 2.1 Data Source Description

The USDA Economic Research Service publishes the **Food Access Research Atlas** data, which identifies census tracts that are Low Income and/or Low Access (LILA) to supermarkets. The dataset is tract-level and includes multiple access distance thresholds.

**Source**: https://www.ers.usda.gov/data-products/food-access-research-atlas/
**Format**: CSV download (or API)
**Geography**: Census tract level, national
**Key fields to include**:

| Field | Display Name | Description |
|-------|-------------|-------------|
| `LILATracts_1And10` | "Low Income, Low Access (1 & 10 mi)" | Flag: tract is both low income and low access at 1 mile (urban) / 10 mile (rural) |
| `LILATracts_halfAnd10` | "Low Income, Low Access (0.5 & 10 mi)" | Flag: tract is both low income and low access at 0.5 mile (urban) / 10 mile (rural) |
| `LILATracts_1And20` | "Low Income, Low Access (1 & 20 mi)" | Flag: tract is both low income and low access at 1 mile (urban) / 20 mile (rural) |
| `lapop1` | "Low Access Population (1 mi)" | Count of people in tract beyond 1 mile from supermarket |
| `lalowi1` | "Low Access, Low Income Pop (1 mi)" | Count of low-income people beyond 1 mile from supermarket |
| `PovertyRate` | "Poverty Rate (LILA)" | Tract poverty rate from the LILA dataset |
| `MedianFamilyIncome` | "Median Family Income (LILA)" | Tract median family income |

**Critical note on vintage and geography**: The current LILA data is based on 2019 ACS data and uses **2010 Census tract boundaries** — NOT 2020 boundaries. Our map uses 2020 TIGER/Line tract boundaries (which align with ACS 2020-2024 and CDC PLACES data). The 2010 and 2020 tract boundaries do not align 1:1 — tracts were split, merged, and renumbered between decades. This means **LILA 2010 GEOIDs cannot be directly joined to our 2020 tract GeoJSON**. A crosswalk conversion step is required (see Section 2.3).

This was discussed in the 3/30 meeting — despite the vintage issue, LILA remains the standard reference for food access research. The "About the Data" page must clearly document this conversion methodology and its limitations.

### 2.2 Add LILA to `project.yml`

```yaml
data_sources:
  # ... existing census_acs and health_lila entries ...

  usda_lila:
    source_type: s3
    s3_bucket: bdaic-public-transform
    s3_prefix:
      tract: "nfp-mapping/usda/lila/tract/"
    source_key: "nfp-mapping/usda/lila/source/food_access_research_atlas.csv"
    crosswalk_key: "nfp-mapping/usda/lila/crosswalk/tract_2010_to_2020_tn.csv"
    output_prefix: usda_lila
    source_geoid_column: CensusTract       # 2010 tract GEOID in source data
    source_geoid_vintage: "2010"            # Signals that crosswalk conversion is needed
    target_geoid_vintage: "2020"            # Target boundary vintage
    note: "LILA data uses 2010 Census tract boundaries. Converted to 2020 tracts via Census Bureau relationship file. Tract-level only (no ZIP aggregation)."
    variables:
      - column: LILATracts_1And10
        display_name: "LILA Designation (1 & 10 mi)"
        colormap: RdYlGn_r
        legend_name: "Low Income + Low Access"
        format_str: "{}"
        tooltip_alias: "LILA"
        default_visible: false
        layer_type: categorical
        categories:
          0: "Not LILA"
          1: "LILA Tract"
      - column: lapop1
        display_name: "Low Access Population (1 mi)"
        colormap: YlOrRd
        legend_name: "Population Beyond 1 mi from Supermarket"
        format_str: "{:,.0f}"
        tooltip_alias: "Low Access Pop"
        default_visible: false
      - column: lalowi1
        display_name: "Low Income, Low Access Population (1 mi)"
        colormap: YlOrRd
        legend_name: "Low Income Pop Beyond 1 mi"
        format_str: "{:,.0f}"
        tooltip_alias: "LI Low Access Pop"
        default_visible: false
```

### 2.3 LILA Pipeline Step — Including 2010→2020 Tract Crosswalk

Add a pipeline step: `python -m pipeline --step usda_lila`

**The core challenge**: LILA data uses 2010 Census tract GEOIDs. Our map renders 2020 Census tract boundaries. These do not align 1:1 — between 2010 and 2020, tracts were split, merged, had boundary adjustments, and were renumbered. A crosswalk conversion is required to map LILA values onto 2020 tract geometries.

**Crosswalk source**: The U.S. Census Bureau publishes an official **2010 Census Tract to 2020 Census Tract Relationship File** that documents every intersection between 2010 and 2020 tract boundaries. Each record represents one relationship where a 2010 tract overlaps a 2020 tract, with area and population proportions for weighting.

- **File**: `tab20_tract20_tract10_natl.txt` (national, pipe-delimited)
- **Source**: https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html (under "2020 Census Tract to 2010 Census Tract Relationship File")
- **Key fields**:
  - `GEOID_TRACT_20` — 2020 tract GEOID (11-char)
  - `GEOID_TRACT_10` — 2010 tract GEOID (11-char)
  - `AREALAND_PART` — land area of the intersection (square meters)
  - `AREALAND_TRACT_20` — total land area of the 2020 tract
  - `AREALAND_TRACT_10` — total land area of the 2010 tract
  - `OPP_TRACT_20` — proportion of 2020 tract area in this intersection
  - `OPP_TRACT_10` — proportion of 2010 tract area in this intersection

**Alternative crosswalk source** (if higher-quality weights are needed): IPUMS NHGIS publishes geographic crosswalks (https://www.nhgis.org/geographic-crosswalks) with population-based interpolation weights derived from Census block-level data. These are generally more accurate than area-based weights for population-related variables like LILA counts. If the Census Bureau relationship file proves insufficient, NHGIS crosswalks are the recommended alternative.

**Processing logic:**

1. **Load LILA CSV** from S3 (pre-uploaded by BDAIC)
2. **Load the crosswalk file** from S3 (pre-uploaded; see Section 2.4)
3. **Normalize GEOIDs**: Zero-fill both LILA `CensusTract` (2010 GEOID) and crosswalk `GEOID_TRACT_10` to 11 characters
4. **Filter crosswalk** to MSA county FIPS prefixes (using the 2020 GEOID's first 5 characters)
5. **Join LILA data to crosswalk** on 2010 GEOID (`CensusTract` = `GEOID_TRACT_10`)
6. **Apply conversion method by variable type**:

   **For binary flag variables** (`LILATracts_1And10`, `LILATracts_halfAnd10`, `LILATracts_1And20`):
   - A 2020 tract inherits the LILA flag if **any** of its contributing 2010 tracts had the flag set to 1
   - Rationale: If any part of a 2020 tract was designated LILA under 2010 boundaries, the 2020 tract should be flagged for investigation. This is a conservative (inclusive) approach appropriate for a strategic planning tool.
   - Implementation: Group by `GEOID_TRACT_20`, take `max()` of the flag column

   **For population count variables** (`lapop1`, `lalowi1`):
   - Use area-weighted apportionment: multiply each 2010 tract's count by `OPP_TRACT_10` (the proportion of the 2010 tract's area that falls in this 2020 tract), then sum across all contributing 2010 tracts
   - Implementation: `lila_value * OPP_TRACT_10`, then `groupby('GEOID_TRACT_20').sum()`
   - Round to integers after summation (population counts should not be fractional)
   - If NHGIS population-weighted crosswalks are used instead, use the population weight in place of `OPP_TRACT_10`

   **For rate/percentage variables** (`PovertyRate`, `MedianFamilyIncome`):
   - Use area-weighted average: multiply each 2010 tract's rate by `OPP_TRACT_10`, sum, then divide by the sum of weights for that 2020 tract
   - Implementation: weighted mean via `(rate * OPP_TRACT_10).sum() / OPP_TRACT_10.sum()` grouped by `GEOID_TRACT_20`
   - This produces an approximate rate for the 2020 tract geometry

7. **Output** the converted data keyed by 2020 GEOID to `data/choropleth/usda_lila_tract_data.parquet`

**Handling edge cases:**
- **2020 tracts with no 2010 match**: Some new 2020 tracts may not have a corresponding 2010 tract in the LILA data (e.g., tracts created from non-tract areas). Set LILA values to NaN for these tracts. Log them.
- **2010 tracts that split into many 2020 tracts**: The area-weighting handles this naturally — each 2020 fragment receives a proportional share.
- **2010 tracts that merged into one 2020 tract**: The aggregation (max for flags, weighted sum for counts, weighted mean for rates) handles this naturally.
- **Very small intersection slivers**: Filter out crosswalk rows where `OPP_TRACT_10 < 0.01` (less than 1% of the 2010 tract's area) to avoid noise from tiny boundary overlaps.

**Important**: LILA data is only available at the tract level. When the user selects ZIP code granularity, LILA layers should be disabled in the sidebar with a tooltip: "LILA data is available at census tract level only. Switch to Census Tracts to view."

### 2.4 Upload LILA Source Data and Crosswalk File to S3

Before the pipeline can run, two files need to be downloaded and uploaded to S3:

**File 1: LILA data**
```
scripts/download_lila_data.py
```
This script:
1. Downloads the Food Access Research Atlas CSV from the USDA ERS website
2. Validates expected columns are present
3. Uploads to S3 at `nfp-mapping/usda/lila/source/food_access_research_atlas.csv`
4. Logs the source URL and download date for provenance

**File 2: Census tract crosswalk**
```
scripts/download_tract_crosswalk.py
```
This script:
1. Downloads the 2010-to-2020 Census Tract Relationship File from the Census Bureau
2. Parses the pipe-delimited format
3. Filters to Tennessee (state FIPS 47) to reduce file size
4. Uploads to S3 at `nfp-mapping/usda/lila/crosswalk/tract_2010_to_2020_tn.csv`
5. Logs the source URL and download date for provenance

**Updated S3 structure for LILA:**
```
nfp-mapping/usda/lila/
├── source/
│   └── food_access_research_atlas.csv   # Raw LILA data (2010 GEOIDs)
├── crosswalk/
│   └── tract_2010_to_2020_tn.csv        # Census relationship file (TN only)
└── tract/
    └── (pipeline output parquet goes here, keyed by 2020 GEOIDs)
```

### 2.5 Handle Categorical vs Continuous Layers

The LILA designation fields (`LILATracts_1And10`, etc.) are binary flags (0/1), not continuous values. The current choropleth rendering assumes continuous data with a linear color scale. Add support for categorical layers:

**In `layer_manager.py`:**
- Check `layer_type` in the layer config (default: `"continuous"`)
- For `categorical` layers: use a discrete color map with one color per category value
- For the LILA binary flag: render as two-tone — e.g., light gray for "Not LILA" and dark red for "LILA Tract"
- The legend should show discrete swatches with category labels, not a gradient

**In `config_loader.py`:**
- Add `get_layer_type(layer_config)` that returns `"continuous"` or `"categorical"`
- For categorical layers, expose the `categories` dict from the config

---

## Phase 3: Giving Matters Integration Pattern

### 3.1 Design Decision

The Giving Matters data from CFMT has not yet been received. CJ Sentell is initiating the connection (target: 2026-04-06). This phase defines the integration pattern so the pipeline is ready to activate when data arrives.

### 3.2 Add Giving Matters Config to `project.yml`

```yaml
data_sources:
  # ... existing entries ...

  giving_matters:
    source_type: s3
    s3_bucket: bdaic-public-transform
    s3_key: "nfp-mapping/partners/giving_matters.csv"
    output_prefix: giving_matters
    enabled: false  # Set to true once data is uploaded to S3
    note: "Giving Matters nonprofit data from CFMT. Schema TBD — enable after data receipt and column mapping."
    # Column mapping will be added here once the schema is known:
    # required_columns:
    #   name_column: TBD
    #   address_column: TBD
    #   category_column: TBD
    geocode_cache_key: "nfp-mapping/partners/giving_matters_geocode_cache.csv"
    point_layer_name: "Community Partners (Giving Matters)"
    marker_style: "circle"  # Use circle markers to distinguish from NFP partner pins
    default_color: "#17BECF"
```

### 3.3 Create `pipeline/process_giving_matters.py`

A pipeline step that gracefully handles the data not yet being present:

```
python -m pipeline --step giving_matters
```

**Logic:**
1. Check `enabled` flag in config. If `false`, log "Giving Matters integration is disabled — skipping" and exit cleanly.
2. If enabled, attempt to load CSV from S3 key.
3. If S3 key doesn't exist, log a warning and exit cleanly (don't crash the pipeline).
4. If data is present:
   a. Validate required columns (from config `required_columns` mapping)
   b. Geocode addresses using the same Nominatim + cache pattern as NFP partners
   c. Validate coordinates fall within MSA bounding box
   d. Output to `data/points/giving_matters.geojson`
5. Log summary: "Processed X/Y Giving Matters locations (Z failed geocoding)"

### 3.4 Render Giving Matters Points on Map

When the Giving Matters GeoJSON exists in `data/points/`:
- Load it alongside NFP partner data
- Render as a separate, toggleable FeatureGroup in LayerControl
- Use **circle markers** (not pin markers) to visually distinguish from NFP partner pins
- Color: `#17BECF` (teal) by default, unless category-based coloring is configured after schema is known
- Popup: display available fields (name, address, category if present)

When the GeoJSON doesn't exist (data not yet received):
- The layer simply doesn't appear in the sidebar or on the map
- No error, no placeholder — it's as if the feature doesn't exist yet

### 3.5 Sidebar Display

Add a "Community Partners" section in the sidebar (below the existing "Partner Locations" section) that only renders when Giving Matters data is available:

```python
if giving_matters_available:
    st.markdown('<div class="sidebar-section">Community Partners</div>', unsafe_allow_html=True)
    show_giving_matters = st.checkbox("Show Giving Matters Partners", value=False)
    if show_giving_matters:
        st.caption(f"{giving_matters_count} organizations from CFMT Giving Matters database")
```

---

## Phase 4: Multi-Page Streamlit App Structure

### 4.1 Convert to Multi-Page App

Streamlit's multi-page app structure uses a `pages/` directory. Convert the current single-page app:

**New directory structure:**
```
dropbuild-nfp-food-insecurity-map/
├── app.py                          # Entry point — configures page, renders Home page
├── pages/
│   ├── 1_Map.py                    # Map page (current app.py map logic moves here)
│   └── 2_About_the_Data.py         # Data methodology and source documentation
├── src/                            # Unchanged from spec_updates_1
├── pipeline/                       # Unchanged from spec_updates_1
├── ...
```

Streamlit uses the filename (minus the number prefix) as the page label in the sidebar navigation. The numbering controls display order.

### 4.2 Home Page (`app.py`)

The entry point becomes the cover/landing page. It should convey:

**Content:**
- **Project title**: "Nashville Food Insecurity Mapping Tool" (large, branded)
- **Subtitle**: "A strategic planning tool for the Nashville Food Project"
- **Brief description** (2-3 sentences): What the tool does, who it's for, why it exists. Written for an internal NFP audience — assumes familiarity with NFP's mission but not with the data.
- **Quick navigation cards**: Visual cards/buttons linking to the Map page and About the Data page, with 1-line descriptions of each
- **Key stats summary**: Dynamic stats pulled from the loaded data — e.g., "Covering 14 counties · 487 census tracts · 6 data indicators · 28 NFP partner locations"
- **Logos/branding**: Nashville Food Project logo (if available as an asset) and BDAIC logo. If logos are not available as files, use styled text with organization names.
- **Data freshness**: "Data last updated: [date of most recent pipeline run]"

**Design:**
- Clean, centered layout using `st.columns` for card alignment
- Same color scheme as the branded header from spec_updates_1 (green gradient: `#2E7D32` to `#1B5E20`)
- No sidebar controls on this page — the sidebar should show only page navigation
- Professional but not corporate — this is an internal tool, not a public website

**Implementation:**
```python
st.set_page_config(
    page_title="NFP Food Insecurity Map",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)
```

### 4.3 Map Page (`pages/1_Map.py`)

This is the existing map functionality relocated from `app.py`. The logic is identical to the current implementation with these additions:

- All sidebar controls (granularity toggle, layer checkboxes, partner toggle, legends) remain on this page
- Add county boundaries layer (from Phase 1.4)
- Add LILA layers (from Phase 2)
- Add Giving Matters layer when available (from Phase 3)
- The branded header moves to the Home page; the Map page gets a simpler header: just the page title and a breadcrumb-style subtitle ("Nashville MSA · Census Tract View" or "Nashville MSA · ZIP Code View" depending on selection)

### 4.4 About the Data Page (`pages/2_About_the_Data.py`)

A reference page documenting all data sources, methodology, and limitations.

**Content structure:**

1. **Overview**: Brief explanation of what data the tool uses and why
2. **Data Sources** (one section per source):
   - **Census ACS (American Community Survey)**
     - What it measures: household income, poverty rate, population
     - Vintage: 2020-2024 5-Year Estimates
     - Geography: Census tract and ZIP code levels
     - Source: U.S. Census Bureau via data.census.gov
     - Update frequency: Annual (5-year rolling estimates)
   - **CDC PLACES**
     - What it measures: health outcomes (diabetes, hypertension, obesity prevalence)
     - Vintage: 2024 model-based estimates
     - Geography: Census tract and ZIP code levels
     - Source: CDC PLACES (places.cdc.gov)
     - Methodology note: Model-based small area estimates, not direct survey data
   - **USDA Food Access Research Atlas (LILA)**
     - What it measures: Low Income, Low Access to supermarkets
     - Vintage: Based on 2019 ACS data and **2010 Census tract boundaries**
     - Geography: Census tract only (not available at ZIP level)
     - Source: USDA Economic Research Service
     - **Boundary conversion note**: The original LILA data uses 2010 Census tract boundaries, which differ from the 2020 boundaries used by this tool's map. BDAIC converted LILA estimates from 2010 to 2020 tract boundaries using the U.S. Census Bureau's official 2010-to-2020 Census Tract Relationship File. Binary LILA designation flags use a conservative approach: a 2020 tract is flagged as LILA if any contributing 2010 tract was designated LILA. Population counts use area-weighted apportionment. Rates use area-weighted averages. This conversion introduces approximation — values should be interpreted as estimates, not exact figures.
     - **Why this matters**: Census tracts are redrawn each decade. Between 2010 and 2020, some tracts were split, merged, or had boundary adjustments. The crosswalk accounts for these changes, but users should be aware that LILA indicators are modeled approximations on 2020 geography, not direct measurements.
   - **NFP Partner Locations**
     - What it shows: Geocoded locations of Nashville Food Project partner organizations
     - Categories: 8 partner types (school/summer, medical/health, etc.)
     - Source: Nashville Food Project partner directory
     - Update process: Partners are geocoded via Nominatim; cached in S3
   - **Giving Matters** (when available)
     - What it shows: Nonprofit and community organization locations from CFMT
     - Source: Community Foundation of Middle Tennessee
     - Status: Integration pending — data not yet received
3. **Geographic Coverage**
   - Nashville MSA (14-county OMB definition)
   - List all 14 counties
   - Note: Some data sources may not cover all tracts (e.g., LILA may have missing values for some tracts)
4. **Limitations and Caveats**
   - Data vintage varies across sources (2019-2024)
   - LILA uses older census tract boundaries than other sources
   - Geocoding accuracy depends on address quality (some partner locations may be approximate)
   - Correlation between indicators does not imply causation
   - The tool is for strategic planning, not granular individual-level assessment
5. **Technical Details**
   - Data pipeline: Python-based ETL producing Parquet files
   - Map rendering: Folium (Leaflet.js) via Streamlit
   - Tile layer: CartoDB Positron
   - Contact: BDAIC team (email or link)

**Design:**
- Use `st.expander` for each data source section (collapsed by default, expandable)
- Clean typography — this is a reference document, not a dashboard
- Include a "last updated" timestamp for the pipeline run

---

## Phase 5: Pipeline and Config Updates

### 5.1 Update Pipeline CLI

Add the new pipeline step:
```
python -m pipeline --step usda_lila       # Process USDA LILA data
python -m pipeline --step giving_matters  # Process Giving Matters data (graceful skip if not available)
```

Update the full pipeline run (`python -m pipeline`) to include both new steps.

### 5.2 Update Mock Data Generation

Update `scripts/generate_mock_data.py` to produce mock data for the expanded geography:
- Generate mock tract data for ~500 tracts (MSA scale) instead of ~170 (Davidson only)
- Generate mock LILA data with binary flags and population counts
- Generate a small mock Giving Matters CSV with 10-15 fake nonprofit locations across the MSA
- Mock data must use realistic GEOID values for MSA counties

### 5.3 Update S3 Data Paths

Ensure the S3 bucket structure accommodates MSA-wide data:
```
bdaic-public-transform/
└── nfp-mapping/
    ├── census/acs/
    │   ├── tract/          # Now contains MSA-wide data, not just Davidson
    │   └── zcta/           # Now contains MSA-wide data
    ├── health/cdc_places/
    │   ├── tract/          # MSA-wide
    │   └── zcta/           # MSA-wide
    ├── usda/lila/
    │   └── tract/          # NEW: LILA data (tract only)
    ├── partners/
    │   ├── nfp_partners.csv
    │   ├── geocode_cache.csv
    │   ├── giving_matters.csv           # NEW: when available
    │   └── giving_matters_geocode_cache.csv  # NEW: when available
    └── geo/                # Optional: pre-processed boundaries
```

### 5.4 Update `data/` Directory Structure

```
data/
├── geo/
│   ├── tracts.geojson              # MSA-wide tracts
│   ├── zipcodes.geojson            # MSA-wide ZCTAs
│   ├── county_boundaries.geojson   # NEW: 14 individual county polygons
│   └── msa_boundary.geojson        # NEW: dissolved MSA outline
├── choropleth/
│   ├── acs_tract_data.parquet      # MSA-wide
│   ├── acs_zipcode_data.parquet    # MSA-wide
│   ├── health_lila_tract_data.parquet  # MSA-wide
│   ├── health_lila_zipcode_data.parquet  # MSA-wide
│   └── usda_lila_tract_data.parquet    # NEW: LILA (tract only)
├── points/
│   ├── partners.geojson            # NFP partners
│   └── giving_matters.geojson      # NEW: when available
├── mock/                           # Updated mock data for MSA scale
└── geocode_cache.csv
```

---

## Phase 6: Testing

### 6.1 Update Existing Tests

All tests that reference Davidson County FIPS (`"47037"`) need to be updated to handle MSA-wide filtering. Specifically:
- Tests in `test_pipeline.py` that verify GEOID filtering
- Tests in `test_data_loader.py` that check tract counts
- Integration tests that verify end-to-end pipeline → map flow

### 6.2 New Tests

| Test | What It Verifies |
|------|-----------------|
| `test_msa_geography.py` | All 14 county FIPS codes are in `project.yml`; TIGER/Line download produces GeoJSON with features from all 14 counties; county boundary GeoJSON has exactly 14 features |
| `test_lila_pipeline.py` | LILA pipeline step loads crosswalk and converts 2010→2020 GEOIDs; output Parquet uses 2020 GEOIDs that match our tract GeoJSON; binary flags use max() aggregation; population counts use area-weighted apportionment and are integers; rate variables use area-weighted means; small intersection slivers are filtered; tracts with no 2010 match have NaN values |
| `test_categorical_layer.py` | Categorical choropleth renders discrete colors (not gradient); legend shows category labels; binary LILA layer renders correctly |
| `test_giving_matters_skip.py` | When `enabled: false`, pipeline step exits cleanly with no error; when S3 key doesn't exist, pipeline logs warning and exits cleanly; when data is present, pipeline produces valid GeoJSON |
| `test_multipage.py` | All three pages load without error; Home page renders key stats; Map page renders map; About the Data page renders all sections |
| `test_county_boundaries.py` | County boundary layer renders as dashed lines; layer appears in LayerControl; toggling works |

### 6.3 Performance Testing

With MSA-scale data (~500 tracts vs ~170):
- Verify initial map load is still under 8 seconds (NFR-01 from original spec)
- If performance degrades, increase `simplify_tolerance` in config
- Verify LayerControl toggle speed is still under 3 seconds (NFR-02)

---

## Phase 7: Cleanup and Documentation

### 7.1 Update `README.md`

- Update geographic scope description (Nashville MSA, not Davidson County)
- Document the multi-page app structure
- Add LILA data source to the data sources section
- Document the Giving Matters integration pattern (how to enable when data arrives)
- Update the quick start to mention the new pipeline steps

### 7.2 Update `ASSUMPTIONS.md`

Add entries for:
- Nashville MSA uses the OMB 14-county definition (list the counties)
- LILA data vintage (2019 ACS / 2020 Census tracts) differs from other data vintages
- Giving Matters integration is designed to activate without code changes — only config + data upload needed
- County boundary layer uses dashed lines to avoid visual competition with choropleth
- LILA is tract-only; layers are disabled at ZIP granularity

### 7.3 Remove Flask App References

Remove any remaining references to `bdaic-nfp-food-insecuirty-map/` in:
- README.md
- Comments in source code
- `project.yml` (if any cross-references exist)
- This spec series going forward

---

## Verification Checklist

### Geographic Expansion
- [ ] `project.yml` lists all 14 Nashville MSA counties with correct FIPS codes
- [ ] `scripts/process_geographic_data.py` downloads and filters TIGER/Line for all 14 counties
- [ ] `data/geo/tracts.geojson` contains tracts from all 14 counties
- [ ] `data/geo/county_boundaries.geojson` has exactly 14 features
- [ ] `data/geo/msa_boundary.geojson` is a single dissolved polygon
- [ ] Census ACS pipeline produces MSA-wide Parquet files
- [ ] CDC PLACES pipeline produces MSA-wide Parquet files
- [ ] Map initial view shows all 14 counties without scrolling
- [ ] County boundary dashed lines render correctly and are toggleable

### LILA Data
- [ ] `scripts/download_lila_data.py` downloads LILA CSV and uploads to S3
- [ ] `scripts/download_tract_crosswalk.py` downloads Census relationship file and uploads to S3
- [ ] LILA pipeline step loads crosswalk and converts 2010 GEOIDs to 2020 GEOIDs
- [ ] Binary LILA flags use max() aggregation (conservative: any contributing 2010 tract flagged → 2020 tract flagged)
- [ ] Population counts use area-weighted apportionment and round to integers
- [ ] Rate variables use area-weighted averages
- [ ] Tiny intersection slivers (< 1% area) are filtered out of crosswalk
- [ ] 2020 tracts with no 2010 LILA match have NaN values (not zero)
- [ ] LILA pipeline step produces `data/choropleth/usda_lila_tract_data.parquet` keyed by 2020 GEOID
- [ ] LILA designation layer renders as categorical (two-tone, not gradient)
- [ ] LILA population layers render as continuous choropleth
- [ ] LILA layers are disabled with tooltip when ZIP granularity is selected
- [ ] LILA data appears in sidebar layer checkboxes
- [ ] About the Data page documents the 2010→2020 crosswalk methodology and its limitations

### Giving Matters
- [ ] Pipeline step exits cleanly when `enabled: false`
- [ ] Pipeline step exits cleanly when S3 key doesn't exist
- [ ] No errors or UI artifacts when Giving Matters data is not present
- [ ] (Future) When data is present: circle markers render, popup works, legend appears

### Multi-Page App
- [ ] Home page renders with project overview and navigation cards
- [ ] Home page shows dynamic key stats (county count, tract count, etc.)
- [ ] Map page has all existing functionality plus new layers
- [ ] About the Data page documents all data sources with vintage dates
- [ ] Sidebar navigation shows all three pages
- [ ] Page transitions are smooth (no full-app reload)

### Pipeline
- [ ] `python -m pipeline` runs all steps including new ones
- [ ] `python -m pipeline --step usda_lila` works independently
- [ ] `python -m pipeline --step giving_matters` works independently (graceful skip)
- [ ] Mock data generation produces MSA-scale data

---

## Build Sequence

Execute phases in order. Each phase should be independently testable before proceeding.

| Phase | Description | Depends On | Testable Output |
|-------|-------------|------------|-----------------|
| 1 | Geographic expansion to MSA | Baseline (spec_updates_1) | Pipeline produces MSA-wide data; map shows 14 counties |
| 2 | USDA LILA integration | Phase 1 (MSA geography) | LILA layers appear in sidebar; categorical rendering works |
| 3 | Giving Matters integration pattern | Phase 1 (MSA geography) | Pipeline step runs cleanly when disabled; no UI artifacts |
| 4 | Multi-page app conversion | Phases 1-3 | All three pages load; navigation works; existing map functionality preserved |
| 5 | Pipeline and config updates | Phases 1-3 | All pipeline steps work; mock data updated |
| 6 | Testing | Phases 1-5 | All tests pass |
| 7 | Cleanup and documentation | Phases 1-6 | README, ASSUMPTIONS updated; no Flask references |

---

## Spec Metadata

```yaml
# Machine-readable metadata — do not remove
spec_id: nfp_food_insecurity_mapping_tool_updates_2
project_id: nashville_food_project__food_insecurity_mapping_tool
spec_type: delta
baseline_spec: spec_updates_1.md
version: 1
status: draft
date: 2026-03-31
author: BDAIC Spec Architect (AI-assisted)
reviewer: Tommy Strickler
deliverable_types:
  - web_application
  - dataset
priority_requirements: 12
total_phases: 7
estimated_build_time: 2-3 days (AI agent build)
open_questions:
  - Giving Matters data schema (blocked on CFMT data receipt)
  - Feeding America "Map the Meal Gap" modeling (pending Tommy's investigation — will be separate spec)
  - Exact LILA CSV column names may differ from documentation (verify after download)
```
