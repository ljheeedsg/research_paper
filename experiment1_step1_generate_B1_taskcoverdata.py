"""
B1 方案：随机招募 + 固定工资（无 CMAB、无信任、无 PGRD、无 LGSC）
输入：step6_worker_segments.json, step6_task_segments.json
输出：step9_worker_option_set_B1.json, step9_task_weight_list_B1.json,
      step9_tasks_grid_num_B1.json, step9_tasks_classification_B1.json,
      step9_final_result_B1.json, experiment1_step1_B1_taskcover.json
      experiment1_step1_B1_trusted_ratio_per_round.json（新增）
"""

"""
B1 方案：随机招募 + 固定工资（无 CMAB、无信任、无 PGRD、无 LGSC）
多次重复实验取平均，输出平均结果到原文件名。
"""

import json
import random
import math
import numpy as np
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42
BUDGET = 5000
K = 7
R = 24
M_VERIFY = 7

# 任务分类参数
MEMBER_RATIO = 0.5
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# 重复次数
NUM_SEEDS = 30   # 可调整

# ========== 工具函数 ==========
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========== 第一阶段：数据准备（同原代码） ==========
def parse_worker_segments(segments_by_region):
    workers = defaultdict(list)
    for region_key, seg_list in sorted(segments_by_region.items()):
        region = int(region_key.split('_')[1])
        for seg in seg_list:
            vid = seg['vehicle_id']
            idx = vid.split('_')[1] if '_' in vid else vid
            workers[idx].append({
                'region_id': region,
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'cost': seg['cost'],
                'is_trusted': seg['is_trusted']
            })
    return workers

def parse_tasks(task_segments):
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
    worker_options = []
    for worker_id, segs in workers.items():
        is_trusted = segs[0]['is_trusted']
        base_cost = segs[0]['cost']
        trust = 1.0 if is_trusted else 0.5
        category = 'trusted' if is_trusted else 'unknown'

        covered = []
        for task in tasks:
            for seg in segs:
                if seg['region_id'] != task['region_id']:
                    continue
                if seg['start_time'] >= task['end_time'] or seg['end_time'] <= task['start_time']:
                    continue
                start = max(seg['start_time'], task['start_time'])
                end = min(seg['end_time'], task['end_time'])
                quality = random.uniform(0, 1)
                task_data = random.uniform(0, 1)
                covered.append({
                    'task_id': task['task_id'],
                    'quality': quality,
                    'task_price': base_cost,
                    'start_time': start,
                    'end_time': end,
                    'task_start_time': task['start_time'],
                    'task_data': task_data
                })
                break
        total_cost = len(covered) * base_cost
        worker_options.append({
            'worker_id': worker_id,
            'is_trusted': is_trusted,
            'trust': trust,
            'category': category,
            'total_cost': total_cost,
            'covered_tasks': covered
        })
    return worker_options

def generate_task_weights(tasks):
    return {task['task_id']: task['required_workers'] for task in tasks}

def generate_task_grid_map(task_segments):
    grid_map = []
    for region_key, task_list in task_segments.items():
        region_id = int(region_key.split('_')[1])
        for task in task_list:
            grid_map.append({'task_id': task['task_id'], 'grid_id': region_id})
    return grid_map

def generate_task_classification(worker_options_path, task_segments_path, output_path):
    data = load_json(worker_options_path)
    worker_options = data['worker_options']
    task_segments = load_json(task_segments_path)

    all_task_ids = []
    for region_key, tasks in task_segments.items():
        for task in tasks:
            all_task_ids.append(task['task_id'])

    task_prices = defaultdict(list)
    for w in worker_options:
        for task in w['covered_tasks']:
            tid = task['task_id']
            task_prices[tid].append(task['task_price'])

    covered_task_ids = set(task_prices.keys())
    if not covered_task_ids:
        print("警告：没有任务被任何工人覆盖！")
        return

    tasks_info = []
    for tid in covered_task_ids:
        base_price = sum(task_prices[tid]) / len(task_prices[tid])
        tasks_info.append({'task_id': tid, 'base_price': base_price})

    tasks_info.sort(key=lambda x: x['base_price'], reverse=True)
    m = len(tasks_info)
    k = int(MEMBER_RATIO * m)

    final_tasks = []
    for idx, info in enumerate(tasks_info):
        tid = info['task_id']
        base_price = info['base_price']
        is_member = idx < k
        if is_member:
            task_price = base_price * MEMBER_MULTIPLIER
            cost_ratio = random.uniform(*MEMBER_COST_RANGE)
        else:
            task_price = base_price * NORMAL_MULTIPLIER
            cost_ratio = random.uniform(*NORMAL_COST_RANGE)

        worker_cost = task_price * cost_ratio
        system_income = task_price * random.uniform(*PROFIT_RANGE)
        pure_income = task_price - worker_cost

        final_tasks.append({
            'task_id': tid,
            'task_price': round(task_price, 2),
            'worker_cost': round(worker_cost, 2),
            'system_income': round(system_income, 2),
            'pure_worker_income': round(pure_income, 2),
            'type': 'member' if is_member else 'normal'
        })

    save_json(final_tasks, output_path)
    print(f"✅ 已生成任务分类 {output_path}，包含 {len(final_tasks)} 个任务（仅覆盖有工人覆盖的任务）")

