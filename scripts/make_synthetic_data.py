"""Generate 18 months of synthetic daily + sleep data for persona synthetic_v1."""

from __future__ import annotations

import math
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
PERSONA = "synthetic_v1"
MONTHS = 18


def _daterange(start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def build_frames(end: date | None = None) -> tuple[pa.Table, pa.Table]:
    rng = np.random.default_rng(SEED)
    end = end or date.today()
    start = end - timedelta(days=30 * MONTHS)
    days = _daterange(start, end)

    # Inject ~21-day missing stretch near the middle
    miss_start = days[len(days) // 2]
    missing = {miss_start + timedelta(days=i) for i in range(21)}

    daily_rows: list[dict[str, object]] = []
    sleep_rows: list[dict[str, object]] = []
    now = datetime.now(UTC)

    for i, d in enumerate(days):
        if d in missing:
            continue
        # Seasonality + weekly pattern + noise
        seasonal = 8 * math.sin(2 * math.pi * i / 365)
        weekend = -1200 if d.weekday() >= 5 else 0
        steps = int(max(0, 8500 + seasonal * 80 + weekend + rng.normal(0, 1200)))
        active_min = int(max(0, 35 + seasonal + (10 if d.weekday() < 5 else -5) + rng.normal(0, 8)))
        resting = float(58 + 3 * math.sin(2 * math.pi * i / 365) + rng.normal(0, 1.5))
        # Inject a few anomalies
        if i % 97 == 0:
            resting += 12
        if i % 113 == 0:
            steps = int(steps * 0.35)

        daily_rows.append(
            {
                "local_date": d,
                "steps": steps,
                "active_min": active_min,
                "resting_hr_bpm": round(resting, 1),
                "source_bronze_paths": [f"synthetic/{PERSONA}/daily/{d.isoformat()}"],
                "ingested_at_utc": now,
            }
        )

        duration = float(420 + 30 * math.sin(2 * math.pi * i / 14) + rng.normal(0, 25))
        deep = max(0.0, duration * 0.18 + rng.normal(0, 8))
        rem = max(0.0, duration * 0.22 + rng.normal(0, 8))
        awake = max(0.0, 15 + rng.normal(0, 5))
        light = max(0.0, duration - deep - rem - awake)
        efficiency = float(min(100.0, max(70.0, 100 * (1 - awake / max(duration, 1)))))
        start_utc = datetime(d.year, d.month, d.day, 5, 30, tzinfo=UTC) - timedelta(
            minutes=duration
        )
        end_utc = start_utc + timedelta(minutes=duration)
        sleep_rows.append(
            {
                "session_id": f"syn-{d.isoformat()}",
                "local_date": d,
                "start_utc": start_utc,
                "end_utc": end_utc,
                "duration_min": round(duration, 1),
                "deep_min": round(deep, 1),
                "rem_min": round(rem, 1),
                "light_min": round(light, 1),
                "awake_min": round(awake, 1),
                "efficiency_pct": round(efficiency, 1),
                "ingested_at_utc": now,
            }
        )

    daily = pa.Table.from_pylist(daily_rows)
    sleep = pa.Table.from_pylist(sleep_rows)
    return daily, sleep


def write_silver(daily: pa.Table, sleep: pa.Table, silver_root: Path) -> None:
    if silver_root.exists():
        shutil.rmtree(silver_root)
    # Partition by month
    for table, name, date_col in (
        (daily, "daily_metrics", "local_date"),
        (sleep, "sleep_sessions", "local_date"),
    ):
        dates = table.column(date_col).to_pylist()
        months = sorted({(d.year, d.month) for d in dates})
        for year, month in months:
            mask = [(d.year == year and d.month == month) for d in dates]
            part = table.filter(pa.array(mask))
            out = silver_root / name / f"month={year:04d}-{month:02d}"
            out.mkdir(parents=True, exist_ok=True)
            pq.write_table(part, out / "part-000.parquet")


def write_fixture_copy(silver_root: Path, fixture_root: Path) -> None:
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    shutil.copytree(silver_root, fixture_root)


def main() -> None:
    data_silver = ROOT / "data" / "silver"
    fixture_silver = ROOT / "tests" / "fixtures" / "synthetic" / "silver"
    daily, sleep = build_frames()
    write_silver(daily, sleep, data_silver)
    write_fixture_copy(data_silver, fixture_silver)
    print(f"Wrote silver daily={daily.num_rows} sleep={sleep.num_rows} -> {data_silver}")
    print(f"Copied fixtures -> {fixture_silver}")


if __name__ == "__main__":
    main()
