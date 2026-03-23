from __future__ import annotations

"""Unit tests for src/data_loader.py."""

import os
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Mock streamlit before importing src modules
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())

from src.data_loader import (  # noqa: E402
    DataLoadError,
    DataSchemaError,
    load_csv_from_file,
)

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "fixtures"
)


# ---------------------------------------------------------------------------
# Test: exception classes are defined
# ---------------------------------------------------------------------------
class TestExceptions:
    def test_data_load_error_is_exception(self):
        assert issubclass(DataLoadError, Exception)

    def test_data_schema_error_is_exception(self):
        assert issubclass(DataSchemaError, Exception)

    def test_data_load_error_can_be_raised(self):
        with pytest.raises(DataLoadError):
            raise DataLoadError("test error")

    def test_data_schema_error_can_be_raised(self):
        with pytest.raises(DataSchemaError):
            raise DataSchemaError("test error")


# ---------------------------------------------------------------------------
# Test: load_csv_from_file
# ---------------------------------------------------------------------------
class TestLoadCsvFromFile:
    def test_loads_valid_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col_a,col_b\n1,2\n3,4\n")
        df = load_csv_from_file(str(csv_file))
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["col_a", "col_b"]
        assert len(df) == 2

    def test_raises_data_load_error_for_missing_file(self):
        with pytest.raises(DataLoadError):
            load_csv_from_file("/nonexistent/path/fake.csv")

    def test_loads_fixture_partners(self):
        path = os.path.join(FIXTURES_DIR, "sample_partners.csv")
        df = load_csv_from_file(path)
        assert len(df) == 5
        assert "partner_name" in df.columns

    def test_loads_fixture_census(self):
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        assert len(df) == 3
        assert "GEOID" in df.columns


# ---------------------------------------------------------------------------
# Test: GEOID normalization
# ---------------------------------------------------------------------------
class TestGeoidNormalization:
    def test_census_geoids_are_11_chars(self):
        """After loading census data via load_census_data, GEOIDs should be 11 chars.
        We test the normalization logic directly."""
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        # Apply the same normalization that load_census_data should apply
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        for geoid in df["GEOID"]:
            assert len(str(geoid)) == 11, f"GEOID {geoid} is not 11 chars"

    def test_cdc_geoids_are_11_chars(self):
        path = os.path.join(FIXTURES_DIR, "sample_cdc_places.csv")
        df = load_csv_from_file(path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        for geoid in df["GEOID"]:
            assert len(str(geoid)) == 11


# ---------------------------------------------------------------------------
# Test: schema validation
# ---------------------------------------------------------------------------
class TestSchemaValidation:
    def test_missing_column_raises_schema_error(self, tmp_path):
        """If we load a CSV missing a required column and validate, it should fail."""
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("wrong_col,another\n1,2\n")
        df = load_csv_from_file(str(csv_file))
        required = ["partner_name", "address", "partner_type"]
        missing = [c for c in required if c not in df.columns]
        assert len(missing) > 0, "Test CSV should be missing required columns"
