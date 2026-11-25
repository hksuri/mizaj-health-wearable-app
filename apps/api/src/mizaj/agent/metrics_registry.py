from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricDef:
    name: str
    gold_table: str
    value_column: str
    unit: str
    default_aggregation: str
    valid_range: tuple[float, float] | None
    label: str
    supports_series: bool = True
    supports_sleep_tool: bool = False


METRICS: dict[str, MetricDef] = {
    m.name: m
    for m in [
        MetricDef(
            name="steps",
            gold_table="daily_summary",
            value_column="steps",
            unit="steps",
            default_aggregation="sum",
            valid_range=(0, 100_000),
            label="Steps",
        ),
        MetricDef(
            name="active_min",
            gold_table="daily_summary",
            value_column="active_min",
            unit="min",
            default_aggregation="sum",
            valid_range=(0, 1440),
            label="Active minutes",
        ),
        MetricDef(
            name="resting_hr_bpm",
            gold_table="daily_summary",
            value_column="resting_hr_bpm",
            unit="bpm",
            default_aggregation="mean",
            valid_range=(30, 120),
            label="Resting heart rate",
        ),
        MetricDef(
            name="sleep_min",
            gold_table="daily_summary",
            value_column="sleep_min",
            unit="min",
            default_aggregation="mean",
            valid_range=(0, 1440),
            label="Sleep duration",
            supports_sleep_tool=True,
        ),
        MetricDef(
            name="sleep_efficiency_pct",
            gold_table="daily_summary",
            value_column="sleep_efficiency_pct",
            unit="%",
            default_aggregation="mean",
            valid_range=(0, 100),
            label="Sleep efficiency",
            supports_sleep_tool=True,
        ),
    ]
}


def get_metric(name: str) -> MetricDef | None:
    return METRICS.get(name)


def registry_prompt_lines() -> list[str]:
    return [f"- {m.name} ({m.unit}): {m.label}" for m in METRICS.values()]