def data_preparation(worker_segments_path, task_segments_path,
                     output_worker_options, output_task_weights,
                     output_task_grid, output_task_class):
    print("=== 第一阶段：数据准备 ===")
    worker_segments = load_json(worker_segments_path)
    task_segments = load_json(task_segments_path)

    workers = parse_worker_segments(worker_segments)
    tasks = parse_tasks(task_segments)
    print(f"工人总数（实体车）: {len(workers)}")
    print(f"任务总数: {len(tasks)}")

    worker_options = generate_worker_options(workers, tasks)
    save_json({'worker_options': worker_options}, output_worker_options)
    print(f"已保存 {output_worker_options}")

    task_weights = generate_task_weights(tasks)
    save_json({'task_weights': task_weights}, output_task_weights)
    print(f"已保存 {output_task_weights}")

    task_grid = generate_task_grid_map(task_segments)
    save_json(task_grid, output_task_grid)
    print(f"已保存 {output_task_grid}")

    generate_task_classification(output_worker_options, task_segments_path, output_task_class)

    return worker_options, tasks, task_weights, task_grid

# ========== 第二阶段：初始化 ==========
def initialize(worker_options_path, task_weights_path, task_class_path):
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)

    task_time_map = {}
    for w in workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            if tid not in task_time_map:
                task_time_map[tid] = task['task_start_time']

    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        w['avg_quality'] = sum(t['quality'] for t in w['covered_tasks']) / w['n_i'] if w['n_i'] > 0 else 0.0
        w['available_rounds'] = set()
        for t in w['covered_tasks']:
            hour = t['task_start_time'] // 3600
            w['available_rounds'].add(hour)

    task_covered_count = {tid: 0 for tid in task_time_map}
    required_workers = {tid: task_weights[tid] for tid in task_time_map}
    initial_Uc = {w['worker_id'] for w in workers if w['category'] == 'trusted'}
    initial_Uu = {w['worker_id'] for w in workers if w['category'] == 'unknown'}

    print(f"初始化完成，工人总数: {len(workers)}，初始可信工人: {len(initial_Uc)}，初始未知工人: {len(initial_Uu)}")

    return workers, task_covered_count, required_workers, task_time_map, initial_Uc

