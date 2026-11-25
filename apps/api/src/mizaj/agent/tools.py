from __future__ import annotations

from datetime import date
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, Field

from mizaj.agent.metrics_registry import METRICS, get_metric

ErrorCode = Literal[
    "OUT_OF_COVERAGE",
    "UNKNOWN_METRIC",
    "INVALID_RANGE",
    "KIND_UNSUPPORTED",
    "SOURCE_NOT_FOUND",
    "INTERNAL",
]


class ToolError(BaseModel):
    ok: Literal[False] = False
    error_code: ErrorCode
    message: str


def _coverage(con: duckdb.DuckDBPyConnection, metric: str) -> tuple[date, date, int] | None:
    row = con.execute(
        "SELECT first_date, last_date, n_days FROM coverage WHERE metric = ?",
        [metric],
    ).fetchone()
    if not row or row[0] is None:
        return None
    return row[0], row[1], int(row[2])


def _ensure_metric_range(
    con: duckdb.DuckDBPyConnection, metric: str, start: date, end: date
) -> ToolError | None:
    if metric not in METRICS:
        return ToolError(error_code="UNKNOWN_METRIC", message=f"Unknown metric: {metric}")
    if start > end:
        return ToolError(error_code="INVALID_RANGE", message="start must be on or before end")
    cov = _coverage(con, metric)
    if cov is None:
        return ToolError(error_code="OUT_OF_COVERAGE", message=f"No coverage for {metric}")
    first, last, _ = cov
    if end < first or start > last:
        return ToolError(
            error_code="OUT_OF_COVERAGE",
            message=f"{metric} available {first} to {last}; requested {start} to {end}",
        )
    return None


