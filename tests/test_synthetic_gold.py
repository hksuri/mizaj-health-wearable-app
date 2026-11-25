from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from mizaj.data.gold_build import build_gold

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SILVER = ROOT / "tests" / "fixtures" / "synthetic" / "silver"


def test_fixture_silver_has_rows_and_low_nulls() -> None:
    assert FIXTURE_SILVER.exists(), "run make synth first to populate fixtures"
    daily_files = list((FIXTURE_SILVER / "daily_metrics").rglob("*.parquet"))
    sleep_files = list((FIXTURE_SILVER / "sleep_sessions").rglob("*.parquet"))
    assert daily_files
    assert sleep_files
    daily = pq.read_table(daily_files[0])
    for path in daily_files[1:]:
        daily = pa_concat(daily, pq.read_table(path))
    assert daily.num_rows >= 400
    null_steps = daily.column("steps").null_count
    assert null_steps == 0


def pa_concat(a, b):  # type: ignore[no-untyped-def]
    import pyarrow as pa

    return pa.concat_tables([a, b])


def test_gold_build_from_fixtures(tmp_path: Path) -> None:
    published = tmp_path / "health.duckdb"
    staging = tmp_path / "staging.duckdb"
    out = build_gold(
        silver_root=FIXTURE_SILVER,
        published_path=published,
        staging_path=staging,
    )
    assert out.exists()
    con = duckdb.connect(str(out), read_only=True)
    try:
        n = con.execute("SELECT count(*) FROM daily_summary").fetchone()
        assert n is not None and n[0] >= 400
        cov = con.execute("SELECT count(*) FROM coverage").fetchone()
        assert cov is not None and cov[0] == 5
        sleep_n = con.execute("SELECT count(*) FROM sleep_sessions").fetchone()
        assert sleep_n is not None and sleep_n[0] >= 400
    finally:
        con.close()