# ========== B1 主循环（不保存文件，返回数据） ==========
def greedy_recruitment_B1(workers, task_covered_count, required_workers, B, K, R, task_time_map, task_class, initial_Uc):
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    round_details = []

    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}
    task_price_map = {t['task_id']: t['task_price'] for t in task_class}
    total_system_income = 0.0

    task_coverage_records = []      # 每轮覆盖率
    cumulative_total = 0
    cumulative_trusted = 0
    cumulative_trusted_ratio = []   # 每轮累积占比

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if r in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 计算最小成本
        min_cost = float('inf')
        for w in available_workers:
            for task in w['covered_tasks']:
                if task['task_start_time'] // 3600 != r:
                    continue
                tid = task['task_id']
                if task_covered_count[tid] < required_workers[tid]:
                    price = task_price_map[tid]
                    if price < min_cost:
                        min_cost = price
        if min_cost == float('inf'):
            print("本轮没有可做的任务")
            break
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break

        if all(cnt >= required_workers[tid] for tid, cnt in task_covered_count.items()):
            print("所有任务已完成，终止")
            break

        # 随机招募
        candidates = available_workers[:]
        random.shuffle(candidates)
        selected_workers = []
        selected_bid_tasks = []
        round_cost = 0.0

        for w in candidates:
            tasks_this_round = []
            for task in w['covered_tasks']:
                if task['task_start_time'] // 3600 == r:
                    tid = task['task_id']
                    if task_covered_count[tid] < required_workers[tid]:
                        tasks_this_round.append(tid)
            if not tasks_this_round:
                continue
            cost = sum(task_price_map[tid] for tid in tasks_this_round)
            if cost > remaining_budget:
                continue
            selected_bid_tasks.append(tasks_this_round)
            selected_workers.append(w)
            round_cost += cost
            remaining_budget -= cost
            if len(selected_workers) >= K:
                break

        if not selected_workers:
            print("本轮未选中任何工人")
            continue

        total_cost += round_cost
        greedy_selected.extend([w['worker_id'] for w in selected_workers])
        greedy_rounds += 1

        round_total = 0
        round_trusted = 0
        for w, tasks_this_round in zip(selected_workers, selected_bid_tasks):
            is_trusted = (w['worker_id'] in initial_Uc)
            for tid in tasks_this_round:
                if task_covered_count[tid] < required_workers[tid]:
                    task_covered_count[tid] += 1
                    total_system_income += task_system_income_map[tid]
                    round_total += 1
                    if is_trusted:
                        round_trusted += 1

        print(f"本轮完成任务数: {round_total}, 其中可信工人完成: {round_trusted}, 占比: {round_trusted/round_total if round_total>0 else 0:.2%}")

        cumulative_total += round_total
        cumulative_trusted += round_trusted
        cumulative_ratio = cumulative_trusted / cumulative_total if cumulative_total > 0 else 0.0
        cumulative_trusted_ratio.append({
            "round": r,
            "cumulative_trusted_ratio": round(cumulative_ratio, 4)
        })
        print(f"累积完成任务数: {cumulative_total}, 累积可信完成: {cumulative_trusted}, 累积占比: {cumulative_ratio:.2%}")

        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        total_task_num = len(required_workers)
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{total_task_num}")

        task_coverage_records.append({
            "round": r,
            "completed_tasks": completed,
            "total_tasks": total_task_num,
            "coverage_rate": round(completed / total_task_num, 4) if total_task_num > 0 else 0.0
        })

        round_details.append({
            'round': r,
            'recruited_workers': [w['worker_id'] for w in selected_workers],
            'recruited_count': len(selected_workers)
        })

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    platform_utility = total_system_income - total_cost
    total_tasks = cumulative_total
    trusted_tasks = cumulative_trusted
    trusted_task_ratio_total = trusted_tasks / total_tasks if total_tasks > 0 else 0.0

    result = {
        'total_rounds': greedy_rounds,
        'total_cost': total_cost,
        'platform_utility': platform_utility,
        'trusted_task_ratio': trusted_task_ratio_total,
        'remaining_budget': remaining_budget,
        'selected_workers': greedy_selected,
        'init_select': len(workers),
        'later_select': len(greedy_selected),
        'covered_task_count': covered_task_count,
        'trusted_count': len(initial_Uc),
        'round_details': round_details
    }

    return result, task_coverage_records, cumulative_trusted_ratio