def list_available_metrics(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = con.execute(
        """
        SELECT c.metric, c.first_date, c.last_date, c.n_days
        FROM coverage c
        ORDER BY c.metric
        """
    ).fetchall()
    metrics = []
    for metric, first, last, n_days in rows:
        meta = get_metric(metric)
        if meta is None:
            continue
        metrics.append(
            {
                "name": metric,
                "unit": meta.unit,
                "label": meta.label,
                "first_date": first.isoformat(),
                "last_date": last.isoformat(),
                "n_days": int(n_days),
            }
        )
    return {"metrics": metrics}


def get_metric_series(
    con: duckdb.DuckDBPyConnection,
    metric: str,
    start: date,
    end: date,
    granularity: Literal["day", "week"] = "day",
) -> dict[str, Any] | ToolError:
    err = _ensure_metric_range(con, metric, start, end)
    if err:
        return err
    meta = METRICS[metric]
    if granularity == "day":
        rows = con.execute(
            f"""
            SELECT date, {meta.value_column} AS value
            FROM daily_summary
            WHERE date BETWEEN ? AND ?
            ORDER BY date
            """,
            [start, end],
        ).fetchall()
        out_rows = []
        for d, value in rows:
            out_rows.append(
                {
                    "date": d.isoformat(),
                    "value": None if value is None else float(value),
                    "n_missing": 1 if value is None else 0,
                }
            )
    else:
        rows = con.execute(
            f"""
            SELECT date_trunc('week', date)::DATE AS week_start,
                   avg({meta.value_column}) AS value,
                   sum(CASE WHEN {meta.value_column} IS NULL THEN 1 ELSE 0 END) AS n_missing
            FROM daily_summary
            WHERE date BETWEEN ? AND ?
            GROUP BY 1
            ORDER BY 1
            """,
            [start, end],
        ).fetchall()
        out_rows = [
            {
                "date": d.isoformat(),
                "value": None if value is None else float(value),
                "n_missing": int(n_missing),
            }
            for d, value, n_missing in rows
        ]
    present = [r for r in out_rows if r["value"] is not None]
    return {
        "metric": metric,
        "unit": meta.unit,
        "granularity": granularity,
        "rows": out_rows,
        "n": len(present),
    }


def compare_periods(
    con: duckdb.DuckDBPyConnection,
    metric: str,
    a_start: date,
    a_end: date,
    b_start: date,
    b_end: date,
) -> dict[str, Any] | ToolError:
    err_a = _ensure_metric_range(con, metric, a_start, a_end)
    if err_a:
        return err_a
    err_b = _ensure_metric_range(con, metric, b_start, b_end)
    if err_b:
        return err_b
    meta = METRICS[metric]

    def _stats(start: date, end: date) -> tuple[float | None, int, int]:
        row = con.execute(
            f"""
            SELECT avg({meta.value_column}),
                   count({meta.value_column}),
                   sum(CASE WHEN {meta.value_column} IS NULL THEN 1 ELSE 0 END)
            FROM daily_summary
            WHERE date BETWEEN ? AND ?
            """,
            [start, end],
        ).fetchone()
        assert row is not None
        mean, n, missing = row
        return (None if mean is None else float(mean), int(n), int(missing or 0))

    mean_a, n_a, miss_a = _stats(a_start, a_end)
    mean_b, n_b, miss_b = _stats(b_start, b_end)
    abs_change = None if mean_a is None or mean_b is None else mean_b - mean_a
    pct_change = (
        None
        if mean_a is None or mean_b is None or mean_a == 0
        else (mean_b - mean_a) / abs(mean_a) * 100
    )
    return {
        "metric": metric,
        "unit": meta.unit,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "abs_change": abs_change,
        "pct_change": pct_change,
        "n_a": n_a,
        "n_b": n_b,
        "n_missing_a": miss_a,
        "n_missing_b": miss_b,
    }


def get_baseline_and_anomalies(
    con: duckdb.DuckDBPyConnection,
    metric: str,
    window_days: int = 30,
) -> dict[str, Any] | ToolError:
    if metric not in METRICS:
        return ToolError(error_code="UNKNOWN_METRIC", message=f"Unknown metric: {metric}")
    if window_days < 7:
        return ToolError(error_code="INVALID_RANGE", message="window_days must be >= 7")
    meta = METRICS[metric]
    cov = _coverage(con, metric)
    if cov is None:
        return ToolError(error_code="OUT_OF_COVERAGE", message=f"No coverage for {metric}")
    _, last, _ = cov
    start = date.fromordinal(last.toordinal() - window_days + 1)
    row = con.execute(
        """
        SELECT mean_30d, std_30d FROM baselines
        WHERE metric = ? AND date = ?
        """,
        [metric, last],
    ).fetchone()
    if row is None or row[0] is None:
        return ToolError(error_code="INTERNAL", message="Baseline unavailable")
    mean_30d, std_30d = float(row[0]), float(row[1] or 0)
    series = con.execute(
        f"""
        SELECT date, {meta.value_column} AS value
        FROM daily_summary
        WHERE date BETWEEN ? AND ? AND {meta.value_column} IS NOT NULL
        ORDER BY date
        """,
        [start, last],
    ).fetchall()
    flagged = []
    if std_30d > 0:
        for d, value in series:
            z = (float(value) - mean_30d) / std_30d
            if abs(z) >= 2.0:
                flagged.append(
                    {"date": d.isoformat(), "value": float(value), "z_score": round(z, 2)}
                )
    return {
        "metric": metric,
        "baseline_mean": mean_30d,
        "baseline_std": std_30d,
        "flagged": flagged,
    }


def get_sleep_summary(
    con: duckdb.DuckDBPyConnection, start: date, end: date
) -> dict[str, Any] | ToolError:
    err = _ensure_metric_range(con, "sleep_min", start, end)
    if err:
        return err
    rows = con.execute(
        """
        SELECT local_date, duration_min, deep_min, rem_min, light_min, awake_min, efficiency_pct
        FROM sleep_sessions
        WHERE local_date BETWEEN ? AND ?
        ORDER BY local_date
        """,
        [start, end],
    ).fetchall()
    nights = [
        {
            "date": d.isoformat(),
            "duration_min": float(duration),
            "deep_min": None if deep is None else float(deep),
            "rem_min": None if rem is None else float(rem),
            "light_min": None if light is None else float(light),
            "awake_min": None if awake is None else float(awake),
            "efficiency_pct": None if eff is None else float(eff),
        }
        for d, duration, deep, rem, light, awake, eff in rows
    ]
    n = len(nights)
    averages = {
        "duration_min": sum(n["duration_min"] for n in nights) / n if n else None,
        "efficiency_pct": (sum(n["efficiency_pct"] or 0 for n in nights) / n if n else None),
    }
    # calendar nights in range minus present
    calendar_days = (end - start).days + 1
    return {
        "nights": nights,
        "averages": averages,
        "n": n,
        "n_missing": max(0, calendar_days - n),
    }


def correlate_metrics(
    con: duckdb.DuckDBPyConnection,
    metric_x: str,
    metric_y: str,
    start: date,
    end: date,
) -> dict[str, Any] | ToolError:
    for metric in (metric_x, metric_y):
        err = _ensure_metric_range(con, metric, start, end)
        if err:
            return err
    mx = METRICS[metric_x]
    my = METRICS[metric_y]
    rows = con.execute(
        f"""
        SELECT a.{mx.value_column} AS x, b.{my.value_column} AS y
        FROM daily_summary a
        JOIN daily_summary b USING (date)
        WHERE a.date BETWEEN ? AND ?
          AND a.{mx.value_column} IS NOT NULL
          AND b.{my.value_column} IS NOT NULL
        """,
        [start, end],
    ).fetchall()
    n = len(rows)
    if n < 5:
        return {
            "metric_x": metric_x,
            "metric_y": metric_y,
            "spearman_r": None,
            "n": n,
            "caveat": "Too few paired days for a stable correlation.",
        }
    # Spearman via rank correlation in SQL-ish Python
    xs = [float(r[0]) for r in rows]
    ys = [float(r[1]) for r in rows]

    def rank(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        for r, i in enumerate(order, start=1):
            ranks[i] = float(r)
        return ranks

    rx, ry = rank(xs), rank(ys)
    mean_x, mean_y = sum(rx) / n, sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    den_x = sum((a - mean_x) ** 2 for a in rx) ** 0.5
    den_y = sum((b - mean_y) ** 2 for b in ry) ** 0.5
    r = None if den_x == 0 or den_y == 0 else num / (den_x * den_y)
    return {
        "metric_x": metric_x,
        "metric_y": metric_y,
        "spearman_r": None if r is None else round(r, 3),
        "n": n,
        "caveat": "Correlation is not causation; wearable gaps can bias the estimate.",
    }


class RenderChartInput(BaseModel):
    source_call_id: str
    kind: Literal["line", "bar", "scatter"]
    title: str = Field(min_length=1)


def render_chart_ack(
    source_rows_kind: Literal["series", "pairs", "sleep", "unknown"],
    kind: Literal["line", "bar", "scatter"],
) -> dict[str, Any] | ToolError:
    allowed = {
        "series": {"line", "bar"},
        "pairs": {"scatter"},
        "sleep": {"bar", "line"},
        "unknown": set(),
    }
    if kind not in allowed.get(source_rows_kind, set()):
        return ToolError(
            error_code="KIND_UNSUPPORTED",
            message=f"Chart kind {kind!r} unsupported for source shape {source_rows_kind!r}",
        )
    return {"ok": True, "chart_queued": True}
