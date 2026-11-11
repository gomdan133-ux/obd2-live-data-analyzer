"""Generate SYNTHETIC sample logs for demos and tests.

These are simulated, not recorded from a real vehicle. Replace or add to them
with your own scanner exports (remove the VIN first).

Usage: python scripts/make_sample_logs.py
"""
import csv
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "sample_logs"
COLS = ["time_s", "rpm", "speed_mph", "coolant_c", "stft_b1", "ltft_b1", "maf_gs", "o2_b1s1_v"]


def drive(seconds=900, step=5, *, thermostat_ok=True, idle_lean=0.0, seed=1):
    rnd = random.Random(seed)
    rows = []
    coolant = 25.0
    for t in range(0, seconds + 1, step):
        # 0-120 s idle, then cruise, last 120 s idle again
        idle = t < 120 or t > seconds - 120
        rpm = 750 + rnd.uniform(-30, 30) if idle else 2200 + rnd.uniform(-150, 150)
        speed = 0 if idle else 45 + rnd.uniform(-5, 5)
        target = 92 if thermostat_ok else 68
        coolant += (target - coolant) * 0.03 + rnd.uniform(-0.2, 0.2)
        warm = coolant >= 80 or not thermostat_ok
        lean = idle_lean if idle else idle_lean * 0.2
        stft = lean * 0.4 + rnd.uniform(-3, 3)
        ltft = lean * 0.6 + rnd.uniform(-1, 1)
        maf = (2.5 if idle else 12.0) + rnd.uniform(-0.3, 0.3)
        o2 = 0.45 + 0.4 * math.sin(t / 2.0) if warm else 0.45
        rows.append([t, round(rpm), round(speed, 1), round(coolant, 1),
                     round(stft, 1), round(ltft, 1), round(maf, 2), round(o2, 3)])
    return rows


def write(name, rows):
    OUT.mkdir(exist_ok=True)
    with (OUT / name).open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    print("wrote", OUT.name + "/" + name)


if __name__ == "__main__":
    write("healthy_2.5L.csv", drive())
    write("vacuum_leak_2.5L.csv", drive(idle_lean=20, seed=2))
    write("stuck_thermostat_2.5L.csv", drive(thermostat_ok=False, seed=3))
