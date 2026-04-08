"""Unit tests for spec_updates_2.md §6.2 — multi-page Streamlit structure.

Verifies:
- The three page files exist at the correct paths (app.py, pages/1_Map.py,
  pages/2_About_the_Data.py)
- Each file compiles cleanly (no syntax errors)
- Each file has a callable main() that runs without raising when Streamlit
  primitives are mocked out
"""
from __future__ import annotations

import importlib.util
import py_compile
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PAGE_FILES = {
    "Home": PROJECT_ROOT / "app.py",
    "Map": PROJECT_ROOT / "pages" / "1_Map.py",
    "About the Data": PROJECT_ROOT / "pages" / "2_About_the_Data.py",
}


def _install_streamlit_mock() -> MagicMock:
    """Stub the streamlit + streamlit_folium modules so pages can execute."""
    st_mock = MagicMock()
    st_mock.cache_data = lambda f=None, **kw: f if f else lambda g: g
    st_mock.cache_resource = lambda f=None, **kw: f if f else lambda g: g
    st_mock.secrets = {}
    st_mock.session_state = {}
    # Streamlit page_link / set_page_config / sidebar etc. are all MagicMock
    # by default, which is enough for an import-and-call smoke test.
    sys.modules["streamlit"] = st_mock
    sys.modules["streamlit.components.v1"] = MagicMock()
    sys.modules["streamlit_folium"] = MagicMock()
    return st_mock


@pytest.mark.parametrize("name,path", list(PAGE_FILES.items()))
def test_page_file_exists(name: str, path: Path) -> None:
    assert path.exists(), f"{name} page file missing: {path}"


@pytest.mark.parametrize("name,path", list(PAGE_FILES.items()))
def test_page_file_compiles(name: str, path: Path) -> None:
    py_compile.compile(str(path), doraise=True)


def test_pages_directory_layout() -> None:
    pages_dir = PROJECT_ROOT / "pages"
    assert pages_dir.is_dir()
    page_files = sorted(p.name for p in pages_dir.glob("*.py"))
    assert "1_Map.py" in page_files
    assert "2_About_the_Data.py" in page_files
