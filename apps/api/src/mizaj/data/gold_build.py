"""Build gold DuckDB from silver Parquet with atomic publish (HLD D12)."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SILVER = ROOT / "data" / "silver"
DEFAULT_PUBLISHED = ROOT / "data" / "health.duckdb"
DEFAULT_STAGING = ROOT / "data" / "_staging" / "health.duckdb"


def build_gold(
    silver_root: Path | None = None,
    published_path: Path | None = None,
    staging_path: Path | None = None,
) -> Path:
    silver_root = silver_root or DEFAULT_SILVER
    published_path = published_path or DEFAULT_PUBLISHED
    staging_path = staging_path or DEFAULT_STAGING

    daily_glob = str(silver_root / "daily_metrics" / "month=*" / "*.parquet")
    sleep_glob = str(silver_root / "sleep_sessions" / "month=*" / "*.parquet")

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    if staging_path.exists():
        staging_path.unlink()

    con = duckdb.connect(str(staging_path))
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE daily_summary AS
            SELECT
              local_date AS date,
              steps,
              active_min,
              resting_hr_bpm,
              CAST(NULL AS DOUBLE) AS sleep_min,
              CAST(NULL AS DOUBLE) AS sleep_efficiency_pct
            FROM read_parquet('{daily_glob}')
            """
        )
        con.execute(
            f"""
            UPDATE daily_summary d
            SET
              sleep_min = s.duration_min,
              sleep_efficiency_pct = s.efficiency_pct
            FROM (
              SELECT local_date, duration_min, efficiency_pct
              FROM read_parquet('{sleep_glob}')
            ) s
            WHERE d.date = s.local_date
            """
        )
        con.execute(
            f"""
            CREATE OR REPLACE TABLE sleep_sessions AS
            SELECT * FROM read_parquet('{sleep_glob}')
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE coverage AS
            SELECT 'steps' AS metric, min(date) AS first_date, max(date) AS last_date,
                   count(steps) AS n_days FROM daily_summary WHERE steps IS NOT NULL
            UNION ALL
            SELECT 'active_min', min(date), max(date), count(active_min)
            FROM daily_summary WHERE active_min IS NOT NULL
            UNION ALL
            SELECT 'resting_hr_bpm', min(date), max(date), count(resting_hr_bpm)
            FROM daily_summary WHERE resting_hr_bpm IS NOT NULL
            UNION ALL
            SELECT 'sleep_min', min(date), max(date), count(sleep_min)
            FROM daily_summary WHERE sleep_min IS NOT NULL
            UNION ALL
            SELECT 'sleep_efficiency_pct', min(date), max(date), count(sleep_efficiency_pct)
            FROM daily_summary WHERE sleep_efficiency_pct IS NOT NULL
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE baselines AS
            WITH metrics AS (
              SELECT date, 'steps' AS metric, CAST(steps AS DOUBLE) AS value FROM daily_summary
              UNION ALL
              SELECT date, 'active_min', CAST(active_min AS DOUBLE) FROM daily_summary
              UNION ALL
              SELECT date, 'resting_hr_bpm', resting_hr_bpm FROM daily_summary
              UNION ALL
              SELECT date, 'sleep_min', sleep_min FROM daily_summary
            )
            SELECT
              metric,
              date,
              avg(value) OVER (
                PARTITION BY metric ORDER BY date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
              ) AS mean_7d,
              avg(value) OVER (
                PARTITION BY metric ORDER BY date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
              ) AS mean_30d,
              stddev_samp(value) OVER (
                PARTITION BY metric ORDER BY date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
              ) AS std_30d
            FROM metrics
            WHERE value IS NOT NULL
            """
        )
    finally:
        con.close()

    published_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_path, published_path)
    return published_path
