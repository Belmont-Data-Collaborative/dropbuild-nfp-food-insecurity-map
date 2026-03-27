"""Unit tests for src/data_loader.py — Parquet + multi-granularity loading."""
from __future__ import annotations

import os
import sys
from pathlib import Path
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

from src.data_loader import DataLoadError, DataSchemaError  # noqa: E402


# ---------------------------------------------------------------------------
# Test: exception classes
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
# Test: load_geodata with real tract file
# ---------------------------------------------------------------------------
class TestLoadGeodata:
    def test_load_tract_granularity(self):
        """Load tract geodata if the file exists."""
        tract_path = Path("data/geo/tracts.geojson")
        if not tract_path.exists():
            pytest.skip("Tract GeoJSON not available")

        from src.data_loader import load_geodata
        gdf = load_geodata("tract")
        assert len(gdf) > 0
        assert "GEOID" in gdf.columns
        assert "geometry" in gdf.columns

    def test_geoid_normalized_to_11_chars(self):
        tract_path = Path("data/geo/tracts.geojson")
        if not tract_path.exists():
            pytest.skip("Tract GeoJSON not available")

        from src.data_loader import load_geodata
        gdf = load_geodata("tract")
        for geoid in gdf["GEOID"]:
            assert len(str(geoid)) == 11

    def test_unknown_granularity_raises(self):
        from src.data_loader import load_geodata
        with pytest.raises(DataLoadError, match="Unknown granularity"):
            load_geodata("unknown")


# ---------------------------------------------------------------------------
# Test: load_geojson_dict
# ---------------------------------------------------------------------------
class TestLoadGeojsonDict:
    def test_returns_dict(self):
        tract_path = Path("data/geo/tracts.geojson")
        if not tract_path.exists():
            pytest.skip("Tract GeoJSON not available")

        from src.data_loader import load_geojson_dict
        geojson = load_geojson_dict("tract")
        assert isinstance(geojson, dict)
        assert "features" in geojson
        assert len(geojson["features"]) > 0

    def test_geoid_normalized_in_features(self):
        tract_path = Path("data/geo/tracts.geojson")
        if not tract_path.exists():
            pytest.skip("Tract GeoJSON not available")

        from src.data_loader import load_geojson_dict
        geojson = load_geojson_dict("tract")
        for feature in geojson["features"]:
            geoid = feature["properties"].get("GEOID", "")
            if geoid:
                assert len(geoid) == 11
