import json
import csv

def extract_platform_utility(filepath, scheme_name):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('platform_utility', None)
    except Exception as e:
        print(f"读取 {filepath} 失败: {e}")
        return None

def main():
    # 方案文件名映射
    files = {
        'B1': 'step9_final_result_B1.json',
        'B2': 'step9_final_result_B2.json',
        'B3': 'step9_final_result_B3.json',
        'B4': 'step9_final_result_B4.json',
        'OURS': 'step9_final_result_ours.json'
    }
    results = []
    for scheme, fname in files.items():
        value = extract_platform_utility(fname, scheme)
        results.append({'scheme': scheme, 'platform_utility': value})

    # 写入 CSV
    output_file = 'experiment1_step1_platform_utility.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['scheme', 'platform_utility'])
        writer.writeheader()
        writer.writerows(results)

    print(f"已生成 CSV 文件: {output_file}")

if __name__ == '__main__':
    main()