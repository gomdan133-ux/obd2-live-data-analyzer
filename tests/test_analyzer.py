from pathlib import Path

import pytest

from obd2analyzer import analyze, load_log

LOGS = Path(__file__).resolve().parent.parent / "sample_logs"


def checks(name, disp=2.5):
    return {(f.check, f.severity) for f in analyze(load_log(LOGS / name), disp)}, analyze(load_log(LOGS / name), disp)


def test_healthy_log_has_no_warnings():
    _, findings = checks("healthy_2.5L.csv")
    assert [f for f in findings if f.severity != "INFO"] == []


def test_vacuum_leak_detected_as_idle_lean():
    _, findings = checks("vacuum_leak_2.5L.csv")
    trims = [f for f in findings if f.check == "fuel trim"]
    assert trims and "vacuum leak" in trims[0].suggestion


def test_stuck_thermostat_detected():
    found, _ = checks("stuck_thermostat_2.5L.csv")
    assert ("coolant temp", "WARN") in found


def _row(t, rpm=750, speed=0, coolant=90, stft=0, ltft=0, maf=2.5, o2=0.45):
    return dict(time_s=t, rpm=rpm, speed_mph=speed, coolant_c=coolant,
                stft_b1=stft, ltft_b1=ltft, maf_gs=maf, o2_b1s1_v=o2)


def test_overheat_is_critical():
    rows = [_row(t, coolant=95 + t) for t in range(20)]
    assert analyze(rows)[0].severity == "CRITICAL"


def test_low_maf_flagged():
    rows = [_row(t, maf=0.8, o2=0.2 if t % 2 else 0.8) for t in range(20)]
    assert any(f.check == "MAF" for f in analyze(rows, displacement_l=2.5))


def test_missing_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("time_s,rpm\n0,700\n")
    with pytest.raises(ValueError):
        load_log(p)
