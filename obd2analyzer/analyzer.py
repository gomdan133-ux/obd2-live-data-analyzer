"""Rule-based checks on OBD-II live data.

Expected CSV columns (extra columns are ignored):
    time_s, rpm, speed_mph, coolant_c, stft_b1, ltft_b1, maf_gs, o2_b1s1_v

Thresholds are common shop rules of thumb, not factory specs.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ["time_s", "rpm", "speed_mph", "coolant_c", "stft_b1", "ltft_b1", "maf_gs", "o2_b1s1_v"]

TRIM_LIMIT = 10.0           # % total trim (STFT + LTFT)
WARM_C = 80.0               # engine considered warm
OVERHEAT_C = 110.0
THERMOSTAT_WINDOW_S = 600   # should be warm within 10 min of driving
IDLE_RPM_MAX = 1000
MAF_IDLE_MIN_PER_L = 0.6    # g/s per liter of displacement at idle (rule of thumb ~1 g/s/L)
O2_LEAN_V, O2_RICH_V = 0.30, 0.60


@dataclass
class Finding:
    severity: str   # INFO, WARN, CRITICAL
    check: str
    message: str
    suggestion: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check}: {self.message}\n    -> {self.suggestion}"


def load_log(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"log is missing columns: {', '.join(missing)}")
        rows = [{k: float(r[k]) for k in REQUIRED} for r in reader]
    if not rows:
        raise ValueError("log has no data rows")
    return rows


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _warm(rows):
    return [r for r in rows if r["coolant_c"] >= WARM_C]


def _idle(rows):
    return [r for r in rows if r["speed_mph"] < 1 and 0 < r["rpm"] <= IDLE_RPM_MAX]


def check_fuel_trims(rows) -> list[Finding]:
    warm = _warm(rows)
    if not warm:
        return []
    total = lambda r: r["stft_b1"] + r["ltft_b1"]  # noqa: E731
    idle = _idle(warm)
    cruise = [r for r in warm if r["rpm"] > 1800]
    idle_t = _mean([total(r) for r in idle])
    cruise_t = _mean([total(r) for r in cruise])
    overall = _mean([total(r) for r in warm])
    out = []
    if overall is not None and overall > TRIM_LIMIT or (idle_t or 0) > TRIM_LIMIT:
        if idle_t is not None and cruise_t is not None and idle_t > TRIM_LIMIT and cruise_t < idle_t - 5:
            out.append(Finding("WARN", "fuel trim",
                               f"Lean at idle (total trim {idle_t:+.1f}%) that improves at cruise ({cruise_t:+.1f}%).",
                               "Pattern fits a vacuum leak (unmetered air matters most at low airflow). Smoke test the intake and PCV hoses."))
        else:
            out.append(Finding("WARN", "fuel trim",
                               f"Lean across the RPM range (average total trim {overall:+.1f}%).",
                               "Check fuel pressure/volume and MAF accuracy before replacing O2 sensors."))
    elif overall is not None and overall < -TRIM_LIMIT:
        out.append(Finding("WARN", "fuel trim",
                           f"Running rich (average total trim {overall:+.1f}%).",
                           "Check for leaking injectors, high fuel pressure, or a contaminated/biased sensor."))
    return out


def check_coolant(rows) -> list[Finding]:
    out = []
    peak = max(r["coolant_c"] for r in rows)
    if peak >= OVERHEAT_C:
        out.append(Finding("CRITICAL", "coolant temp", f"Coolant reached {peak:.0f} C.",
                           "Stop driving. Check coolant level, cooling fan operation, water pump and for combustion gas in coolant."))
    duration = rows[-1]["time_s"] - rows[0]["time_s"]
    if duration >= THERMOSTAT_WINDOW_S:
        start = rows[0]["time_s"]
        after = [r["coolant_c"] for r in rows if r["time_s"] - start >= THERMOSTAT_WINDOW_S]
        if after and max(after) < WARM_C:
            out.append(Finding("WARN", "coolant temp",
                               f"Engine never reached {WARM_C:.0f} C after {THERMOSTAT_WINDOW_S // 60} min (max {max(after):.0f} C).",
                               "Likely thermostat stuck open (P0128). Verify the ECT reading with an IR thermometer first."))
    return out


def check_maf(rows, displacement_l: float | None) -> list[Finding]:
    if not displacement_l:
        return []
    idle = _idle(_warm(rows))
    avg = _mean([r["maf_gs"] for r in idle])
    if avg is None:
        return []
    floor = MAF_IDLE_MIN_PER_L * displacement_l
    if avg < floor:
        return [Finding("WARN", "MAF", f"Warm idle MAF {avg:.1f} g/s is low for a {displacement_l:.1f} L engine (expect about {displacement_l:.1f} g/s).",
                        "Possible contaminated MAF or air entering after the MAF. Inspect the intake duct and clean/test the MAF.")]
    return []


def check_o2(rows) -> list[Finding]:
    warm = [r for r in _warm(rows) if r["rpm"] > 0]
    if len(warm) < 10:
        return []
    v = [r["o2_b1s1_v"] for r in warm]
    crossings = sum(1 for a, b in zip(v, v[1:]) if (a - 0.45) * (b - 0.45) < 0)
    if max(v) < O2_LEAN_V:
        return [Finding("WARN", "O2 sensor", "Upstream O2 stays below 0.30 V (always lean).",
                        "Confirm with fuel trims: if trims are also high, the engine is really lean. If trims are normal, test the sensor.")]
    if min(v) > O2_RICH_V:
        return [Finding("WARN", "O2 sensor", "Upstream O2 stays above 0.60 V (always rich).",
                        "Check for a rich condition (injectors, fuel pressure) or a contaminated sensor.")]
    if crossings < 2:
        return [Finding("INFO", "O2 sensor", "Upstream O2 barely switches while warm.",
                        "May be a slow/aging sensor or an open-loop log. Check at 2500 RPM in closed loop.")]
    return []


def analyze(rows, displacement_l: float | None = None) -> list[Finding]:
    findings = []
    findings += check_coolant(rows)
    findings += check_fuel_trims(rows)
    findings += check_maf(rows, displacement_l)
    findings += check_o2(rows)
    order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    return sorted(findings, key=lambda f: order[f.severity])
