# NFP Food Insecurity Map — Build Instructions

**App ID**: nfp-food-insecurity-map
**Runtime**: streamlit

## Technology Constraints

RUNTIME CONSTRAINT — PYTHON / STREAMLIT APP:
The spec declares runtime "streamlit". This means:
- techStack.frontend MUST be "Streamlit".
- techStack.backend MUST be "Python 3.11".
- techStack.deployment MUST be "Streamlit Community Cloud".
- The app MUST be a Python application using Streamlit as the web framework.
- Entry point MUST be app.py at the project root.
- Source modules MUST live under src/ (e.g. src/config.py, src/data_loader.py).
- Tests MUST live under tests/ using pytest.
- A requirements.txt with pinned dependency versions MUST be included.
- A .env.example documenting all required environment variables MUST be included.

ALLOWED LIBRARIES (pin versions in requirements.txt):
- streamlit, streamlit-folium, folium (for mapping)
- pandas (for data manipulation)
- boto3 (for AWS S3 access)
- geopy (for geocoding via Nominatim)
- python-dotenv (for local .env loading)
- branca (for Folium legends/colormaps)
- pytest, pytest-cov (for testing)
- Any other Python library explicitly mentioned in the spec requirements.

DO NOT USE:
- Node.js, npm, JavaScript frameworks, or any JS build tools.
- Flask, FastAPI, Django, Dash, or any other web framework besides Streamlit.
- Plotly, Mapbox, Google Maps, or any mapping library besides Folium.

ERROR HANDLING PATTERN:
- Define typed exceptions (e.g. DataLoadError, DataSchemaError) in the appropriate module.
- Use st.error() for user-facing errors — never expose Python tracebacks.
- Use st.warning() for non-fatal issues (e.g. geocoding failures).
- Credentials via os.environ with st.secrets fallback (for Streamlit Cloud deployment).

## Required Project Structure

Required directory structure:
- app.py — Streamlit entrypoint (at project root; first Streamlit call must be st.set_page_config())
- src/__init__.py — Package init (empty file)
- src/config.py — Constants source of truth (zero internal imports; check os.environ before st.secrets)
- src/<module>.py — Source modules (define custom exceptions in the module that raises them)
- tests/__init__.py — Test package init (empty file)
- tests/test_<module>.py — pytest test files (test functions that actually exist in source)
- tests/fixtures/ — Test fixture CSV and data files
- requirements.txt — Pinned Python dependencies (include pytest, pytest-cov)
- .env.example — All required environment variables documented
- Optional: scripts/ — Standalone utility scripts (must NOT import from src/)
- Optional: data/ — Data directories (populated by scripts/)

## Contract Rules

Contract type: `moduleContract`

config.py is the SOURCE OF TRUTH for all constants and configuration. The architect teammate must define a moduleContract in CONTRACT.md listing every Python module, public function signature, shared constant, custom exception, and data flow description. All teammates must use EXACT function names and signatures from this contract.

## Code Patterns and Anti-Patterns

- Add "from __future__ import annotations" as the VERY FIRST LINE of every .py file.
- In app.py: "from dotenv import load_dotenv" then "load_dotenv()" BEFORE any src/ imports.
- In app.py: first Streamlit call in main() MUST be st.set_page_config() — no Streamlit calls before it.
- In config.py: _get_secret() MUST check os.environ.get(key) FIRST, then fall back to st.secrets.
  If st.secrets is checked at module import time it crashes with StreamlitAPIException.
- config.py must have ZERO internal imports (no imports from other src/ modules).
- config.py must define ALL user-facing error/warning message string constants (e.g. ERROR_DATA_LOAD).
- Custom exceptions (DataLoadError, DataSchemaError, etc.) belong in the module that raises them, NOT in config.py.
- app.py imports exceptions from the module that defines them (e.g. "from src.data_loader import DataLoadError").
- Every function imported must match the EXACT name and signature from CONTRACT.md.
- CRITICAL: Do NOT rename functions with synonyms (create/build/make) — use the EXACT name from the contract.
- Scripts in scripts/ must be fully standalone — NO imports from src/ modules (src/config.py imports streamlit).
- Do NOT use Node.js, npm, Flask, FastAPI, Django, Dash, or any framework other than Streamlit.

## QA Validation Rules

PYTHON / STREAMLIT QA CHECKS:

