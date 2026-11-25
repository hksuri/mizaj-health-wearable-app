from __future__ import annotations

import json
import re
from typing import Any

_NUM = re.compile(r"(?<![\w-])[-+]?\d+(?:\.\d+)?(?![\w-])")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_YEAR = re.compile(r"\b20\d{2}\b")


def extract_numbers(text: str) -> list[float]:
    cleaned = _ISO_DATE.sub(" ", text)
    # drop bare years loosely
    cleaned = _YEAR.sub(" ", cleaned)
    vals: list[float] = []
    for m in _NUM.finditer(cleaned):
        raw = m.group(0)
        # skip simple enumerations like "1." at line starts handled loosely by regex
        vals.append(float(raw))
    return vals


def numbers_from_tool_payloads(tool_results: list[Any]) -> list[float]:
    blob = json.dumps(tool_results, default=str)
    return extract_numbers(blob)


def find_ungrounded(answer: str, tool_results: list[Any]) -> list[float]:
    allowed = numbers_from_tool_payloads(tool_results)
    ungrounded: list[float] = []
    for num in extract_numbers(answer):
        if not any(_close(num, a) for a in allowed):
            ungrounded.append(num)
    return ungrounded


def _close(a: float, b: float) -> bool:
    if float(a).is_integer() and float(b).is_integer():
        return int(round(a)) == int(round(b))
    tol = max(0.5, abs(b) * 0.005)
    return abs(a - b) <= tol
