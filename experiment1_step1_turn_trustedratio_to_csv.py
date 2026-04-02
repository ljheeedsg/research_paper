import json
import csv
import os

def load_trusted_ratio(filepath):
    """加载 JSON 文件，返回 {round: ratio} 字典"""
    if not os.path.exists(filepath):
        print(f"警告: 文件 {filepath} 不存在，跳过")
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"警告: {filepath} 格式错误，应为列表")
        return {}
    ratio_dict = {}
    for item in data:
        round_num = item.get('round')
        ratio = item.get('cumulative_trusted_ratio')
        if round_num is not None and ratio is not None:
            ratio_dict[round_num] = ratio
    return ratio_dict

def main():
    # 定义文件名映射
    files = {
        'B1': 'experiment1_step1_B1_trusted_ratio_per_round.json',
        'B2': 'experiment1_step1_B2_trusted_ratio_per_round.json',
        'B3': 'experiment1_step1_B3_trusted_ratio_per_round.json',
        'B4': 'experiment1_step1_B4_trusted_ratio_per_round.json',
        'OURS': 'experiment1_step1_ours_trusted_ratio_per_round.json'
    }

    # 加载所有数据
    data_dict = {}
    all_rounds = set()
    for scheme, fname in files.items():
        ratio_dict = load_trusted_ratio(fname)
        data_dict[scheme] = ratio_dict
        all_rounds.update(ratio_dict.keys())

    if not all_rounds:
        print("未找到任何有效数据，退出。")
        return

    # 按轮次排序
    sorted_rounds = sorted(all_rounds)

    # 准备CSV行
    rows = []
    for r in sorted_rounds:
        row = {'round': r}
        for scheme in files.keys():
            row[scheme] = data_dict[scheme].get(r, '')  # 缺失则留空
        rows.append(row)

    # 写入CSV
    output_file = 'experiment1_step1_trusted_ratio_compare.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['round'] + list(files.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV文件已保存: {output_file}")

if __name__ == '__main__':
    main()