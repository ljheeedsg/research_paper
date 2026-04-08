# -*- coding: utf-8 -*-
"""
第一步：计算工人可选项集合与任务权重
输入：step6_worker_segments.json, step6_task_segments.json
输出：step7_worker_option_set.json, step7_task_weight_list.json
"""

import json
import random
from collections import defaultdict

# 固定随机种子，保证可重复
random.seed(42)

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def parse_worker_segments(segments_by_region):
    """
    将按区域分组的工人轨迹段，按工人序号聚合。
    工人序号从 vehicle_id 中提取（如 v00_000 -> 000）。
    """
    workers = defaultdict(list)
    for region_key, seg_list in segments_by_region.items():
        region = int(region_key.split('_')[1])          # 从 "region_0" 提取 0
        for seg in seg_list:
            vid = seg['vehicle_id']
            # 提取序号（假设格式 v00_000 或 000）
            if '_' in vid:
                idx = vid.split('_')[1]
            else:
                idx = vid
            workers[idx].append({
                'region_id': region,
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'cost': seg['cost'],
                'is_trusted': seg['is_trusted']
            })
    return workers

def parse_tasks(task_segments):
    """
    将按区域分组的任务窗口，平铺为任务列表。
    """
    tasks = []
    for region_key, task_list in task_segments.items():
        region = int(region_key.split('_')[1])
        for task in task_list:
            tasks.append({
                'task_id': task['task_id'],
                'region_id': region,
                'start_time': task['start_time'],
                'end_time': task['end_time'],
                'required_workers': task['required_workers']
            })
    return tasks

def generate_worker_options(workers, tasks):
    """
    为每个工人生成可覆盖任务列表。
    质量随机生成，成本 = 覆盖任务数 * 工人固定报价。
    """
    worker_options = []
    for worker_id, segs in workers.items():
        # 取第一个段的属性（假设同一工人所有段一致）
        is_trusted = segs[0]['is_trusted']
        base_cost = segs[0]['cost']

        covered = []
        for task in tasks:
            # 检查该工人是否有任何一段能覆盖该任务
            for seg in segs:
                if seg['region_id'] != task['region_id']:
                    continue
                if seg['start_time'] >= task['end_time'] or seg['end_time'] <= task['start_time']:
                    continue
                # 有覆盖，记录任务
                start = max(seg['start_time'], task['start_time'])
                end = min(seg['end_time'], task['end_time'])
                quality = random.uniform(0, 1)          # 随机质量
                covered.append({
                    'task_id': task['task_id'],
                    'quality': quality,
                    'task_price': base_cost,
                    'start_time': start,                # 实际可执行窗口起始
                    'end_time': end                     # 实际可执行窗口结束
                })
                break   # 一个任务只需记录一次

        total_cost = len(covered) * base_cost
        worker_options.append({
            'worker_id': worker_id,
            'is_trusted': is_trusted,
            'total_cost': total_cost,
            'covered_tasks': covered
        })
    return worker_options

def generate_task_weights(tasks):
    """
    生成任务权重字典，权重 = required_workers。
    """
    return {task['task_id']: task['required_workers'] for task in tasks}

def main():
    # 输入文件
    WORKER_SEGMENTS_FILE = 'experiment3_worker_segments.json'
    TASK_SEGMENTS_FILE = 'experiment3_task_segments.json'

    # 输出文件
    OUTPUT_WORKER_OPTIONS = 'step7_worker_option_set.json'
    OUTPUT_TASK_WEIGHTS = 'step7_task_weight_list.json'

    # 加载数据
    print("加载数据...")
    worker_segments = load_json(WORKER_SEGMENTS_FILE)
    task_segments = load_json(TASK_SEGMENTS_FILE)

    # 解析数据
    workers = parse_worker_segments(worker_segments)
    tasks = parse_tasks(task_segments)

    print(f"工人总数（实体车）: {len(workers)}")
    print(f"任务总数: {len(tasks)}")

    # 生成工人选项
    print("生成工人可选项...")
    worker_options = generate_worker_options(workers, tasks)
    save_json({'worker_options': worker_options}, OUTPUT_WORKER_OPTIONS)
    print(f"已保存 {OUTPUT_WORKER_OPTIONS}")

    # 生成任务权重
    task_weights = generate_task_weights(tasks)
    save_json({'task_weights': task_weights}, OUTPUT_TASK_WEIGHTS)
    print(f"已保存 {OUTPUT_TASK_WEIGHTS}")

    print("数据准备阶段完成。")

if __name__ == '__main__':
    main()