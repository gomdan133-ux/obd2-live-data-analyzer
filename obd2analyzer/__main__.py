"""Command line: python -m obd2analyzer LOG.csv [--displacement 2.5]"""
import argparse

from .analyzer import analyze, load_log


def main():
    p = argparse.ArgumentParser(description="Flag abnormal conditions in an OBD-II live data CSV.")
    p.add_argument("log", help="CSV log file")
    p.add_argument("--displacement", type=float, help="engine size in liters (enables MAF check)")
    args = p.parse_args()

    rows = load_log(args.log)
    dur = rows[-1]["time_s"] - rows[0]["time_s"]
    print(f"{args.log}: {len(rows)} samples, {dur / 60:.1f} min")
    findings = analyze(rows, args.displacement)
    if not findings:
        print("No issues found by the current checks.")
    for f in findings:
        print(f)


if __name__ == "__main__":
    main()
