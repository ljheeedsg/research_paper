import argparse
from experiment2_恶意比例鲁棒性_common import (
    MALICIOUS_RATIOS,
    RUNS_PER_RATIO,
    RESULTS_BUNDLE_FILE,
    plot_all_figures,
    run_full_experiment,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratios", nargs="*", type=float, default=MALICIOUS_RATIOS)
    parser.add_argument("--runs", type=int, default=RUNS_PER_RATIO)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    bundle = run_full_experiment(
        ratios=args.ratios,
        runs_per_ratio=args.runs,
        keep_temp=args.keep_temp,
    )
    plot_all_figures(bundle)
    print(f"\nSaved bundle: {RESULTS_BUNDLE_FILE}")


if __name__ == "__main__":
    main()
