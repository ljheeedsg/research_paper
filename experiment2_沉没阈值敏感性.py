import argparse

from experiment2_沉没阈值敏感性_common import (
    RESULTS_BUNDLE_FILE,
    RUNS_PER_VALUE,
    SUNK_THRESHOLD_VALUES,
    plot_all_figures,
    run_full_experiment,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--values", nargs="*", type=int, default=SUNK_THRESHOLD_VALUES)
    parser.add_argument("--runs", type=int, default=RUNS_PER_VALUE)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    bundle = run_full_experiment(
        sunk_threshold_values=args.values,
        runs_per_value=args.runs,
        keep_temp=args.keep_temp,
    )
    plot_all_figures(bundle)
    print(f"\nSaved bundle: {RESULTS_BUNDLE_FILE}")


if __name__ == "__main__":
    main()
