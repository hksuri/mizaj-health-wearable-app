from __future__ import annotations

from typing import Any, Literal


def build_chart_spec(
    kind: Literal["line", "bar", "scatter"],
    title: str,
    rows: list[dict[str, Any]],
    y_label: str = "value",
    series_name: str = "Series",
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    if kind == "scatter":
        for row in rows:
            if row.get("x") is None or row.get("y") is None:
                continue
            points.append({"x": row["x"], "y": row["y"]})
    else:
        for row in rows:
            if row.get("date") is None or row.get("value") is None:
                continue
            points.append({"x": row["date"], "y": row["value"]})

    note = ""
    if len(points) > 400:
        # weekly downsample by taking every nth point as a simple cap
        step = max(1, len(points) // 400)
        points = points[::step][:400]
        note = " (downsampled)"

    return {
        "type": kind,
        "title": f"{title}{note}",
        "x": {"field": "date", "label": "Date", "kind": "time"},
        "y": {"label": y_label},
        "series": [{"name": series_name, "points": points}],
    }
