import argparse

from experiment2_任务完成指标对比六种算法_common import (
    RESULTS_BUNDLE_FILE,
    RUNS_PER_ALGORITHM,
    ALGORITHM_NAMES,
    plot_all_figures,
    run_full_experiment,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithms", nargs="*", type=str, default=ALGORITHM_NAMES)
    parser.add_argument("--runs", type=int, default=RUNS_PER_ALGORITHM)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    bundle = run_full_experiment(
        algorithms=args.algorithms,
        runs_per_algorithm=args.runs,
        keep_temp=args.keep_temp,
    )
    plot_all_figures(bundle)
    print(f"\nSaved bundle: {RESULTS_BUNDLE_FILE}")


if __name__ == "__main__":
    main()
