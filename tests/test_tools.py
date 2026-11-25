from datetime import date
from pathlib import Path

import duckdb
import pytest

from mizaj.agent import tools
from mizaj.data.gold_build import build_gold

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SILVER = ROOT / "tests" / "fixtures" / "synthetic" / "silver"


@pytest.fixture(scope="module")
def gold_con(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    base = tmp_path_factory.mktemp("gold")
    published = build_gold(
        silver_root=FIXTURE_SILVER,
        published_path=base / "health.duckdb",
        staging_path=base / "staging.duckdb",
    )
    return duckdb.connect(str(published), read_only=True)


def test_list_available_metrics(gold_con: duckdb.DuckDBPyConnection) -> None:
    out = tools.list_available_metrics(gold_con)
    names = {m["name"] for m in out["metrics"]}
    assert "steps" in names
    assert "resting_hr_bpm" in names


def test_get_metric_series_and_unknown(gold_con: duckdb.DuckDBPyConnection) -> None:
    cov = tools.list_available_metrics(gold_con)["metrics"]
    steps = next(m for m in cov if m["name"] == "steps")
    start = date.fromisoformat(steps["first_date"])
    end = date.fromisoformat(steps["last_date"])
    series = tools.get_metric_series(gold_con, "steps", start, end, "week")
    assert not isinstance(series, tools.ToolError)
    assert series["n"] > 0

    bad = tools.get_metric_series(gold_con, "not_a_metric", start, end)
    assert isinstance(bad, tools.ToolError)
    assert bad.error_code == "UNKNOWN_METRIC"


def test_out_of_coverage(gold_con: duckdb.DuckDBPyConnection) -> None:
    err = tools.get_metric_series(gold_con, "steps", date(1990, 1, 1), date(1990, 1, 31))
    assert isinstance(err, tools.ToolError)
    assert err.error_code == "OUT_OF_COVERAGE"


def test_compare_and_sleep_and_correlate(gold_con: duckdb.DuckDBPyConnection) -> None:
    cov = next(
        m for m in tools.list_available_metrics(gold_con)["metrics"] if m["name"] == "sleep_min"
    )
    first = date.fromisoformat(cov["first_date"])
    mid = date.fromordinal(first.toordinal() + 40)
    end = date.fromordinal(first.toordinal() + 70)
    cmp_ = tools.compare_periods(gold_con, "sleep_min", first, mid, mid, end)
    assert not isinstance(cmp_, tools.ToolError)
    assert cmp_["n_a"] > 0

    sleep = tools.get_sleep_summary(gold_con, first, end)
    assert not isinstance(sleep, tools.ToolError)
    assert sleep["n"] > 0

    corr = tools.correlate_metrics(gold_con, "steps", "resting_hr_bpm", first, end)
    assert not isinstance(corr, tools.ToolError)
    assert corr["n"] > 5


def test_baseline_and_chart_kind(gold_con: duckdb.DuckDBPyConnection) -> None:
    out = tools.get_baseline_and_anomalies(gold_con, "resting_hr_bpm", window_days=30)
    assert not isinstance(out, tools.ToolError)
    assert "baseline_mean" in out

    ok = tools.render_chart_ack("series", "line")
    assert not isinstance(ok, tools.ToolError)
    bad = tools.render_chart_ack("series", "scatter")
    assert isinstance(bad, tools.ToolError)
    assert bad.error_code == "KIND_UNSUPPORTED"
