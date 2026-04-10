"""Environment-driven configuration.

All layer definitions, partner types, colors, and S3 paths now live in
project.yml and are accessed via src.config_loader.

This module retains only environment-based settings and user-facing
message constants.
"""
from __future__ import annotations

import logging
import os

import streamlit as st


def _get_secret(key: str, default: str | None = None) -> str | None:
    """Check os.environ.get(key) FIRST, then fall back to st.secrets.
    NEVER call st.secrets before checking os.environ."""
    value = os.environ.get(key)
    if value is not None:
        return value
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Environment / mode
# ---------------------------------------------------------------------------
APP_ENV: str = os.environ.get("APP_ENV", "development")
IS_PRODUCTION: bool = APP_ENV == "production"
LOG_LEVEL: int = logging.WARNING if IS_PRODUCTION else logging.INFO

# ---------------------------------------------------------------------------
# AWS configuration
# ---------------------------------------------------------------------------
AWS_BUCKET_NAME: str = _get_secret("AWS_BUCKET_NAME", "") or ""

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
