import json
import csv

def json_to_csv(json_file, csv_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 假设 data 是一个列表，每个元素包含 'round' 和 'cumulative_trusted_ratio'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['round', 'cumulative_trusted_ratio'])
        for item in data:
            writer.writerow([item['round'], item['cumulative_trusted_ratio']])
    
    print(f"转换完成：{csv_file}")

if __name__ == '__main__':
    json_to_csv('experiment1_step1_B3_cumulative_trusted_ratio.json', 'experiment1_step1_B3_cumulative_trusted_ratio.csv')