CRITICAL META-RULE — ONLY REPORT ACTUAL PROBLEMS:
- Each issue in the issues list MUST require an actual code change to fix.
- Do NOT include issues where the suggested fix is "no fix required" or "implementation is correct".
- If a requirement is correctly implemented, do NOT add it to the issues list at all.
- Every issue you report will be sent to a fixer agent. If there is nothing to fix, do not report it.

IMPORT CONSISTENCY (HIGHEST PRIORITY — #1 cause of Python build failures):
- For every "from src.X import Y" statement, verify Y ACTUALLY EXISTS as a function/class/constant in src/X.py.
- For every "from src.config import Z", verify Z is defined in config.py.
- Flag as HIGH severity if a module imports a name that does not exist in the target module.

COMMON PHANTOM IMPORT PATTERNS TO CHECK:
- app.py imports error MESSAGE CONSTANTS (e.g. ERROR_DATA_LOAD, WARNING_GEOCODE_FAILURES) from config.py
  → Verify these string constants are actually defined in config.py. If not, flag as HIGH.
- app.py imports EXCEPTION CLASSES (e.g. DataLoadError, DataSchemaError) from config.py
  → These should be imported from the module that defines them (usually data_loader.py), NOT config.py.
  → If app.py imports an exception from config.py but it is defined in data_loader.py, flag as HIGH.
  → The fix is to change the import source in app.py, not to move the class.
- Any "from src.X import Y" where Y exists in a DIFFERENT module than X → flag as HIGH.

FUNCTION SIGNATURE AND RETURN TYPE CONSISTENCY:
- If app.py calls load_csv_from_s3(bucket, key), verify data_loader.py defines that function with matching parameters.
- Flag as HIGH severity if call signatures do not match definitions.
- CHECK RETURN TYPE UNPACKING: if any caller does "a, b = some_func()", verify some_func() returns a tuple.
  If the function returns a single object (e.g. GeoJson | None), the caller will crash with "cannot unpack".
  Flag as HIGH severity if a caller unpacks a return value but the function does not return a tuple.

FUNCTION NAME PREFIX CONSISTENCY:
- Check that module-internal function names use consistent prefixes.
  If layer_manager.py defines build_choropleth_layer and build_partner_markers,
  but another module imports create_base_tract_layer — that is a mismatch.
- Flag as HIGH severity if an imported function name uses a different prefix than the actual definition.

CONSTANT NAME EXACT MATCH:
- If config.py defines LAYOUT but app.py imports PAGE_LAYOUT, that will crash.
- For EVERY constant imported from config, verify the EXACT name exists in config.py.
- Common mistake: adding/removing a prefix (PAGE_LAYOUT vs LAYOUT, MAP_ZOOM vs DEFAULT_ZOOM).
- Flag as HIGH severity if a constant name does not match exactly.

REQUIREMENTS COMPLETENESS:
- Every "import X" in source code should have X (or its PyPI name) in requirements.txt.
- Flag as MEDIUM severity if a dependency is missing from requirements.txt.

TEST VALIDITY:
- Test files must import functions that actually exist in the source modules.
- Tests must not reference classes/methods that do not exist.
- Flag as HIGH severity if tests will fail due to import errors.

EXCEPTION HANDLING:
- Custom exceptions (DataLoadError, DataSchemaError, etc.) must be defined before being raised/caught.
- st.error() should be used for user-facing errors in app.py, not bare raise statements.

CONFIG REFERENCES:
- Every config.CONSTANT referenced in code must be defined in config.py.
- Flag as HIGH severity if a constant is referenced but not defined.

STREAMLIT STARTUP ORDER:
- app.py MUST call load_dotenv() BEFORE importing from src/ (so os.environ is populated when config.py loads).
- app.py MUST "import folium" explicitly if it references folium.Map or any folium type.
- config.py _get_secret() MUST check os.environ.get() FIRST, then fall back to st.secrets.
  If st.secrets is called at module import time it triggers Streamlit before set_page_config() and crashes.
- Flag as CRITICAL severity ONLY if config.py calls st.secrets BEFORE checking os.environ (i.e., st.secrets is the first path).
- Flag as CRITICAL severity ONLY if app.py does NOT call load_dotenv() before src imports.
- Flag as HIGH severity if app.py uses folium types without an explicit "import folium".
- IMPORTANT: If the startup order IS correct (load_dotenv first, os.environ checked first in _get_secret), do NOT create an issue for it AT ALL.
  Do NOT include it in the issues list, even to say "no fix required" — that inflates the issue count and breaks the fix loop.
  Only include issues that ACTUALLY NEED FIXING. A correct implementation is not an issue.

GEOCODING ERROR HANDLING:
- geocode_partners() MUST NOT raise exceptions for individual unresolvable addresses.
- It should silently skip addresses where geocoding returns None or throws per-address exceptions.
- The caller counts NaN lat/lon rows to determine failures, then shows st.warning().
- Flag as HIGH severity if geocode_partners() raises GeocodingError from within the per-address loop.
- Flag as HIGH severity if tests expect GeocodingError for unresolvable addresses (tests should check for NaN instead).
- If geocode_partners() correctly catches per-address errors and returns NaN, do NOT create an issue for it.
  A correct implementation is not an issue — only flag things that NEED FIXING.

MAP EXPORT — READ CAREFULLY:
- PNG export is IMPOSSIBLE in pure Streamlit (no headless browser). HTML download is the CORRECT implementation.
- If the code uses st.download_button with map HTML, the export requirement IS FULLY SATISFIED.
- The spec says "Download Map as PNG" but this is a known limitation. HTML export is the approved workaround.
- Do NOT flag HTML export as an issue AT ANY SEVERITY — not critical, not high, not medium, not low.
- Do NOT suggest implementing PNG export, Selenium, or headless browsers.
- Flag ONLY if no download/export functionality exists at all (MEDIUM severity).

STRUCTURED REQUIREMENT VERIFICATION (when structuredRequirements and fileRequirementMap are provided):
- For each file, check the requirements listed in its implementsRequirements.
- For each such requirement, verify every acceptance criterion against the source code.
- Populate requirementCoverage with per-requirement status.
- When an issue maps to a specific requirement, set requirementId and acceptanceCriterion on the issue.

ENVIRONMENT FILE SETUP:
- If .env.example exists but .env does not, flag as HIGH severity.
- The tester should copy .env.example to .env before running the app.
- Without .env, the app cannot read configuration and will crash at runtime.

UTILITY SCRIPT INDEPENDENCE:
- Scripts in scripts/ (e.g. generate_mock_data.py, import_shapefiles.py) must NOT import from src/ modules.
- src/config.py imports streamlit, which triggers ScriptRunContext warnings when run outside the Streamlit app.
- If a script imports from src.config, src.data_loader, or any src/ module, flag as HIGH severity.
- Scripts should define any needed constants locally or read from data files.

UTILITY SCRIPT DATA ASSERTIONS:
- If scripts assert data counts (e.g. assert 200 <= tract_count <= 300), verify the range is realistic.
- Real-world data often differs from spec estimates. A too-narrow range causes script failures.
- Flag as MEDIUM severity if assertion ranges are too tight (e.g. exact match or <20% tolerance).

UTILITY SCRIPT EXECUTION AND DATA COMPLETENESS:
- If scripts/ directory contains .py files (e.g. generate_mock_data.py, import_shapefiles.py), they MUST be executed during testing.
- After running scripts, verify data directories (data/, data/mock/, data/shapefiles/) are NOT empty.
- Flag as CRITICAL severity if scripts exist but their output data directories are empty — the app will crash at runtime with missing data.

SMOKE TEST — APP ACTUALLY RUNS:
- After pytest passes, the tester MUST start the Streamlit app and verify it responds.
- Start: streamlit run app.py --server.port 8599 --server.headless true &
- Verify: curl -s http://localhost:8599 should contain "streamlit" (case-insensitive).
- Flag as CRITICAL severity if the app crashes on startup or does not respond.
- A passing "import app" test and passing pytest do NOT guarantee the app actually runs.

## Test Artifact Requirements

The tester teammate MUST produce ALL of the following artifacts. These let humans and CI
inspect, reproduce, and re-run every check independently — without re-running the agent.

### 1. Playwright E2E tests  (`tests/e2e/app.spec.mjs` + `playwright.config.mjs`)

Write a Playwright test file `tests/e2e/app.spec.mjs` that covers EVERY requirement
in the spec — one test per requirement, named `REQ-N: <description>`.

For Streamlit, write `tests/e2e/app.spec.mjs` using Playwright with `baseURL: http://localhost:8501`.
Use `page.waitForSelector` to wait for Streamlit hydration before asserting content.

**After writing the test files, run them:**
```bash
npm install --save-dev @playwright/test
npx playwright install chromium
npx playwright test
```

### 2. Screenshots  (`tests/screenshots/`)

Playwright captures screenshots automatically via `screenshot: "on"` in the config.
Additionally, call `page.screenshot(...)` inside tests at key moments:
- Initial page load (01-initial-load.png)
- After each interactive action (02-after-click.png, etc.)
- Final state (04-full-page-final.png)

### 3. HTML snapshot  (`tests/snapshots/homepage.html`)

After page hydration, capture the full rendered HTML for offline inspection:
```js
test('snapshot: capture full HTML', async ({ page }) => {
  await page.goto('/'); await page.waitForTimeout(500);
  const { writeFileSync, mkdirSync } = await import("fs");
  mkdirSync("tests/snapshots", { recursive: true });
  writeFileSync("tests/snapshots/homepage.html", await page.content(), "utf8");
});
```

### 4. Test manifest  (`tests/test-manifest.json`)

Write a JSON file documenting every check performed, with `howToReproduce` for each:
```json
{
  "appId": "<appId>", "generatedAt": "<ISO timestamp>",
  "howToRunAll": "cd build/<appId> && ./tests/run-tests.sh",
  "checks": [
    { "id": "BUILD-1", "name": "npm run build succeeds", "requirement": "REQ-N",
      "category": "build", "howToReproduce": "npm run build",
      "expectedOutcome": "exit code 0", "result": "passed" },
    { "id": "E2E-REQ1", "name": "...", "requirement": "REQ-1",
      "category": "e2e", "howToReproduce": "npx playwright test --grep REQ-1",
      "screenshotPath": "tests/screenshots/01-initial-load.png", "result": "passed" }
  ],
  "artifacts": {
    "screenshots": { "files": [{ "path": "tests/screenshots/01-initial-load.png", "description": "Initial load" }] },
    "htmlSnapshot": { "file": "tests/snapshots/homepage.html" },
    "e2eReport": { "file": "tests/playwright-report/index.html" }
  }
}
```

### 5. Runnable test script  (`tests/run-tests.sh`)

Write a shell script that runs all tests from scratch — a new team member should be able
to clone the repo and run `./tests/run-tests.sh` to verify everything:
```bash
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
npm install --silent
npm run build
npx playwright install chromium --quiet 2>/dev/null || true
npx playwright test --reporter=list
echo "Reports: tests/playwright-report/index.html | Screenshots: tests/screenshots/"
```
chmod +x tests/run-tests.sh after writing.

### 6. Legacy JSON result files  (still required)

Also write the original JSON result files for orchestrator compatibility:

**`tests/unit/unit-result.json`:**
```json
{ "runner": "jest", "total": 12, "passed": 10, "failed": 2, "skipped": 0,
  "failures": [{ "suite": "ComponentName", "test": "test description", "error": "error message" }] }
```

**`tests/smoke/smoke-result.json`:**
```json
{ "passed": true, "serverStarted": true, "httpStatus": 200, "containsMarker": true,
  "marker": "__next", "curlOutput": "first 200 chars of response" }
```

**Rules that apply to all artifacts:**
- Create all directories (`tests/unit/`, `tests/smoke/`, `tests/screenshots/`, `tests/snapshots/`) before writing.
- Write every file even if tests fail — record actual results, not just successes.
- If no unit tests exist, write `{ "runner": null, "total": 0, "passed": 0, "failed": 0, "skipped": 0, "note": "no unit tests in project" }`.
- `tests/smoke/smoke-result.json` is the primary health check — always write it.
## Fix Guidelines

You are a senior Python engineer fixing bugs found by a QA review.
You are given:
- The refined app spec.
- ALL files in the project with their current contents.
- ALL QA issues found across the project.
- The ONE file you need to fix.

Return the COMPLETE corrected contents of that ONE file.

CRITICAL RULES:
- Respond with the raw file contents ONLY: no markdown fences, no JSON, no commentary.
- Return the COMPLETE file, not a diff.
- Follow PEP8. Use type hints. Add concise docstrings.

DO NOT BREAK CROSS-MODULE CONSISTENCY — THIS IS THE #1 RULE:
- NEVER rename functions, classes, constants, or exceptions that exist in other files.
- NEVER change function signatures (parameter names, order, types) — other files depend on them.
- NEVER change import paths — other files are importing from these exact paths.
- If app.py imports "load_csv_from_s3" from data_loader, that name MUST stay exactly the same.
- If config.py defines BUCKET_NAME, do NOT rename it to S3_BUCKET or anything else.
- Fix ONLY the logic within existing function bodies. Preserve all public interfaces exactly.
- If a fix requires changing a public interface, make the MINIMUM change and document it clearly.

CONSERVATIVE FIXES ONLY:
- Fix the specific QA issues listed. Do NOT refactor unrelated code.
- Do NOT reorganize imports, reorder functions, or rename variables that are not part of the issue.
- Do NOT add new functions or classes unless the QA issue specifically requires it.
- Keep the file as close to the original as possible while fixing the flagged issues.

GEOCODER FIX PATTERN (if fixing geocoder.py):
- geocode_partners() must NEVER raise for individual address failures.
- Catch ALL per-address exceptions inside the loop and silently continue.
- Return (df, cache) with NaN for failed addresses. The caller counts NaN to show warnings.

IMPORT SOURCE FIX PATTERN (if fixing import errors in app.py):
- Constants (ERROR_DATA_LOAD, WARNING_GEOCODE_FAILURES, color maps) → import from src.config.
- Exception classes (DataLoadError, DataSchemaError) → import from the module that DEFINES them
  (usually src.data_loader), NOT from src.config.
- If a constant is missing from config.py, ADD it there (config.py owns all constants).
- If an exception is imported from the wrong module, change the import source in app.py.

TECHNOLOGY: Python / Streamlit only. No Node.js or JS frameworks.

REQUIREMENT-DRIVEN FIXES:
- Use the acceptance criteria to understand what "correct" means.
- When an issue references a requirementId, check the corresponding acceptance criteria.
- Fix the code to satisfy the specific criteria listed, not just the vague issue description.

## Deployment

Strategy: manual
Streamlit apps use manual deployment to Streamlit Community Cloud.
Build output should be a complete, runnable Python project.

## Known Mistakes — Do NOT Repeat

These are real errors from previous builds in this project. Internalize them before writing any code.

### Confirmed Working Patterns (use these)
- **Use direct spawn args (not bash -c) for subprocess execution — avoids shell injection via filenames** — appLauncher.mjs
  - Use full path to venv binaries: `.venv/bin/pip`, `.venv/bin/python3`, `.venv/bin/streamlit`
- **Schema validation (additionalProperties:false) must skip already-processed specs — check status before validating** — bugFixOrchestrator
  - Fixed/errored bug specs have system-written fields (agentResult) that would fail strict schema

## Application Requirements

1. Build with Python and Streamlit (minimum 1.30.0).
2. All dependencies must be listed in `requirements.txt` with fully pinned versions (e.g., `folium==0.15.1`, not `folium>=0.15.1`).
3. The app must run with `streamlit run app.py` from the project root inside a `.venv` virtual environment.
4. Implement the exact directory structure: `app.py` (thin Streamlit entry point), `src/__init__.py`, `src/config.py`, `src/data_loader.py`, `src/geocoder.py`, `src/layer_manager.py`, `src/map_builder.py`, `data/shapefiles/`, `data/mock/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `scripts/setup.sh`, `scripts/import_shapefiles.py`, `scripts/generate_mock_data.py`, `docs/spec.md`, `ASSUMPTIONS.md`, `.env.example`.
5. Document any deviation from this structure in `ASSUMPTIONS.md`.
6. Implement `scripts/import_shapefiles.py`: download the Census TIGER/Line Tennessee tract shapefile from `https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_47_tract.zip` using a temp directory, filter to Davidson County FIPS `037`, assert 200–300 rows (exit code 1 if assertion fails), reproject to EPSG:4326, retain only `GEOID`/`NAME`/`NAMELSAD`/`geometry` fields, zero-pad GEOID to 11 characters with `str.zfill(11)`, and write to `data/shapefiles/davidson_county_tracts.geojson`.
7. Support optional `--output PATH` flag.
8. Handle network errors, empty filter results, and directory creation failures with descriptive messages and exit code 1.
9. Print progress and a success summary with tract count.
10. Implement `scripts/generate_mock_data.py`: read GEOIDs from `data/shapefiles/davidson_county_tracts.geojson` (must be run after `import_shapefiles.py`).
11. Generate `data/mock/mock_nfp_partners.csv` (30 rows, exactly 2 blank address values, names using real Davidson County neighborhood prefixes from the list: Antioch/Bordeaux/Donelson/East Nashville/Germantown/Madison/Napier/North Nashville/Rivergate/Sylvan Park, addresses using real Nashville street names and Davidson County zip codes, partner_type weighted: school_summer+community_development at 20% each, remaining 6 types split evenly).
12. Generate `data/mock/mock_census_tract_data.csv` (one row per GEOID, poverty_rate 3.0–45.0 right-skewed via lognormal, median_household_income 22000–120000 negatively correlated with poverty_rate, exactly 3 rows with blank values, data_vintage='ACS 2022 5-Year Estimates').
13. Generate `data/mock/mock_cdc_places_data.csv` (one row per GEOID, DIABETES_CrudePrev 5.0–22.0 mildly correlated with poverty_rate, data_vintage='CDC PLACES 2022').
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
26. Implement `src/config.py` as the single source of truth for all constants: `AWS_BUCKET_NAME` (from env), S3 file paths, expected CSV column names, `PARTNER_TYPE_COLORS` dict mapping 8 raw partner_type values to hex colors (school_summer=#E41A1C, medical_health=#377EB8, transitional_housing=#4DAF4A, senior_services=#984EA3, community_development=#FF7F00, homeless_outreach=#A65628, workforce_development=#F781BF, after_school=#999999), `PARTNER_TYPE_LABELS` dict mapping raw values to plain-English display labels, `FALLBACK_COLOR='#CCCCCC'`, `CHOROPLETH_LAYERS` list of dicts (each with keys: id, display_name, csv_source, csv_column, unit_label, format_string, data_vintage_key), `DEFAULT_CHOROPLETH_LAYER='median_income'`, `CDC_PLACES_INDICATOR_COLUMN='DIABETES_CrudePrev'`, `DAVIDSON_CENTER=[36.1627, -86.7816]`, `DEFAULT_ZOOM=11`.
27. Implement `src/geocoder.py`: accept a list of address strings, check the geocode cache CSV for each address, call Nominatim via geopy for uncached addresses at a rate of no more than 1 request per second, append results to the cache, and write the updated cache back to S3 (or skip S3 write in mock mode).
28. Construct every Nominatim query string by appending `', Davidson County, TN, USA'` to the raw address (Transform 2).
29. Return a DataFrame with columns: partner_name, address, latitude, longitude, geocode_status ('success' or 'failed').
30. Wrap the Nominatim geolocator in `@st.cache_resource`.
31. Render an interactive Folium map (via `streamlit-folium` minimum 0.18.0) centered on Davidson County at `DEFAULT_ZOOM` showing all census tract boundaries without requiring scroll or zoom on a 1920x1080 display.
32. Map height must be at least 700px.
33. Pass `returned_objects=[]` to `st_folium()` unless click event data is explicitly needed.
34. Load Davidson County census tract boundaries from `data/shapefiles/davidson_county_tracts.geojson` and render them as a persistent Folium GeoJSON layer at all times.
35. Cache the GeoJSON dict with `@st.cache_data` so the file is read from disk exactly once per session.
36. Render each successfully geocoded NFP partner as a Folium CircleMarker colored by `PARTNER_TYPE_COLORS` from `config.py`.
37. Partners with unrecognized partner_type values render in `FALLBACK_COLOR` with label 'Unknown Type' and a console warning that includes the unrecognized value and partner name.
38. Display a Folium popup on click for each partner marker containing: organization name (plain text), partner type display label from `PARTNER_TYPE_LABELS` (never the raw CSV value), and the static text 'Nashville Food Project Partner'.
39. No raw field names, column names, or internal identifiers may appear in any popup.
40. Implement the Streamlit sidebar with exactly these sections in order, each separated by `st.divider()`: (1) `st.title('Nashville Food Project — Food Insecurity Map')` and a 2-sentence description; (2) `st.subheader('Data Layers')` with checkbox 'Show NFP Partner Locations' (default: True) and selectbox 'Background Data Layer' with options [None, 'Poverty Rate (Census)', 'Median Household Income (Census)', CDC PLACES display name] defaulting to 'Median Household Income (Census)'; (3) `st.subheader('Partner Type Legend')` listing all 8 partner types as inline colored HTML swatches with plain-English labels; (4) `st.subheader('Export')` with `st.download_button` labeled '⬇ Download Map as PNG'; (5) `st.subheader('Data Sources')` with the data freshness notice.
41. All sections must be visible without sidebar scrolling on a 1920x1080 display at 100% browser zoom.
42. On initial page load with no user interaction, render the Median Household Income choropleth by default (FR-09).
43. Store all layer selection and checkbox state in `st.session_state`.
44. Switching layers or toggling partner visibility must not trigger S3 re-fetches.
45. Render the selected choropleth as a Folium GeoJSON layer with YlOrRd (yellow-to-red) color scale where lighter=lower value and darker/redder=higher value.
46. Display a map legend in the bottom-right corner of the map showing the color scale and numeric range (min/max) labeled in plain English with the variable name and unit.
47. Legend must update when the user changes layers and disappear when 'None' is selected.
48. Display a Folium popup on click for each census tract showing: 'Census Tract [number]', the value of the currently selected choropleth variable formatted correctly (poverty_rate as '18.3%', median_household_income as '$74,500', CDC PLACES as '14.2%'), and the data vintage year.
49. When no choropleth is selected, popup shows only 'Census Tract [number] — Select a data layer to see values.' Tracts present in GeoJSON but missing from the data CSV render in neutral gray #EEEEEE with popup note 'Data not available for this tract.'
50. Display a persistent data freshness notice in the sidebar that is always visible without scrolling.
51. The notice must dynamically update when the user changes the choropleth layer selection, showing the vintage year for each data source currently displayed.
52. Wrap all data loading and transformation functions in `app.py`, `data_loader.py`, and `geocoder.py` with `@st.cache_data` so S3 fetches and disk reads occur at most once per app session.
53. Wrap any operation expected to take more than 1 second in `st.spinner()` with a plain-English message.
54. Handle all error states without exposing Python tracebacks to the user: S3 connection or NoSuchKey failure → `st.error('Map data could not be loaded.
55. Please refresh the page or contact BDAIC support.')` and stop rendering; missing required CSV column → `st.error('Partner data is missing required column: [column_name].
56. Please check the data file.')`; geocoding failures → `st.warning('X partner location(s) could not be mapped due to address lookup errors.')` where X is the exact count; GeoJSON file missing → same S3 error message; zero GEOID join matches → `st.warning('No data could be matched to map boundaries.
57. Please contact BDAIC support.')`.
58. Geocode cache S3 write failure logs to console only — the app must continue running.
59. Implement the complete pytest test suite under `tests/`: unit tests for each src/ module covering all transforms, error paths, and cache logic; integration test in `tests/integration/test_full_pipeline.py` covering the pipeline from CSV load through map object construction using fixture data.
60. Create fixture files in `tests/fixtures/`: `sample_partners.csv` (5 rows including 1 blank address and 1 unknown partner_type), `sample_geocode_cache.csv`, `sample_census.csv` (3 rows with Davidson County GEOIDs starting with 47037), `sample_cdc_places.csv` (matching GEOIDs).
61. All tests must pass before the build is considered complete.
62. Follow PEP8 for all Python.
63. Use `black` for formatting (max line length 88) and `flake8` for linting.
64. Implement `scripts/setup.sh` as a one-command setup: creates `.venv`, activates it, installs `requirements.txt`, runs `import_shapefiles.py`, and runs `generate_mock_data.py`.
65. Create `ASSUMPTIONS.md` at project root from project start and document every architectural decision not explicitly covered by the spec before proceeding with implementation.

## Full Description

An interactive food insecurity mapping tool for the Nashville Food Project (NFP) and Belmont University's BDAIC. Displays a Folium choropleth map of Davidson County, Tennessee at census-tract level, overlaying NFP partner locations with Census ACS poverty/income data and CDC PLACES health indicators. Designed for non-technical NFP staff, city policymakers, and foundation funders — enabling data-informed decisions about where food need is concentrated and where NFP should expand its partner network.
