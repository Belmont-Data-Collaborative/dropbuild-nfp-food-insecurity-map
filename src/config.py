from __future__ import annotations

import os

import streamlit as st


def _get_secret(key: str, default: str | None = None) -> str | None:
    """Check os.environ.get(key) FIRST, then fall back to st.secrets.
    NEVER call st.secrets before checking os.environ — it crashes at import time."""
    value = os.environ.get(key)
    if value is not None:
        return value
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# AWS / S3 Configuration
# ---------------------------------------------------------------------------
AWS_BUCKET_NAME: str = _get_secret("AWS_BUCKET_NAME", "") or ""
S3_PARTNERS_KEY: str = "nfp-mapping/nfp_partners.csv"
S3_CENSUS_KEY: str = "nfp-mapping/census_tract_data.csv"
S3_CDC_PLACES_KEY: str = "nfp-mapping/cdc_places_data.csv"
S3_GEOCODE_CACHE_KEY: str = "nfp-mapping/geocode_cache.csv"

# ---------------------------------------------------------------------------
# Expected CSV column names
# ---------------------------------------------------------------------------
PARTNERS_CSV_COLUMNS: list[str] = [
    "partner_name",
    "address",
    "partner_type",
]
CENSUS_CSV_COLUMNS: list[str] = [
    "GEOID",
    "poverty_rate",
    "median_household_income",
    "data_vintage",
]
CDC_PLACES_CSV_COLUMNS: list[str] = [
    "GEOID",
    "DIABETES_CrudePrev",
    "data_vintage",
]

# ---------------------------------------------------------------------------
# Partner type colors and labels
# ---------------------------------------------------------------------------
PARTNER_TYPE_COLORS: dict[str, str] = {
    "school_summer": "#E41A1C",
    "medical_health": "#377EB8",
    "transitional_housing": "#4DAF4A",
    "senior_services": "#984EA3",
    "community_development": "#FF7F00",
    "homeless_outreach": "#A65628",
    "workforce_development": "#F781BF",
    "after_school": "#999999",
}

PARTNER_TYPE_LABELS: dict[str, str] = {
    "school_summer": "School & Summer Programs",
    "medical_health": "Medical & Health Services",
    "transitional_housing": "Transitional Housing",
    "senior_services": "Senior Services",
    "community_development": "Community Development",
    "homeless_outreach": "Homeless Outreach",
    "workforce_development": "Workforce Development",
    "after_school": "After-School Programs",
}

FALLBACK_COLOR: str = "#CCCCCC"

# ---------------------------------------------------------------------------
# Choropleth layer definitions
# ---------------------------------------------------------------------------
CHOROPLETH_LAYERS: list[dict] = [
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

DEFAULT_CHOROPLETH_LAYER: str = "median_income"
CDC_PLACES_INDICATOR_COLUMN: str = "DIABETES_CrudePrev"

# ---------------------------------------------------------------------------
# Map defaults
# ---------------------------------------------------------------------------
DAVIDSON_CENTER: list[float] = [36.1627, -86.7816]
DEFAULT_ZOOM: int = 11

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
GEOJSON_PATH: str = "data/shapefiles/davidson_county_tracts.geojson"

# ---------------------------------------------------------------------------
# Mock data configuration
# ---------------------------------------------------------------------------
MOCK_DATA_DIR: str = os.environ.get("MOCK_DATA_DIR", "data/mock/")
USE_MOCK_DATA: bool = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"

# ---------------------------------------------------------------------------
# User-facing message constants
# ---------------------------------------------------------------------------
ERROR_DATA_LOAD: str = (
    "Map data could not be loaded. "
    "Please refresh the page or contact BDAIC support."
)
ERROR_MISSING_COLUMN: str = (
    "Partner data is missing required column: {column_name}. "
    "Please check the data file."
)
WARNING_GEOCODE_FAILURES: str = (
    "{count} partner location(s) could not be mapped "
    "due to address lookup errors."
)
WARNING_NO_GEOID_MATCH: str = (
    "No data could be matched to map boundaries. "
    "Please contact BDAIC support."
)
