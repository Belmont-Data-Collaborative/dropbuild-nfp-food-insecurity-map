"""Pipeline CLI entry point.

Usage:
    python -m pipeline                      # Run full pipeline
    python -m pipeline --step geo           # Download geographic data only
    python -m pipeline --step census_acs    # Process Census ACS only
    python -m pipeline --step health_lila   # Process CDC PLACES only
    python -m pipeline --step partners      # Process partner data only
    python -m pipeline --inspect census_acs # Inspect a data source
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root to path so we can import src and pipeline modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_loader import (
    get_data_sources,
    get_geography,
    get_granularities,
    get_partner_config,
)
from src import config
from pipeline.load_source import process_data_source
from pipeline.process_partners import run as run_partners

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure root logger."""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def run_geo_step() -> None:
    """Run geographic data processing script."""
    script = Path("scripts/process_geographic_data.py")
    if not script.exists():
        logger.error("Geographic data script not found: %s", script)
        sys.exit(1)

    logger.info("Running geographic data processing...")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Geographic data processing failed:\n%s", result.stderr)
        sys.exit(1)
    logger.info("Geographic data processing complete")
    if result.stdout:
        print(result.stdout)


def run_data_step(source_key: str) -> None:
    """Run a single data source processing step."""
    sources = get_data_sources()
    geography = get_geography()
    granularities = get_granularities()
    gran_lookup = {g["id"]: g for g in granularities}

    if source_key not in sources:
        logger.error("Unknown data source: %s", source_key)
        logger.info("Available sources: %s", list(sources.keys()))
        sys.exit(1)

    source_config = sources[source_key]

    for granularity in ["tract", "zip"]:
        logger.info("Processing %s / %s ...", source_key, granularity)
        gran_config = gran_lookup.get(granularity)
        process_data_source(
            source_key, source_config, geography, granularity,
            granularity_config=gran_config,
        )


def run_partners_step() -> None:
    """Run partner data processing pipeline."""
    partner_config = get_partner_config()
    use_mock = config.USE_MOCK_DATA
    mock_dir = config.MOCK_DATA_DIR

    run_partners(partner_config, use_mock, mock_dir)


def inspect_source(source_key: str) -> None:
    """Inspect a data source by printing its processed output."""
    import pandas as pd

    for granularity in ["tract", "zip"]:
        sources = get_data_sources()
        if source_key not in sources:
            print(f"Unknown source: {source_key}")
            return

        prefix = sources[source_key].get("output_prefix", source_key)
        path = f"data/choropleth/{prefix}_{granularity}_data.parquet"

        if not Path(path).exists():
            print(f"  {path}: not found (run pipeline first)")
            continue

        df = pd.read_parquet(path)
        print(f"\n=== {source_key} / {granularity} ===")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {list(df.columns)}")
        print(df.head())
        print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NFP Food Insecurity Map — Data Pipeline"
    )
    parser.add_argument(
        "--step",
        choices=["geo", "census_acs", "health_lila", "partners"],
        help="Run a specific pipeline step",
    )
    parser.add_argument(
        "--inspect",
        metavar="SOURCE",
        help="Inspect processed data for a source",
    )
    args = parser.parse_args()

    setup_logging()

    if args.inspect:
        inspect_source(args.inspect)
        return

    if args.step:
        if args.step == "geo":
            run_geo_step()
        elif args.step == "partners":
            run_partners_step()
        else:
            run_data_step(args.step)
        return

    # Full pipeline
    logger.info("Running full pipeline...")
    run_geo_step()

    sources = get_data_sources()
    for source_key in sources:
        run_data_step(source_key)

    run_partners_step()
    logger.info("Full pipeline complete")


if __name__ == "__main__":
    main()
