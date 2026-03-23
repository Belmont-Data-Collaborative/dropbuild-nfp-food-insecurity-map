# NFP Food Insecurity Map — Specification

## Overview

An interactive food insecurity mapping tool for the Nashville Food Project (NFP) and
Belmont University's BDAIC. Displays a Folium choropleth map of Davidson County,
Tennessee at census-tract level, overlaying NFP partner locations with Census ACS
poverty/income data and CDC PLACES health indicators. Designed for non-technical NFP
staff, city policymakers, and foundation funders — enabling data-informed decisions
about where food need is concentrated and where NFP should expand its partner network.

## Requirements

1. Build with Python and Streamlit (minimum 1.30.0).
2. All dependencies must be listed in `requirements.txt` with fully pinned versions (e.g., `folium==0.15.1`, not `folium>=0.15.1`).
3. The app must run with `streamlit run app.py` from the project root inside a `.venv` virtual environment.
4. Implement the exact directory structure: `app.py` (thin Streamlit entry point), `src/__init__.py`, `src/config.py`, `src/data_loader.py`, `src/geocoder.py`, `src/layer_manager.py`, `src/map_builder.py`, `data/shapefiles/`, `data/mock/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `scripts/setup.sh`, `scripts/import_shapefiles.py`, `scripts/generate_mock_data.py`, `docs/spec.md`, `ASSUMPTIONS.md`, `.env.example`.
5. Document any deviation from this structure in `ASSUMPTIONS.md`.
6. Implement `scripts/import_shapefiles.py`: download the Census TIGER/Line Tennessee tract shapefile from `https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_47_tract.zip` using a temp directory, filter to Davidson County FIPS `037`, assert 200-300 rows (exit code 1 if assertion fails), reproject to EPSG:4326, retain only `GEOID`/`NAME`/`NAMELSAD`/`geometry` fields, zero-pad GEOID to 11 characters with `str.zfill(11)`, and write to `data/shapefiles/davidson_county_tracts.geojson`.
7. Support optional `--output PATH` flag.
8. Handle network errors, empty filter results, and directory creation failures with descriptive messages and exit code 1.
9. Print progress and a success summary with tract count.
10. Implement `scripts/generate_mock_data.py`: read GEOIDs from `data/shapefiles/davidson_county_tracts.geojson` (must be run after `import_shapefiles.py`).
11. Generate `data/mock/mock_nfp_partners.csv` (30 rows, exactly 2 blank address values, names using real Davidson County neighborhood prefixes from the list: Antioch/Bordeaux/Donelson/East Nashville/Germantown/Madison/Napier/North Nashville/Rivergate/Sylvan Park, addresses using real Nashville street names and Davidson County zip codes, partner_type weighted: school_summer+community_development at 20% each, remaining 6 types split evenly).
12. Generate `data/mock/mock_census_tract_data.csv` (one row per GEOID, poverty_rate 3.0-45.0 right-skewed via lognormal, median_household_income 22000-120000 negatively correlated with poverty_rate, exactly 3 rows with blank values, data_vintage='ACS 2022 5-Year Estimates').
13. Generate `data/mock/mock_cdc_places_data.csv` (one row per GEOID, DIABETES_CrudePrev 5.0-22.0 mildly correlated with poverty_rate, data_vintage='CDC PLACES 2022').
14. Accept `--seed` (default 42) and `--output-dir` flags.
15. Output must be byte-identical for the same seed.
16. Fetch the three production data CSVs from S3 at startup using boto3: `nfp_partners.csv`, `census_tract_data.csv`, `cdc_places_data.csv` from paths `s3://[AWS_BUCKET_NAME]/nfp-mapping/[filename]`.
17. Load AWS credentials and bucket name from environment variables via python-dotenv.
18. Never hardcode credentials.
19. Wrap the boto3 client factory in `@st.cache_resource`.
20. Support local development mode: if `USE_MOCK_DATA=true` is in `.env`, load CSV files from `MOCK_DATA_DIR` (default `data/mock/`) instead of S3, load geocode cache from `data/mock/mock_geocode_cache.csv` if it exists, and skip all S3 reads and writes.
21. Add both env vars to `.env.example` with descriptive comments.
22. This mode must allow full local operation with no AWS credentials.
23. Implement GEOID normalization in `data_loader.py`: apply `str.zfill(11)` to the GEOID column in Census ACS and CDC PLACES DataFrames immediately after loading.
24. Also normalize GeoJSON feature GEOID properties to 11 characters.
25. All three sources must use consistent 11-character GEOIDs for join operations.
26. Implement `src/config.py` as the single source of truth for all constants.
27. Implement `src/geocoder.py`: accept a list of address strings, check the geocode cache CSV for each address, call Nominatim via geopy for uncached addresses at a rate of no more than 1 request per second, append results to the cache, and write the updated cache back to S3 (or skip S3 write in mock mode).
28. Construct every Nominatim query string by appending `', Davidson County, TN, USA'` to the raw address.
29. Return a DataFrame with columns: partner_name, address, latitude, longitude, geocode_status ('success' or 'failed').
30. Wrap the Nominatim geolocator in `@st.cache_resource`.
31. Render an interactive Folium map (via `streamlit-folium` minimum 0.18.0) centered on Davidson County at `DEFAULT_ZOOM` showing all census tract boundaries without requiring scroll or zoom on a 1920x1080 display.
32. Map height must be at least 700px.
33. Pass `returned_objects=[]` to `st_folium()` unless click event data is explicitly needed.
34. Load Davidson County census tract boundaries from `data/shapefiles/davidson_county_tracts.geojson` and render them as a persistent Folium GeoJSON layer at all times.
35. Cache the GeoJSON dict with `@st.cache_data` so the file is read from disk exactly once per session.
36. Render each successfully geocoded NFP partner as a Folium CircleMarker colored by `PARTNER_TYPE_COLORS` from `config.py`.
37. Partners with unrecognized partner_type values render in `FALLBACK_COLOR` with label 'Unknown Type' and a console warning.
38. Display a Folium popup on click for each partner marker containing: organization name, partner type display label, and 'Nashville Food Project Partner'.
39. No raw field names, column names, or internal identifiers may appear in any popup.
40. Implement the Streamlit sidebar with exactly the specified sections in order, separated by `st.divider()`.
41. All sections must be visible without sidebar scrolling on a 1920x1080 display at 100% browser zoom.
42. On initial page load, render the Median Household Income choropleth by default.
43. Store all layer selection and checkbox state in `st.session_state`.
44. Switching layers or toggling partner visibility must not trigger S3 re-fetches.
45. Render the selected choropleth as a Folium GeoJSON layer with YlOrRd color scale.
46. Display a map legend in the bottom-right corner showing color scale and numeric range.
47. Legend must update when the user changes layers and disappear when 'None' is selected.
48. Display a Folium popup on click for each census tract showing formatted data.
49. When no choropleth is selected, popup shows only tract number with instruction.
50. Display a persistent data freshness notice in the sidebar.
51. The notice must dynamically update when the user changes the choropleth layer selection.
52. Wrap all data loading functions with `@st.cache_data`.
53. Wrap operations expected to take more than 1 second in `st.spinner()`.
54-58. Handle all error states without exposing Python tracebacks.
59. Implement the complete pytest test suite under `tests/`.
60. Create fixture files in `tests/fixtures/`.
61. All tests must pass before the build is considered complete.
62. Follow PEP8 for all Python.
63. Use `black` for formatting and `flake8` for linting.
64. Implement `scripts/setup.sh` as a one-command setup.
65. Create `ASSUMPTIONS.md` at project root.
