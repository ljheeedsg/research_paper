import json
import csv
import sys

def json_to_csv(json_file, csv_file):
    """
    将 OURS 实验输出的分类统计 JSON 文件转换为 CSV 格式。
    JSON 格式应为包含每轮记录的列表，每个记录包含 "round", "trusted_count", "unknown_count", "malicious_count"。
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：文件 {json_file} 不存在。")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误：文件 {json_file} 不是有效的 JSON 格式。")
        sys.exit(1)

    if not isinstance(data, list):
        print("错误：JSON 文件应包含一个列表。")
        sys.exit(1)

    # 检查每个记录是否包含必要字段
    required_keys = {'round', 'trusted_count', 'unknown_count', 'malicious_count'}
    for item in data:
        if not required_keys.issubset(item.keys()):
            print(f"错误：记录 {item} 缺少必要字段，需要包含 {required_keys}。")
            sys.exit(1)

    # 按轮次排序（可选）
    data_sorted = sorted(data, key=lambda x: x['round'])

    # 写入 CSV
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['round', 'trusted_count', 'unknown_count', 'malicious_count'])
        for item in data_sorted:
            writer.writerow([item['round'], item['trusted_count'], item['unknown_count'], item['malicious_count']])

    print(f"成功将 {json_file} 转换为 {csv_file}")

if __name__ == '__main__':
    # 默认输入输出文件
    input_file = 'experiment1_step1_worker_category.json'
    output_file = 'experiment1_step1_worker_category.csv'

    # 允许通过命令行参数指定输入输出
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    json_to_csv(input_file, output_file)