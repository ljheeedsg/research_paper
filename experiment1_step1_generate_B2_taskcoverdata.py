"""
群智感知双阶段工人招募算法（B2 方案：仅 CMAB 贪心招募，无信任验证、无 PGRD、无 LGSC）
输入：step6_worker_segments.json, step6_task_segments.json
输出：step9_worker_option_set_B2.json, step9_task_weight_list_B2.json, step9_tasks_grid_num_B2.json,
      step9_tasks_classification_B2.json（占位）, step9_lgsc_params_B2.json（占位）, step9_final_result_B2.json
      experiment1_step1_B2_taskcover.json（覆盖率记录）
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

BUDGET = 10000
K = 7
R = 24

# 信任度参数（B2 不使用，保留占位）
ETA = 0.6
THETA_HIGH = 0.75
THETA_LOW = 0.3

# 任务分类参数（B2 不使用 PGRD，但需生成任务数据占位）
MEMBER_RATIO = 0.5
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# LGSC 参数（B2 不使用，占位）
SUNK_THRESHOLD = 20
MEMBER_BONUS = 20
RHO_INIT = 1.0

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
    for worker_id, segs in sorted(workers.items()):
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
    # B2 虽不使用 PGRD，但仍需生成任务分类文件以保持兼容（后续可能用不到）
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

    tasks_info = []
    default_price = 10.0
    for tid in all_task_ids:
        if tid in task_prices:
            base_price = sum(task_prices[tid]) / len(task_prices[tid])
        else:
            base_price = default_price
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
    print(f"✅ 已生成任务分类 {output_path}，包含 {len(final_tasks)} 个任务")

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

    # 占位 LGSC 参数文件
    lgsc_params = {
        'sunk_threshold': SUNK_THRESHOLD,
        'member_bonus': MEMBER_BONUS,
        'rho_init': RHO_INIT
    }
    save_json(lgsc_params, 'step9_lgsc_params_B2.json')
    print("已保存 LGSC 参数 step9_lgsc_params_B2.json（占位）")

    return worker_options, tasks, task_weights, task_grid

# ========== 第二阶段：初始化 ==========
def initialize_cmab(worker_options_path, task_weights_path, task_class_path, lgsc_params_path):
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)   # 占位，不使用
    lgsc = load_json(lgsc_params_path)        # 占位

    task_time_map = {}
    for w in workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            if tid not in task_time_map:
                task_time_map[tid] = task['task_start_time']

    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        w['avg_quality'] = sum(t['quality'] for t in w['covered_tasks']) / w['n_i'] if w['n_i'] > 0 else 0.0
        w['judge_count'] = 1
        w['available_rounds'] = set()
        for t in w['covered_tasks']:
            hour = t['task_start_time'] // 3600
            w['available_rounds'].add(hour)

        # 保留其他字段（虽然 B2 不使用）
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0
        w['is_member'] = False
        w['member_until'] = -1

    # 工人分类集合（B2 中虽然不用信任，但保留分类用于招募，招募时取 trusted+unknown）
    Uc = set()
    Uu = set()
    Um = set()
    for w in workers:
        if w['category'] == 'trusted':
            Uc.add(w['worker_id'])
        elif w['category'] == 'unknown':
            Uu.add(w['worker_id'])
        else:
            Um.add(w['worker_id'])

    task_covered_count = {tid: 0 for tid in task_time_map}
    required_workers = {tid: task_weights[tid] for tid in task_time_map}
    total_learned_counts = sum(w['n_i'] for w in workers)

    # 平均报酬变量（B2 不使用）
    R_m = 0.0
    R_n = 0.0

    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")

    return workers, task_covered_count, required_workers, total_learned_counts, \
           Uc, Uu, Um, R_m, R_n, task_time_map

# ========== 第三阶段：核心函数 ==========
def ucb_quality(worker, total_learned_counts):
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx, bid_tasks):
    candidates = [w for w in workers if round_idx in w['available_rounds']
                  and w['category'] in ('trusted', 'unknown')
                  and bid_tasks.get(w['worker_id'])]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, []

    round_selected = []
    round_cost = 0.0
    completed_tasks_per_worker = []

    for _ in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        best_bid_tasks = None
        for w in candidates:
            tid_list = bid_tasks[w['worker_id']]
            actual_bid = [tid for tid in tid_list if task_covered_count[tid] < required_workers[tid]]
            if not actual_bid:
                continue
            cost = len(actual_bid) * w['covered_tasks'][0]['task_price']
            if cost > remaining_budget:
                continue
            ucb_q = ucb_quality(w, total_learned_counts)
            gain = 0.0
            for tid in actual_bid:
                gain += required_workers[tid] * ucb_q
            ratio = gain / cost if gain > 0 else 0
            if ratio > best_ratio:
                best_ratio = ratio
                best_worker = w
                best_bid_tasks = actual_bid

        if best_worker is None:
            break
        round_selected.append(best_worker['worker_id'])
        cost = len(best_bid_tasks) * best_worker['covered_tasks'][0]['task_price']
        round_cost += cost
        remaining_budget -= cost
        completed_tasks_per_worker.append((best_worker, best_bid_tasks))

        for tid in best_bid_tasks:
            if task_covered_count[tid] < required_workers[tid]:
                task_covered_count[tid] += 1

        learned = len(best_bid_tasks)
        if learned > 0:
            best_worker['n_i'] += learned
            task_quality_map = {t['task_id']: t['quality'] for t in best_worker['covered_tasks']}
            observed = sum(task_quality_map[tid] for tid in best_bid_tasks) / learned
            prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned)
            new_sum = prev_sum + observed * learned
            best_worker['avg_quality'] = new_sum / best_worker['n_i']
            total_learned_counts += learned

        candidates.remove(best_worker)

    return round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, completed_tasks_per_worker

# ========== B2 主循环 ==========
def greedy_recruitment_B2(workers, task_covered_count, required_workers, total_learned_counts,
                          Uc, Uu, Um, B, K, R, task_time_map,
                          task_class):   # task_class 用于系统收益映射
    """B2 方案：仅 CMAB 贪心招募，无信任、无 PGRD、无 LGSC"""
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    round_details = []
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}
    total_system_income = 0.0
    task_completion_records = []   # 存储 (task_id, worker_id, is_trusted)

    # 记录覆盖率
    task_coverage_records = []

    # 累积可信任务占比
    cumulative_total_tasks = 0
    cumulative_trusted_tasks = 0
    trusted_ratio_per_round = []   # 记录每轮的累积可信任务占比

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if r in w['available_rounds']]
        print(f"可用工人数: {len(available_workers)}")
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 统计未完成任务数
        remaining_tasks = sum(1 for tid, cnt in task_covered_count.items() if cnt < required_workers[tid])
        print(f"当前轮未完成任务数: {remaining_tasks}")
        if remaining_tasks == 0:
            print("所有任务已完成，终止")
            break

        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break

        # 生成投标任务：工人投标其所有可覆盖且属于当前轮次的任务
        bid_tasks = {}
        for w in available_workers:
            tasks_this_round = []
            for task in w['covered_tasks']:
                if task['task_start_time'] // 3600 == r:
                    tasks_this_round.append(task['task_id'])
            bid_tasks[w['worker_id']] = tasks_this_round

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, completed_tasks = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r, bid_tasks
        )

        total_cost += round_cost

        # 累加本轮完成的系统收益
        for w, task_list in completed_tasks:
            for tid in task_list:
                total_system_income += task_system_income_map[tid]

        # 记录本轮完成的任务并统计
        round_total = 0
        round_trusted = 0
        for w, task_list in completed_tasks:
            is_trusted = (w['worker_id'] in Uc)   # B2 使用初始可信集合
            for tid in task_list:
                round_total += 1
                if is_trusted:
                    round_trusted += 1
                task_completion_records.append((tid, w['worker_id'], is_trusted))

        # 打印本轮完成任务情况
        print(f"本轮完成任务数: {round_total}, 其中可信工人完成: {round_trusted}, 占比: {round_trusted/round_total if round_total>0 else 0:.2%}")

        # 更新累积统计并记录
        cumulative_total_tasks += round_total
        cumulative_trusted_tasks += round_trusted
        cumulative_ratio = cumulative_trusted_tasks / cumulative_total_tasks if cumulative_total_tasks > 0 else 0.0
        print(f"累积可信任务占比: {cumulative_ratio:.2%}")
        trusted_ratio_per_round.append({
            "round": r,
            "cumulative_trusted_ratio": round(cumulative_ratio, 4)
        })

        # 打印招募工人信息
        if round_selected:
            recruited_trusted = [wid for wid in round_selected if wid in Uc]
            print(f"招募工人: {round_selected}, 其中可信: {recruited_trusted} (共{len(recruited_trusted)}人)")
        else:
            print("本轮未选中任何工人")
            continue

        greedy_selected.extend(round_selected)
        greedy_rounds += 1

        # 统计覆盖率
        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        total_task_num = len(required_workers)
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{total_task_num}")

        # 记录本轮覆盖率
        task_coverage_records.append({
            "round": r,
            "completed_tasks": completed,
            "total_tasks": total_task_num,
            "coverage_rate": round(completed / total_task_num, 4) if total_task_num > 0 else 0.0
        })

        # 记录本轮详情
        round_details.append({
            'round': r,
            'recruited_workers': round_selected,
            'completed_tasks': completed
        })

    # 保存覆盖率文件
    save_json(task_coverage_records, "experiment1_step1_B2_taskcover.json")
    print(f"\n✅ 覆盖率文件已保存：experiment1_step1_B2_taskcover.json")
    # 保存累积可信任务占比文件
    save_json(trusted_ratio_per_round, "experiment1_step1_B2_trusted_ratio_per_round.json")
    print(f"✅ 累积可信任务占比文件已保存：experiment1_step1_B2_trusted_ratio_per_round.json")

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    platform_utility = total_system_income - total_cost
    total_tasks = len(task_completion_records)
    trusted_tasks = sum(1 for _, _, is_trusted in task_completion_records if is_trusted)
    trusted_task_ratio = trusted_tasks / total_tasks if total_tasks > 0 else 0.0
    result = {
        'total_rounds': greedy_rounds,
        'platform_utility': platform_utility,
        'trusted_task_ratio': trusted_task_ratio,
        'total_cost': total_cost,
        'remaining_budget': remaining_budget,
        'selected_workers': greedy_selected,
        'init_select': len(workers),
        'later_select': len(greedy_selected),
        'covered_task_count': covered_task_count,
        'round_details': round_details
    }
    return result

# ========== 主函数 ==========
def main():
    random.seed(RANDOM_SEED)

    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    # B2 专用输出文件名
    OUTPUT_WORKER_OPTIONS = 'step9_worker_option_set_B2.json'
    OUTPUT_TASK_WEIGHTS = 'step9_task_weight_list_B2.json'
    OUTPUT_TASK_GRID = 'step9_tasks_grid_num_B2.json'
    OUTPUT_TASK_CLASS = 'step9_tasks_classification_B2.json'
    OUTPUT_FINAL = 'step9_final_result_B2.json'

    # 第一阶段
    worker_options, tasks, task_weights, task_grid = data_preparation(
        WORKER_SEGMENTS, TASK_SEGMENTS,
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
        OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS
    )

    # 第二阶段
    workers, task_covered_count, required_workers, total_learned_counts, \
    Uc, Uu, Um, _, _, task_time_map = initialize_cmab(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS, 'step9_lgsc_params_B2.json'
    )

    # 加载任务分类（占位）
    task_class = load_json(OUTPUT_TASK_CLASS)

    # 第三阶段（B2）
    result = greedy_recruitment_B2(
        workers, task_covered_count, required_workers, total_learned_counts,
        Uc, Uu, Um,
        BUDGET, K, R, task_time_map, task_class
    )

    save_json(result, OUTPUT_FINAL)
    print(f"\n最终结果已保存至 {OUTPUT_FINAL}")

    # 打印简要结果
    print("\n=== 最终结果 ===")
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 10:
            print(f"{k}: {v[:10]}... (共{len(v)})")
        else:
            print(f"{k}: {v}")

if __name__ == '__main__':
    main()