# Assumptions & Architectural Decisions

## A1: Map Export Format
The spec requests "Download Map as PNG" but PNG export is impossible in a pure Streamlit
environment (no headless browser available). We implement HTML download via
`st.download_button` instead. This provides a fully interactive, offline-viewable map
file that is superior to a static PNG for the target audience.

## A2: Geocoding Rate Limiting
Nominatim's usage policy requires max 1 request per second. We enforce this with a
`time.sleep(1)` between uncached geocoding requests. Cached addresses are returned
instantly.

## A3: Geocoding Failure Handling
Individual geocoding failures (unresolvable addresses, timeouts) are silently handled
by setting latitude/longitude to NaN and geocode_status to 'failed'. The app displays
a warning with the exact count of failures. No exceptions are raised for individual
address failures.

## A4: GEOID Normalization
All GEOID values across Census, CDC PLACES, and GeoJSON data are normalized to exactly
11 characters using `str.zfill(11)` immediately after loading. This ensures consistent
join operations across all data sources.

## A5: Config as Source of Truth
`src/config.py` is the single source of truth for all constants, color maps, layer
definitions, and user-facing message strings. It has zero imports from other src/
modules. It uses `_get_secret()` which checks `os.environ` first, then `st.secrets`.

## A6: Exception Ownership
Custom exceptions are defined in the module that raises them:
- `DataLoadError`, `DataSchemaError` in `src/data_loader.py`
- `GeocodingError` in `src/geocoder.py`
They are NOT defined in `config.py`.

## A7: Script Independence
Scripts in `scripts/` (import_shapefiles.py, generate_mock_data.py) are fully
standalone and do NOT import from `src/` modules. This avoids triggering Streamlit's
ScriptRunContext warnings when run outside the Streamlit app.

## A8: Mock Data Mode
When `USE_MOCK_DATA=true`, the app reads all data from local CSV files in `MOCK_DATA_DIR`
(default: `data/mock/`). No AWS credentials are required. S3 reads and writes are
completely skipped.

## A9: Choropleth Color Scale
All choropleth layers use the YlOrRd (yellow-to-red) color scale from branca where
lighter = lower value and darker/redder = higher value.

## A10: Tract Boundary Persistence
Census tract boundaries are rendered as a persistent GeoJSON layer at all times,
regardless of choropleth selection. The choropleth is rendered as a separate layer
on top of (or replacing) the base boundary style.

## A11: Davidson County Tract Count
The Census TIGER/Line 2020 data for Davidson County (FIPS 037) contains approximately
200-300 census tracts. The import_shapefiles.py script asserts this range.

## A12: Sidebar Scrolling
All sidebar sections are designed to fit within a 1920x1080 viewport at 100% zoom
without scrolling, using compact HTML for the partner type legend.
