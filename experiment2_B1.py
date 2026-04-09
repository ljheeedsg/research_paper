"""
B1 方案：随机招募 + 固定工资（无 CMAB、无信任、无 PGRD、无 LGSC）
适用于北京数据集：144 轮（10 分钟切片）
多次重复实验取平均，输出平均结果到原文件名。
输入：experiment2_worker_segments.json, experiment2_task_segments.json
输出：experiment2_final_result_B1.json, experiment2_step1_B1_taskcover.json,
      experiment2_step1_B1_cumulative_trusted_ratio.json,
      experiment2_step1_B1_std_results.json（标准差）
      experiment2_step1_B1_worker_category.csv（工人类别变化）
"""

import json
import random
import numpy as np
import csv
from collections import defaultdict
import os

# ========== 参数配置 ==========
RANDOM_SEED = 2
BUDGET = 50000
K = 7
R = 144                     # 修改：北京数据 144 轮（10分钟切片）
SLOT_SEC = 600              # 新增：每个时段长度（秒），北京为 10 分钟
M_VERIFY = 7

# 任务分类参数
MEMBER_RATIO = 0.8
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.1, 0.3)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# 重复次数
NUM_SEEDS = 1   # 可改为30

# ========== 工具函数 ==========
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ========== 第一阶段：数据准备 ==========
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
            # 修改：计算10分钟槽索引（北京数据）
            slot = t['task_start_time'] // SLOT_SEC
            w['available_rounds'].add(slot)

    task_covered_count = {tid: 0 for tid in task_time_map}
    required_workers = {tid: task_weights[tid] for tid in task_time_map}
    initial_Uc = {w['worker_id'] for w in workers if w['category'] == 'trusted'}
    initial_Uu = {w['worker_id'] for w in workers if w['category'] == 'unknown'}

    print(f"初始化完成，工人总数: {len(workers)}，初始可信工人: {len(initial_Uc)}，初始未知工人: {len(initial_Uu)}")

    return workers, task_covered_count, required_workers, task_time_map, initial_Uc, initial_Uu