# ========== 主函数：多次重复实验取平均 ==========
def main():
    SEEDS = list(range(1, NUM_SEEDS + 1))
    
    # 存储多次实验的数据
    all_coverage_curves = []
    all_cumulative_curves = []
    all_platform_utils = []
    all_final_coverages = []
    all_trusted_counts = []
    all_final_costs = []       # 可选
    all_remaining_budgets = [] # 可选

    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    for seed in SEEDS:
        print(f"\n========== 运行随机种子 {seed} ==========")
        random.seed(seed)

        # 临时输出文件名（每次循环覆盖，但最终我们不保留中间文件，只用于传递数据）
        OUTPUT_WORKER_OPTIONS = 'step9_worker_option_set_B1.json'
        OUTPUT_TASK_WEIGHTS = 'step9_task_weight_list_B1.json'
        OUTPUT_TASK_GRID = 'step9_tasks_grid_num_B1.json'
        OUTPUT_TASK_CLASS = 'step9_tasks_classification_B1.json'

        # 第一阶段
        worker_options, tasks, task_weights, task_grid = data_preparation(
            WORKER_SEGMENTS, TASK_SEGMENTS,
            OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
            OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS
        )

        # 第二阶段
        workers, task_covered_count, required_workers, task_time_map, initial_Uc = initialize(
            OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS
        )

        # 加载任务分类
        task_class = load_json(OUTPUT_TASK_CLASS)

        # 第三阶段
        result, coverage_records, cumulative_records = greedy_recruitment_B1(
            workers, task_covered_count, required_workers,
            BUDGET, K, R, task_time_map, task_class, initial_Uc
        )

        # 收集数据
        all_coverage_curves.append([item['coverage_rate'] for item in coverage_records])
        all_cumulative_curves.append([item['cumulative_trusted_ratio'] for item in cumulative_records])
        all_platform_utils.append(result['platform_utility'])
        total_tasks = len(required_workers)
        all_final_coverages.append(result['covered_task_count'] / total_tasks)
        all_trusted_counts.append(result['trusted_count'])
        all_final_costs.append(result['total_cost'])
        all_remaining_budgets.append(result['remaining_budget'])

    # 计算平均曲线（假设所有实验轮数相同）
    num_rounds = len(all_coverage_curves[0])
    avg_coverage = []
    std_coverage = []
    avg_cumulative = []
    std_cumulative = []
    for r in range(num_rounds):
        round_cov = [curve[r] for curve in all_coverage_curves]
        avg_coverage.append(np.mean(round_cov))
        std_coverage.append(np.std(round_cov))
        round_cum = [curve[r] for curve in all_cumulative_curves]
        avg_cumulative.append(np.mean(round_cum))
        std_cumulative.append(np.std(round_cum))

    # 其他指标平均值
    avg_platform = np.mean(all_platform_utils)
    avg_final_coverage = np.mean(all_final_coverages)
    avg_trusted = np.mean(all_trusted_counts)
    avg_cost = np.mean(all_final_costs)
    avg_remaining = np.mean(all_remaining_budgets)

    # ========== 保存平均结果到原文件名 ==========
    # 1. 保存平均覆盖率曲线（每轮）
    avg_coverage_records = [
        {
            "round": r,
            "completed_tasks": int(round(avg_coverage[r] * total_tasks)),  # 近似，实际可保留原值
            "total_tasks": total_tasks,
            "coverage_rate": round(avg_coverage[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_coverage_records, "experiment1_step1_B1_taskcover.json")
    print("✅ 平均覆盖率曲线已保存至 experiment1_step1_B1_taskcover.json")

    # 2. 保存平均累积可信任务占比曲线
    avg_cumulative_records = [
        {
            "round": r,
            "cumulative_trusted_ratio": round(avg_cumulative[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_cumulative_records, "experiment1_step1_B1_cumulative_trusted_ratio.json")
    print("✅ 平均累积可信任务占比曲线已保存至 experiment1_step1_B1_cumulative_trusted_ratio.json")

    # 3. 保存平均最终结果
    avg_result = {
        'total_rounds': num_rounds,
        'total_cost': round(avg_cost, 2),
        'platform_utility': round(avg_platform, 2),
        'remaining_budget': round(avg_remaining, 2),
        'covered_task_count': int(round(avg_final_coverage * total_tasks)),
        'trusted_count': int(round(avg_trusted)),
        'init_select': len(workers),
        'later_select': int(round(avg_trusted)),  # B1 中 later_select 与 trusted_count 相同，简化
        'trusted_workers_list': list(initial_Uc),  # 平均结果中无法列出具体工人ID，可省略或保留空列表
        'round_details': []  # 平均后无法保留详细轮次信息，可省略
    }
    save_json(avg_result, "step9_final_result_B1.json")
    print("✅ 平均最终结果已保存至 step9_final_result_B1.json")

    # 可选：同时保存标准差（供后续绘图误差棒）
    std_result = {
        "std_coverage_per_round": [round(x, 4) for x in std_coverage],
        "std_cumulative_trusted_ratio_per_round": [round(x, 4) for x in std_cumulative],
        "std_platform_utility": round(np.std(all_platform_utils), 2),
        "std_final_coverage_rate": round(np.std(all_final_coverages), 4),
        "std_final_trusted_count": round(np.std(all_trusted_counts), 2)
    }
    save_json(std_result, "experiment1_step1_B1_std_results.json")
    print("✅ 标准差结果已保存至 experiment1_step1_B1_std_results.json")

if __name__ == '__main__':
    main()