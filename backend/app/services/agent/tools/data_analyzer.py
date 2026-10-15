"""Real data_analyzer tool — statistics over validated numeric measurements.

Demo-safe synthetic Pump P-204 inspection measurements (clearly labeled).
No network I/O, no file I/O, no path parameters.
"""

from __future__ import annotations

import math
import re
from statistics import mean, median, stdev

class DataAnalyzerError(Exception):
    """Raised when analyzer input fails validation."""


MAX_SERIES = 20
MAX_POINTS = 5000
MAX_KEY_LEN = 64

_FORBIDDEN_KEY = re.compile(r"(\.\.|/|\\|\x00)")

# Demo-safe synthetic Pump P-204 inspection measurements (labeled synthetic).
DEMO_PUMP_P204_MEASUREMENTS: dict[str, list[float]] = {
    "temperature_c": [58.2, 59.1, 60.4, 61.0, 62.0, 63.5, 64.1, 65.0],
    "vibration_mm_s": [2.1, 2.3, 2.5, 2.8, 3.1, 3.4, 3.7, 4.0],
    "pressure_bar": [4.1, 4.2, 4.0, 4.3, 4.2, 4.1, 4.4, 4.2],
    "flow_rate_m3h": [84.0, 85.5, 86.2, 83.9, 87.1, 85.0, 84.5, 86.0],
    "current_amps": [12.2, 12.5, 12.4, 12.8, 13.0, 12.6, 12.9, 13.1],
}

_DEMO_DATASET_IDS = frozenset({"pump_p204_demo", "pump_p204", "demo"})


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not key or len(key) > MAX_KEY_LEN:
        raise DataAnalyzerError("Invalid series name")
    if _FORBIDDEN_KEY.search(key):
        raise DataAnalyzerError(f"Rejected path-like series name: {key!r}")


def _coerce_series(values: object, name: str) -> list[float]:
    if not isinstance(values, (list, tuple)):
        raise DataAnalyzerError(f"Series '{name}' must be a list of numbers")
    if len(values) == 0:
        raise DataAnalyzerError(f"Series '{name}' is empty")
    if len(values) > MAX_POINTS:
        raise DataAnalyzerError(
            f"Series '{name}' exceeds maximum of {MAX_POINTS} points"
        )
    out: list[float] = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise DataAnalyzerError(f"Series '{name}'[{i}] is not numeric")
        f = float(v)
        if not math.isfinite(f):
            raise DataAnalyzerError(f"Series '{name}'[{i}] is not finite")
        out.append(f)
    return out


def _demo_series() -> dict[str, list[float]]:
    return {k: list(v) for k, v in DEMO_PUMP_P204_MEASUREMENTS.items()}


def _extract_series(input_data: dict | None) -> dict[str, list[float]]:
    if input_data is None:
        input_data = {}
    if not isinstance(input_data, dict):
        raise DataAnalyzerError("input_data must be an object")

    dataset = input_data.get("dataset")
    if dataset is not None:
        if not isinstance(dataset, str) or dataset not in _DEMO_DATASET_IDS:
            raise DataAnalyzerError(f"Unknown dataset selector: {dataset!r}")
        return _demo_series()

    if "measurements" in input_data:
        return {"measurements": _coerce_series(input_data["measurements"], "measurements")}

    if "series" in input_data:
        series = input_data["series"]
        if not isinstance(series, dict):
            raise DataAnalyzerError("'series' must be an object mapping name → number list")
        if not series:
            raise DataAnalyzerError("'series' must not be empty")
        if len(series) > MAX_SERIES:
            raise DataAnalyzerError(f"Too many series (max {MAX_SERIES})")
        out: dict[str, list[float]] = {}
        for key, values in series.items():
            _validate_key(key)
            out[key] = _coerce_series(values, key)
        return out

    # Empty / metadata-only payload → demo-safe synthetic Pump P-204 set.
    if not input_data or set(input_data.keys()) <= {"dataset", "source", "label", "equipment"}:
        return _demo_series()

    # Top-level numeric lists treated as series (excluding reserved keys).
    reserved = {"dataset", "source", "label", "equipment", "task_id", "title", "purpose"}
    out = {}
    for key, values in input_data.items():
        if key in reserved:
            continue
        if isinstance(values, (list, tuple)):
            _validate_key(key)
            out[key] = _coerce_series(values, key)
    if not out:
        raise DataAnalyzerError(
            "No numeric series found; provide 'measurements', 'series', or omit input for demo data"
        )
    if len(out) > MAX_SERIES:
        raise DataAnalyzerError(f"Too many series (max {MAX_SERIES})")
    return out


def compute_stats(values: list[float]) -> dict[str, float | int]:
    n = len(values)
    result: dict[str, float | int] = {
        "count": n,
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
        "stdev": stdev(values) if n >= 2 else 0.0,
    }
    return result


def analyze(action: str, input_data: dict | None = None) -> str:
    """Run a real statistical analysis and return a human-readable report."""
    series = _extract_series(input_data)
    lines = [f"[DataAnalyzer] Analysis complete: {action}"]
    for name, values in series.items():
        s = compute_stats(values)
        lines.append(
            "series {name}: n={count} mean={mean:.4f} min={min:.4f} max={max:.4f} "
            "median={median:.4f} stdev={stdev:.4f}".format(name=name, **s)
        )
    lines.append("dataset: demo-safe synthetic Pump P-204 measurements (labeled synthetic)")
    return "\n".join(lines)
