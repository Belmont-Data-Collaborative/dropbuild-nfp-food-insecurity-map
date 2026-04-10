"""Giving Matters pipeline step — graceful skip when data is unavailable.

Per spec_updates_2.md §3.3:
1. Returns None immediately when ``enabled: false`` in project.yml
2. Returns None gracefully if the S3 key does not exist
3. Otherwise, validates required columns and (eventually) geocodes addresses
   and writes ``data/points/giving_matters.geojson``

The Giving Matters dataset from CFMT has not yet been received. This module
defines the integration so the pipeline activates the moment the data is
uploaded to S3 and the schema is wired into ``required_columns``.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def process_giving_matters(source_config: dict[str, Any]) -> pd.DataFrame | None:
    """Run the Giving Matters pipeline step.

    Args:
        source_config: ``data_sources.giving_matters`` from project.yml.

    Returns:
        DataFrame of loaded organizations if data was processed, otherwise
        None (when disabled, when the S3 object is missing, or when the
        loaded CSV is missing required columns).
    """
    if not source_config.get("enabled", False):
        logger.info("Giving Matters integration is disabled — skipping")
        return None

    bucket = source_config.get("s3_bucket")
    s3_key = source_config.get("s3_key")
    if not bucket or not s3_key:
        logger.warning("giving_matters: missing s3_bucket or s3_key — skipping")
        return None

    s3 = boto3.client("s3")
    logger.info("Loading Giving Matters data from s3://%s/%s", bucket, s3_key)
    try:
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NoSuchBucket"}:
            logger.warning(
                "Giving Matters data not yet available at s3://%s/%s — skipping",
                bucket, s3_key,
            )
            return None
        logger.error("Failed to load Giving Matters data: %s", exc)
        return None
    except BotoCoreError as exc:
        logger.error("Failed to load Giving Matters data: %s", exc)
        return None

    df = pd.read_csv(io.BytesIO(obj["Body"].read()), low_memory=False)
    logger.info("Loaded %d Giving Matters rows", len(df))

    required = source_config.get("required_columns", {}) or {}
    missing = [c for c in required.values() if c and c not in df.columns]
    if missing:
        logger.error("Giving Matters: missing required columns: %s", missing)
        return None

    # Geocoding + GeoJSON output will be implemented once the column mapping
    # is finalized after data receipt. For now, return the loaded DataFrame
    # so callers can confirm the load path works end-to-end.
    Path("data/points").mkdir(parents=True, exist_ok=True)
    logger.info(
        "Giving Matters loaded successfully (%d rows). "
        "Geocoding step pending finalized schema.",
        len(df),
    )
    return df
