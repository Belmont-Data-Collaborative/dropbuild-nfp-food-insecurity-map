from __future__ import annotations

"""Unit tests for src/config.py."""

import os
import sys
from unittest.mock import MagicMock

# Mock streamlit before importing src modules so config.py can load
# without a running Streamlit server.
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)

# Also mock optional deps that config.py does NOT import but guards against
# side-effects from other test imports.
sys.modules.setdefault("streamlit_folium", MagicMock())

from src import config  # noqa: E402


# ---------------------------------------------------------------------------
# Test: module imports without error
# ---------------------------------------------------------------------------
def test_config_imports():
    """config module should import cleanly."""
    assert config is not None


# ---------------------------------------------------------------------------
# Test: required constants exist
# ---------------------------------------------------------------------------
class TestRequiredConstants:
    def test_aws_bucket_name_exists(self):
        assert hasattr(config, "AWS_BUCKET_NAME")

    def test_s3_keys(self):
        assert hasattr(config, "S3_PARTNERS_KEY")
        assert hasattr(config, "S3_CENSUS_KEY")
        assert hasattr(config, "S3_CDC_PLACES_KEY")
        assert hasattr(config, "S3_GEOCODE_CACHE_KEY")

    def test_csv_column_lists(self):
        assert isinstance(config.PARTNERS_CSV_COLUMNS, list)
        assert isinstance(config.CENSUS_CSV_COLUMNS, list)
        assert isinstance(config.CDC_PLACES_CSV_COLUMNS, list)

    def test_partner_type_colors_has_8_entries(self):
        assert isinstance(config.PARTNER_TYPE_COLORS, dict)
        assert len(config.PARTNER_TYPE_COLORS) == 8

    def test_partner_type_labels_has_8_entries(self):
        assert isinstance(config.PARTNER_TYPE_LABELS, dict)
        assert len(config.PARTNER_TYPE_LABELS) == 8

    def test_partner_type_colors_keys_match_labels_keys(self):
        assert set(config.PARTNER_TYPE_COLORS.keys()) == set(
            config.PARTNER_TYPE_LABELS.keys()
        )

    def test_fallback_color(self):
        assert config.FALLBACK_COLOR == "#CCCCCC"

    def test_default_choropleth_layer(self):
        assert config.DEFAULT_CHOROPLETH_LAYER == "median_income"

    def test_davidson_center(self):
        assert isinstance(config.DAVIDSON_CENTER, list)
        assert len(config.DAVIDSON_CENTER) == 2
        assert all(isinstance(v, (int, float)) for v in config.DAVIDSON_CENTER)

    def test_default_zoom(self):
        assert isinstance(config.DEFAULT_ZOOM, int)
        assert config.DEFAULT_ZOOM == 11

    def test_cdc_places_indicator_column(self):
        assert config.CDC_PLACES_INDICATOR_COLUMN == "DIABETES_CrudePrev"

    def test_geojson_path(self):
        assert hasattr(config, "GEOJSON_PATH")
        assert isinstance(config.GEOJSON_PATH, str)

    def test_mock_data_dir(self):
        assert hasattr(config, "MOCK_DATA_DIR")

    def test_use_mock_data(self):
        assert hasattr(config, "USE_MOCK_DATA")
        assert isinstance(config.USE_MOCK_DATA, bool)

    def test_error_message_constants(self):
        assert hasattr(config, "ERROR_DATA_LOAD")
        assert hasattr(config, "ERROR_MISSING_COLUMN")
        assert hasattr(config, "WARNING_GEOCODE_FAILURES")
        assert hasattr(config, "WARNING_NO_GEOID_MATCH")


# ---------------------------------------------------------------------------
# Test: CHOROPLETH_LAYERS structure
# ---------------------------------------------------------------------------
class TestChoroplethLayers:
    REQUIRED_KEYS = {
        "id",
        "display_name",
        "csv_source",
        "csv_column",
        "unit_label",
        "format_string",
        "data_vintage_key",
    }

    def test_choropleth_layers_is_list(self):
        assert isinstance(config.CHOROPLETH_LAYERS, list)
        assert len(config.CHOROPLETH_LAYERS) >= 1

    def test_each_layer_has_required_keys(self):
        for layer in config.CHOROPLETH_LAYERS:
            missing = self.REQUIRED_KEYS - set(layer.keys())
            assert not missing, f"Layer {layer.get('id', '?')} missing keys: {missing}"

    def test_layer_ids_are_unique(self):
        ids = [layer["id"] for layer in config.CHOROPLETH_LAYERS]
        assert len(ids) == len(set(ids))

    def test_default_layer_id_exists(self):
        ids = [layer["id"] for layer in config.CHOROPLETH_LAYERS]
        assert config.DEFAULT_CHOROPLETH_LAYER in ids


# ---------------------------------------------------------------------------
# Test: specific color values from spec
# ---------------------------------------------------------------------------
class TestPartnerTypeColors:
    def test_school_summer_color(self):
        assert config.PARTNER_TYPE_COLORS["school_summer"] == "#E41A1C"

    def test_medical_health_color(self):
        assert config.PARTNER_TYPE_COLORS["medical_health"] == "#377EB8"

    def test_transitional_housing_color(self):
        assert config.PARTNER_TYPE_COLORS["transitional_housing"] == "#4DAF4A"

    def test_senior_services_color(self):
        assert config.PARTNER_TYPE_COLORS["senior_services"] == "#984EA3"

    def test_community_development_color(self):
        assert config.PARTNER_TYPE_COLORS["community_development"] == "#FF7F00"

    def test_homeless_outreach_color(self):
        assert config.PARTNER_TYPE_COLORS["homeless_outreach"] == "#A65628"

    def test_workforce_development_color(self):
        assert config.PARTNER_TYPE_COLORS["workforce_development"] == "#F781BF"

    def test_after_school_color(self):
        assert config.PARTNER_TYPE_COLORS["after_school"] == "#999999"
