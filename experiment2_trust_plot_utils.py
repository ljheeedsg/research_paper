import csv
import json
from pathlib import Path


SERIES_CONFIG_TRUST = [
    {
        "label": "Trust-Aware",
        "csv_key": "cmab_trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
        "linestyle": "-",
        "linewidth": 2.1,
        "markersize": 4.2,
        "alpha": 0.98,
        "zorder": 4,
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
        "marker": "P",
        "linestyle": "-",
        "linewidth": 2.9,
        "markersize": 4.8,
        "alpha": 1.0,
        "zorder": 5,
    },
]


WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5


def load_worker_options():
    with Path(WORKER_OPTIONS_FILE).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


def build_initial_worker_states(worker_options):
    workers = {}
    for worker in worker_options.values():
        worker_id = int(worker["worker_id"])
        init_category = worker["init_category"]
        if init_category == "trusted":
            trust = TRUST_INIT_TRUSTED
            category = "trusted"
        else:
            trust = TRUST_INIT_UNKNOWN
            category = "unknown"

        workers[worker_id] = {
            "worker_id": worker_id,
            "init_category": init_category,
            "trust": float(trust),
            "category": category,
        }
    return workers


def _safe_mean(values):
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def compute_trust_series(round_results, initial_workers):
    workers = {
        worker_id: {
            "worker_id": item["worker_id"],
            "init_category": item["init_category"],
            "trust": float(item["trust"]),
            "category": item["category"],
        }
        for worker_id, item in initial_workers.items()
    }

    rounds = []
    avg_trust_true_trusted = []
    avg_trust_true_malicious = []
    trust_gap = []

    for round_result in round_results:
        for update in round_result.get("trust_update_records", []):
            worker_id = int(update["worker_id"])
            if worker_id not in workers:
                continue
            workers[worker_id]["trust"] = float(update["new_trust"])
            workers[worker_id]["category"] = update["new_category"]

        trusted_values = [
            item["trust"] for item in workers.values()
            if item["init_category"] == "trusted"
        ]
        malicious_values = [
            item["trust"] for item in workers.values()
            if item["init_category"] == "malicious"
        ]

        avg_trusted = _safe_mean(trusted_values)
        avg_malicious = _safe_mean(malicious_values)

        rounds.append(int(round_result["round_id"]))
        avg_trust_true_trusted.append(avg_trusted)
        avg_trust_true_malicious.append(avg_malicious)
        trust_gap.append(round(avg_trusted - avg_malicious, 4))

    return rounds, avg_trust_true_trusted, avg_trust_true_malicious, trust_gap


def compute_current_category_trust_series(round_results, initial_workers):
    workers = {
        worker_id: {
            "worker_id": item["worker_id"],
            "init_category": item["init_category"],
            "trust": float(item["trust"]),
            "category": item["category"],
        }
        for worker_id, item in initial_workers.items()
    }

    rounds = []
    avg_trust_current_trusted = []
    avg_trust_current_malicious = []
    trust_gap = []

    for round_result in round_results:
        for update in round_result.get("trust_update_records", []):
            worker_id = int(update["worker_id"])
            if worker_id not in workers:
                continue
            workers[worker_id]["trust"] = float(update["new_trust"])
            workers[worker_id]["category"] = update["new_category"]

        current_trusted_values = [
            item["trust"] for item in workers.values()
            if item["category"] == "trusted"
        ]
        current_malicious_values = [
            item["trust"] for item in workers.values()
            if item["category"] == "malicious"
        ]

        avg_trusted = _safe_mean(current_trusted_values)
        avg_malicious = _safe_mean(current_malicious_values)

        rounds.append(int(round_result["round_id"]))
        avg_trust_current_trusted.append(avg_trusted)
        avg_trust_current_malicious.append(avg_malicious)
        trust_gap.append(round(avg_trusted - avg_malicious, 4))

    return rounds, avg_trust_current_trusted, avg_trust_current_malicious, trust_gap


def save_plot_data_csv(output_csv, rounds, series_rows, series_config):
    headers = ["round"] + [config["csv_key"] for config in series_config]
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, round_id in enumerate(rounds):
            row = [round_id]
            for values in series_rows:
                row.append(values[idx])
            writer.writerow(row)
