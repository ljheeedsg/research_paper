from experiment2_重构_main import build_config, run_experiment, run_single_experiment as _run_single


MODE = "lgsc"


def run_single_experiment(seed):
    config = build_config(MODE)
    return _run_single(MODE, seed, config)


def main():
    run_experiment(MODE)


if __name__ == "__main__":
    main()
