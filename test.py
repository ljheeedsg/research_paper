import argparse
import csv
import json
from pathlib import Path


def json_to_csv(json_file, csv_file):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON 内容必须是列表。")

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "cumulative_trusted_ratio"])
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"第 {index} 项不是对象。")
            if "round" not in item or "cumulative_trusted_ratio" not in item:
                raise ValueError(
                    f"第 {index} 项缺少 'round' 或 'cumulative_trusted_ratio' 字段。"
                )
            writer.writerow([item["round"], item["cumulative_trusted_ratio"]])

    print(f"转换完成：{csv_file}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="将 cumulative_trusted_ratio 的 JSON 文件转换为 CSV。"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="experiment1_step1_B3_cumulative_trusted_ratio.json",
        help="输入 JSON 文件路径",
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        help="输出 CSV 文件路径；不传时默认与输入文件同名",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    json_path = Path(args.json_file)
    csv_path = Path(args.csv_file) if args.csv_file else json_path.with_suffix(".csv")
    json_to_csv(json_path, csv_path)
