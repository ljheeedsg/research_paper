import json
import random


# ========== 可调参数 ==========
# 信任度参数（后续使用）
ETA = 0.2
THETA_HIGH = 0.8
THETA_LOW = 0.2
M = 3  # 每轮验证任务数
# =============================

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_worker_is_trusted(csv_file):
    """从 step1_vehicles.csv 读取每个工人的 is_trusted 字段（取第一个出现值）"""
    is_trusted_dict = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        header = f.readline().strip().split(',')
        idx_vehicle = header.index('vehicle_id')
        idx_trusted = header.index('is_trusted')
        for line in f:
            parts = line.strip().split(',')
            vid = parts[idx_vehicle]
            trusted = parts[idx_trusted] == 'True'
            if vid not in is_trusted_dict:
                is_trusted_dict[vid] = trusted
    return is_trusted_dict

def generate_task_data():
    """生成随机任务数据（均匀分布 [0,1]）"""
    return random.uniform(0, 1)

def main():
    # 加载已有数据
    worker_options_data = load_json('step2_worker_option_set.json')
    worker_options = worker_options_data['worker_options']
    task_segments = load_json('step1_task_segments.json')

    # 读取 is_trusted 信息
    is_trusted_dict = read_worker_is_trusted('step1_vehicles.csv')

    # 初始化工人档案（添加 trust, category, task_data）
    new_worker_options = []
    for w in worker_options:
        wid = w['worker_id']
        is_trusted = is_trusted_dict.get(wid, False)  # 默认 False
        if is_trusted:
            trust = 1.0
            category = 'trusted'
        else:
            trust = 0.5
            category = 'unknown'
        # 为每个覆盖任务添加随机 task_data
        new_tasks = []
        for task in w['covered_tasks']:
            new_task = task.copy()
            new_task['task_data'] = generate_task_data()
            new_tasks.append(new_task)
        new_worker_options.append({
            'worker_id': wid,
            'total_cost': w['total_cost'],
            'trust': trust,
            'category': category,
            'covered_tasks': new_tasks
        })

    # 生成任务网格映射（从 task_segments 读取 region_id）
    tasks_grid = []
    for region_id_str, task_list in task_segments.items():
        region_id = int(region_id_str.split('_')[1])
        for task in task_list:
            tasks_grid.append({'task_id': task['task_id'], 'grid_id': region_id})

    # 保存结果
    save_json({'worker_options': new_worker_options}, 'step3_worker_option_set.json')
    save_json(tasks_grid, 'step3_tasks_grid_num.json')
    print("step3_worker_option_set.json 和 step3_tasks_grid_num.json 已生成。")

if __name__ == '__main__':
    main()