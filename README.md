# OBD-II Live Data Analyzer

A Python command-line tool that reads an OBD-II live data log (CSV export from a scan tool) and flags abnormal conditions the way a technician would read them, with a likely cause and a next test for each finding.

No dependencies beyond the Python standard library.

## What it checks

| Check | Rule | What it suggests |
|---|---|---|
| Overheating | Coolant ≥ 110 °C | Stop driving; cooling fan, level, water pump, head gasket |
| Thermostat | Not at 80 °C after 10 min | Thermostat stuck open (P0128); verify ECT with IR thermometer |
| Fuel trims (lean, idle only) | Total trim > +10% at idle, better at cruise | Vacuum leak; smoke test |
| Fuel trims (lean, everywhere) | Total trim > +10% across RPM | Fuel delivery or MAF |
| Fuel trims (rich) | Total trim < −10% | Injectors, fuel pressure |
| MAF at idle | Below ~0.6 g/s per liter | Dirty MAF or air leak after the MAF |
| Upstream O2 | Stuck lean, stuck rich, or not switching | Confirm against trims before replacing the sensor |

Thresholds are common shop rules of thumb, not factory specs. Each finding tells you what to test next instead of just naming a part, because a code or a number by itself is not a diagnosis.

## Usage

```bash
python -m obd2analyzer sample_logs/vacuum_leak_2.5L.csv --displacement 2.5
```

```
sample_logs/vacuum_leak_2.5L.csv: 181 samples, 15.0 min
[WARN] fuel trim: Lean at idle (total trim +20.7%) that improves at cruise (+4.2%).
    -> Pattern fits a vacuum leak (unmetered air matters most at low airflow). Smoke test the intake and PCV hoses.
```

### Log format

CSV with these columns (extra columns are ignored):

```
time_s, rpm, speed_mph, coolant_c, stft_b1, ltft_b1, maf_gs, o2_b1s1_v
```

Most scan tools (Torque Pro, OBDLink, BlueDriver, Autel) can export live data to CSV. Rename the columns to match.

## Sample logs

`sample_logs/` contains **synthetic** logs made by `scripts/make_sample_logs.py`: a healthy engine, a vacuum leak, and a stuck-open thermostat. They're simulated so the tests are repeatable. Real logs from customer vehicles (VINs removed) are the next step.

## Tests

```bash
pip install pytest
pytest -q
```

## Roadmap

- Bank 2 trims and V-engine bank comparison
- Downstream O2 / catalyst efficiency check
- Misfire counters
- Plot output (matplotlib)

## How this was built

1. **Turned shop rules of thumb into code.** I took the checks I run in my head while reading live data (fuel trim totals, idle vs cruise trims, warm-up time, idle MAF per liter, O2 switching) and wrote each one as a separate rule in `analyzer.py`.
2. **Made findings actionable.** Each finding has a severity (INFO, WARN, CRITICAL), what was seen, and the next test to run. For example, lean at idle but fine at cruise leads to a smoke test, not a new O2 sensor.
3. **Used only the standard library.** The tool needs nothing but Python, so it runs on any shop laptop. It reads plain CSV exports from common scan tools.
4. **Generated test logs.** `scripts/make_sample_logs.py` creates three synthetic 15-minute drives (healthy, vacuum leak, stuck-open thermostat) so the tests give the same result every run. They're labeled as synthetic, not real vehicle data.
5. **Tested it.** 6 pytest tests cover the sample logs, overheating, low MAF and bad input files. All pass, and the README output comes from real runs.

## License

MIT