# ========== B1 主循环（单次实验，返回曲线和结果） ==========
def greedy_recruitment_B1(workers, task_covered_count, required_workers, B, K, R, task_time_map, task_class, initial_Uc, initial_Uu):
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    round_details = []

    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}
    task_price_map = {t['task_id']: t['task_price'] for t in task_class}
    total_system_income = 0.0

    task_coverage_records = []
    cumulative_total = 0
    cumulative_trusted = 0
    cumulative_trusted_ratio = []

    worker_category_per_round = []

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if r in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(initial_Uc),
                "unknown_count": len(initial_Uu),
                "malicious_count": 0
            })
            continue

        # 计算最小成本
        min_cost = float('inf')
        for w in available_workers:
            for task in w['covered_tasks']:
                # 修改：使用 SLOT_SEC 计算槽索引
                if task['task_start_time'] // SLOT_SEC != r:
                    continue
                tid = task['task_id']
                if task_covered_count[tid] < required_workers[tid]:
                    price = task_price_map[tid]
                    if price < min_cost:
                        min_cost = price
        if min_cost == float('inf'):
            print("本轮没有可做的任务")
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(initial_Uc),
                "unknown_count": len(initial_Uu),
                "malicious_count": 0
            })
            break
        if remaining_budget < min_cost:
            print("预算不足，终止")
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(initial_Uc),
                "unknown_count": len(initial_Uu),
                "malicious_count": 0
            })
            break

        if all(cnt >= required_workers[tid] for tid, cnt in task_covered_count.items()):
            print("所有任务已完成，终止")
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(initial_Uc),
                "unknown_count": len(initial_Uu),
                "malicious_count": 0
            })
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
                # 修改：使用 SLOT_SEC 计算槽索引
                if task['task_start_time'] // SLOT_SEC == r:
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
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(initial_Uc),
                "unknown_count": len(initial_Uu),
                "malicious_count": 0
            })
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

        worker_category_per_round.append({
            "round": r,
            "trusted_count": len(initial_Uc),
            "unknown_count": len(initial_Uu),
            "malicious_count": 0
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

    coverage_curve = [item['coverage_rate'] for item in task_coverage_records]
    cumulative_curve = [item['cumulative_trusted_ratio'] for item in cumulative_trusted_ratio]

    return result, coverage_curve, cumulative_curve, worker_category_per_round

# ========== 单次实验封装 ==========
def run_experiment_B1(seed, worker_segments_path, task_segments_path, budget, K, R):
    random.seed(seed)

    OUTPUT_WORKER_OPTIONS = 'experiment2_worker_option_set_B1.json'
    OUTPUT_TASK_WEIGHTS = 'experiment2_task_weight_list_B1.json'
    OUTPUT_TASK_GRID = 'experiment2_tasks_grid_num_B1.json'
    OUTPUT_TASK_CLASS = 'experiment2_tasks_classification_B1.json'

    data_preparation(worker_segments_path, task_segments_path,
                     OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
                     OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS)

    workers, task_covered_count, required_workers, task_time_map, initial_Uc, initial_Uu = initialize(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS
    )

    task_class = load_json(OUTPUT_TASK_CLASS)

    result, coverage_curve, cumulative_curve, worker_cat = greedy_recruitment_B1(
        workers, task_covered_count, required_workers,
        budget, K, R, task_time_map, task_class, initial_Uc, initial_Uu
    )

    return coverage_curve, cumulative_curve, result, worker_cat

# ========== 主函数：多次重复实验取平均 ==========
# ========== 主函数：多次重复实验取平均 ==========
import os   # 确保文件开头有这一行

def main():
    WORKER_SEGMENTS = 'experiment2_worker_segments.json'
    TASK_SEGMENTS = 'experiment2_task_segments.json'

    base_seed = RANDOM_SEED
    seeds = [base_seed + i for i in range(NUM_SEEDS)]

    all_coverage_curves = []
    all_cumulative_curves = []
    all_worker_categories = []
    all_platform_utils = []
    all_final_coverages = []
    all_total_costs = []
    all_remaining_budgets = []
    all_trusted_counts = []
    all_unit_costs = []   # 新增：存储每次实验的单位任务成本

    # 定义要删除的中间文件列表
    intermediate_files = [
        'experiment2_worker_option_set_B1.json',
        'experiment2_task_weight_list_B1.json',
        'experiment2_tasks_grid_num_B1.json',
        'experiment2_tasks_classification_B1.json',
        'experiment2_lgsc_params_B1.json'   # 如果不存在则跳过
    ]

    # 获取总任务数（从第一次实验的任务分类文件获取）
    print("获取总任务数...")
    temp_seed = seeds[0]
    random.seed(temp_seed)
    temp_worker_options = 'experiment2_worker_option_set_B1.json'
    temp_task_weights = 'experiment2_task_weight_list_B1.json'
    temp_task_grid = 'experiment2_tasks_grid_num_B1.json'
    temp_task_class = 'experiment2_tasks_classification_B1.json'
    data_preparation(WORKER_SEGMENTS, TASK_SEGMENTS,
                     temp_worker_options, temp_task_weights,
                     temp_task_grid, temp_task_class)
    task_class_temp = load_json(temp_task_class)
    TOTAL_TASKS = len(task_class_temp)
    print(f"总任务数: {TOTAL_TASKS}")

    for idx, seed in enumerate(seeds):
        print(f"\n========== 运行实验 {idx+1}/{NUM_SEEDS}，随机种子 {seed} ==========")
        coverage_curve, cumulative_curve, result, worker_cat = run_experiment_B1(
            seed, WORKER_SEGMENTS, TASK_SEGMENTS, BUDGET, K, R
        )
        all_coverage_curves.append(coverage_curve)
        all_cumulative_curves.append(cumulative_curve)
        all_worker_categories.append(worker_cat)
        all_platform_utils.append(result['platform_utility'])
        all_total_costs.append(result['total_cost'])
        all_remaining_budgets.append(result['remaining_budget'])
        all_trusted_counts.append(result['trusted_count'])
        final_coverage = result['covered_task_count'] / TOTAL_TASKS
        all_final_coverages.append(final_coverage)

        # 计算单位任务成本
        unit_cost = result['total_cost'] / result['covered_task_count'] if result['covered_task_count'] > 0 else 0
        all_unit_costs.append(unit_cost)


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

    avg_trusted_per_round = []
    avg_unknown_per_round = []
    avg_malicious_per_round = []
    for r in range(num_rounds):
        trusted_vals = [cat[r]['trusted_count'] for cat in all_worker_categories]
        unknown_vals = [cat[r]['unknown_count'] for cat in all_worker_categories]
        malicious_vals = [cat[r]['malicious_count'] for cat in all_worker_categories]
        avg_trusted_per_round.append(round(np.mean(trusted_vals)))
        avg_unknown_per_round.append(round(np.mean(unknown_vals)))
        avg_malicious_per_round.append(round(np.mean(malicious_vals)))

    avg_platform = np.mean(all_platform_utils)
    avg_final_coverage = np.mean(all_final_coverages)
    avg_cost = np.mean(all_total_costs)
    avg_remaining = np.mean(all_remaining_budgets)
    avg_trusted = np.mean(all_trusted_counts)
    avg_unit_cost = np.mean(all_unit_costs) if all_unit_costs else 0
    std_unit_cost = np.std(all_unit_costs) if all_unit_costs else 0

    # 保存平均覆盖率曲线（JSON + CSV）
    avg_coverage_records = [
        {
            "round": r,
            "completed_tasks": int(round(avg_coverage[r] * TOTAL_TASKS)),
            "total_tasks": TOTAL_TASKS,
            "coverage_rate": round(avg_coverage[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_coverage_records, "experiment2_step1_B1_taskcover.json")
    with open("experiment2_step1_B1_taskcover.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "completed_tasks", "total_tasks", "coverage_rate"])
        for record in avg_coverage_records:
            writer.writerow([record["round"], record["completed_tasks"], record["total_tasks"], record["coverage_rate"]])
    print("✅ 平均覆盖率曲线已保存 (JSON + CSV)")

    # 保存平均累积可信任务占比曲线（JSON + CSV）
    avg_cumulative_records = [
        {
            "round": r,
            "cumulative_trusted_ratio": round(avg_cumulative[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_cumulative_records, "experiment2_step1_B1_cumulative_trusted_ratio.json")
    with open("experiment2_step1_B1_cumulative_trusted_ratio.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "cumulative_trusted_ratio"])
        for record in avg_cumulative_records:
            writer.writerow([record["round"], record["cumulative_trusted_ratio"]])
    print("✅ 平均累积可信任务占比曲线已保存 (JSON + CSV)")

    # 保存平均最终结果
    avg_result = {
        'total_rounds': num_rounds,
        'total_cost': round(avg_cost, 2),
        'platform_utility': round(avg_platform, 2),
        'remaining_budget': round(avg_remaining, 2),
        'covered_task_count': int(round(avg_final_coverage * TOTAL_TASKS)),
        'trusted_count': int(round(avg_trusted)),
        'init_select': len(load_json(temp_worker_options)['worker_options']),
        'later_select': int(round(avg_trusted)),
        'trusted_workers_list': [],
        'round_details': [],
        'avg_unit_cost': round(avg_unit_cost, 2)   # 新增
    }
    save_json(avg_result, "experiment2_final_result_B1.json")

    # 保存标准差结果
    std_result = {
        "std_coverage_per_round": [round(x, 4) for x in std_coverage],
        "std_cumulative_trusted_ratio_per_round": [round(x, 4) for x in std_cumulative],
        "std_platform_utility": round(np.std(all_platform_utils), 2),
        "std_final_coverage_rate": round(np.std(all_final_coverages), 4),
        "std_total_cost": round(np.std(all_total_costs), 2),
        "std_trusted_count": round(np.std(all_trusted_counts), 2),
        "std_unit_cost": round(std_unit_cost, 2)   # 新增
    }
    save_json(std_result, "experiment2_step1_B1_std_results.json")

    # 工人类别变化 CSV
    with open("experiment2_step1_B1_worker_category.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "trusted_count", "unknown_count", "malicious_count"])
        for r in range(num_rounds):
            writer.writerow([r, avg_trusted_per_round[r], avg_unknown_per_round[r], avg_malicious_per_round[r]])
    print("✅ 工人类别变化曲线已保存至 experiment2_step1_B1_worker_category.csv")

    # ========== 删除中间 JSON 文件 ==========
    for file in intermediate_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"已删除中间文件: {file}")
        else:
            print(f"中间文件不存在，跳过: {file}")

    print("✅ 实验完成，中间文件已清理")

if __name__ == '__main__':
    main()