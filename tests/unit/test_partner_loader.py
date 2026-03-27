"""Unit tests for src/partner_loader.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock streamlit
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())


class TestLoadPartners:
    def test_loads_from_geojson_if_exists(self):
        geojson_path = Path("data/points/partners.geojson")
        if not geojson_path.exists():
            pytest.skip("Partners GeoJSON not available")

        from src.partner_loader import load_partners
        gdf = load_partners()
        assert len(gdf) > 0
        assert "partner_name" in gdf.columns
        assert "partner_type" in gdf.columns
        assert "geometry" in gdf.columns

    def test_mock_fallback(self):
        """In mock mode, should fall back to CSV if GeoJSON missing."""
        from src.partner_loader import _load_from_mock_csv

        mock_path = Path("data/mock/mock_nfp_partners.csv")
        if not mock_path.exists():
            pytest.skip("Mock partner CSV not available")

        gdf = _load_from_mock_csv()
        assert len(gdf) > 0
        assert "partner_name" in gdf.columns
