from mizaj.agent.grounding import extract_numbers, find_ungrounded
from mizaj.agent.pricing import estimate_cost_usd


def test_extract_skips_iso_dates() -> None:
    nums = extract_numbers("On 2026-08-01 resting HR was 58.2 bpm")
    assert 58.2 in nums
    assert 2026 not in [int(n) for n in nums if float(n).is_integer()]


def test_ungrounded_detection() -> None:
    tools = [{"mean_a": 58.0, "mean_b": 55.0}]
    bad = find_ungrounded("It dropped to 12 bpm", tools)
    assert 12.0 in bad
    good = find_ungrounded("It dropped from 58 to 55", tools)
    assert good == []


def test_pricing_haiku() -> None:
    cost = estimate_cost_usd("claude-haiku-5-5", 100_000, 100_000)
    assert abs(cost - 0.06) < 1e-9
