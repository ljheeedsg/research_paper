"""
群智感知双阶段工人招募与信任度验证算法（三阶段架构）

本代码实现：
- 第一阶段：数据准备（生成工人可选项、任务权重、网格映射）
- 第二阶段：初始化（学习阶段，招募所有工人，初始化CMAB档案）
- 第三阶段：贪心轮次（多轮迭代，含信任度验证）

使用前请确保已有 step1_worker_segments.json 和 step1_task_segments.json。
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
# 数据准备参数
RANDOM_SEED = 42

# 预算与招募参数
BUDGET = 10000          # 总预算
K = 5                    # 每轮招募人数
R = 6                    # 总轮数（6小时）
M_VERIFY = 3             # 每轮验证任务数

# 信任度参数
ETA = 0.2                # 信任度更新步长
THETA_HIGH = 0.8         # 可信阈值
THETA_LOW = 0.2          # 恶意阈值

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
    for region_id, seg_list in segments_by_region.items():
        region = int(region_id.split('_')[1])
        for seg in seg_list:
            worker_id = seg['vehicle_id']
            workers[worker_id].append({
                'region_id': region,
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'cost': seg['cost'],
                'is_trusted': seg['is_trusted']
            })
    return workers

def parse_tasks(task_segments):
    tasks = []
    for region_id, task_list in task_segments.items():
        region = int(region_id.split('_')[1])
        for task in task_list:
            tasks.append({
                'task_id': task['task_id'],
                'region_id': region,
                'start_time': task['start_time'],
                'end_time': task['end_time'],
                'required_workers': task['required_workers']
            })
    return tasks

def generate_worker_options(workers, tasks, random_seed=None):
    if random_seed is not None:
        random.seed(random_seed)

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
                start = max(seg['start_time'], task['start_time'])
                end = min(seg['end_time'], task['end_time'])
                if start < end:
                    quality = random.uniform(0, 1)
                    task_data = random.uniform(0, 1)
                    covered.append({
                        'task_id': task['task_id'],
                        'quality': quality,
                        'task_price': base_cost,
                        'start_time': start,
                        'end_time': end,
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

def generate_task_grid_map(task_segments_path):
    task_segments = load_json(task_segments_path)
    grid_map = []
    for region_id_str, task_list in task_segments.items():
        region_id = int(region_id_str.split('_')[1])
        for task in task_list:
            grid_map.append({'task_id': task['task_id'], 'grid_id': region_id})
    return grid_map

def generate_worker_options_and_task_weights(
    worker_segments_path,
    task_segments_path,
    output_worker_options_path,
    output_task_weights_path,
    output_task_grid_path,
    random_seed=RANDOM_SEED
):
    worker_segments = load_json(worker_segments_path)
    task_segments = load_json(task_segments_path)

    workers = parse_worker_segments(worker_segments)
    tasks = parse_tasks(task_segments)

    worker_options = generate_worker_options(workers, tasks, random_seed)
    task_weights = generate_task_weights(tasks)
    task_grid = generate_task_grid_map(task_segments_path)

    save_json({'worker_options': worker_options}, output_worker_options_path)
    save_json({'task_weights': task_weights}, output_task_weights_path)
    save_json(task_grid, output_task_grid_path)

    print(f"✅ 已生成 {output_worker_options_path}、{output_task_weights_path}、{output_task_grid_path}")

# ========== 第二阶段：初始化（学习阶段） ==========
def initialize_cmab(worker_options_path, task_weights_path):
    """初始化 CMAB 档案、任务覆盖、工人分类"""
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']

    # 初始化 CMAB 档案
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        if w['n_i'] > 0:
            total_q = sum(t['quality'] for t in w['covered_tasks'])
            w['avg_quality'] = total_q / w['n_i']
        else:
            w['avg_quality'] = 0.0
        w['judge_count'] = 1

    # 初始化工人分类集合
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

    # 任务覆盖计数
    task_covered_count = {tid: 0 for tid in task_weights}
    required_workers = task_weights

    total_learned_counts = sum(w['n_i'] for w in workers)

    return workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um

# ========== 第三阶段：贪心轮次 ==========
def compute_avg_quality(worker):
    if not worker['covered_tasks']:
        return 0.0
    total_q = sum(task['quality'] for task in worker['covered_tasks'])
    return total_q / len(worker['covered_tasks'])

def ucb_quality(worker, total_learned_counts, K):
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def generate_validation_tasks(workers, task_grid_map, Uc, Uu, round_idx, M):
    """
    生成验证任务：只从有 Uc 工人经过的网格中，按 Uu 出现次数排序取前 M 个。
    返回验证任务列表（每个元素为 task_id）。
    """
    # 当前轮可用工人（由 worker_id 中的小时决定）
    available_workers = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]
    if not available_workers:
        return []

    # 统计每个网格中 Uc 和 Uu 的出现次数
    grid_uc = defaultdict(int)
    grid_uu = defaultdict(int)
    for w in available_workers:
        wid = w['worker_id']
        for task in w['covered_tasks']:
            tid = task['task_id']
            gid = task_grid_map.get(tid)
            if gid is None:
                continue
            if wid in Uc:
                grid_uc[gid] += 1
            elif wid in Uu:
                grid_uu[gid] += 1

    # 筛选有 Uc 的网格
    valid_grids = [g for g in grid_uc if grid_uc[g] > 0]
    if not valid_grids:
        return []

    # 按 Uu 出现次数降序排序
    valid_grids.sort(key=lambda g: grid_uu.get(g, 0), reverse=True)
    selected_grids = valid_grids[:M]

    # 构建网格到任务列表的映射（仅当前轮可用的任务）
    grid_to_tasks = defaultdict(list)
    for tid, gid in task_grid_map.items():
        # 任务属于当前轮次的条件： start_time // 3600 == round_idx
        # 注意：我们需要从 workers 中获取任务的 start_time，这里简单起见，可以从第一个覆盖该任务的工人中取
        # 但为了效率，我们可以在生成 worker_options 时已经记录了每个任务的 start_time，这里直接从 task_grid_map 无法获得。
        # 改进：在生成任务网格映射时，同时记录任务的 start_time。但为简化，我们假设任务的时间与工人覆盖的时间已存储在 worker 的 covered_tasks 中，
        # 因此我们直接遍历 available_workers 来收集当前轮的任务。
        # 这里我们采用另一种方法：收集所有 available_workers 中覆盖的任务，并去重，然后判断其 start_time 是否属于当前轮。
        pass

    # 更简单的方法：对于每个选中的网格，从该网格的任务中随机选一个，但必须确保该任务在当前轮次有工人覆盖。
    # 由于我们有 available_workers，我们可以先收集所有当前轮的任务列表。
    # 构建网格 -> 任务列表（仅当前轮任务）
    grid_to_tasks_current = defaultdict(list)
    for w in available_workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            # 任务是否属于当前轮：由 start_time 决定（从任务数据中获取，但任务数据已存储在 task 中）
            # 由于我们在第一步已将任务 start_time 保存在 covered_tasks 中，可直接使用。
            if (task['start_time'] // 3600) == round_idx:
                gid = task_grid_map.get(tid)
                if gid is not None:
                    if tid not in grid_to_tasks_current[gid]:
                        grid_to_tasks_current[gid].append(tid)

    validation_tasks = []
    for g in selected_grids:
        if grid_to_tasks_current[g]:
            task = random.choice(grid_to_tasks_current[g])
            validation_tasks.append(task)
    return validation_tasks

def update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, round_idx, eta, theta_high, theta_low):
    """
    根据验证任务更新信任度。
    注意：只更新本轮可用工人（即其轨迹覆盖当前轮次）的信任度。
    """
    # 本轮可用工人
    available_workers = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]
    # 构建 worker_id -> worker 的映射
    worker_map = {w['worker_id']: w for w in available_workers}

    for vtask in validation_tasks:
        # 收集完成该任务的 Uc 工人的 task_data
        uc_data = []
        for w in available_workers:
            if w['worker_id'] in Uc:
                for task in w['covered_tasks']:
                    if task['task_id'] == vtask:
                        uc_data.append(task['task_data'])
                        break
        if not uc_data:
            continue
        base = sorted(uc_data)[len(uc_data)//2]  # 中位数

        # 更新完成该任务的 Uu 工人
        for w in available_workers:
            wid = w['worker_id']
            if wid in Uu:
                # 检查该工人是否完成了该验证任务
                data = None
                for task in w['covered_tasks']:
                    if task['task_id'] == vtask:
                        data = task['task_data']
                        break
                if data is None:
                    continue
                if base == 0:
                    error = abs(data - base)
                else:
                    error = abs(data - base) / base
                w['trust'] += eta * (1 - 2 * error)
                w['trust'] = max(0.0, min(1.0, w['trust']))
                if w['trust'] >= theta_high:
                    Uc.add(wid)
                    Uu.discard(wid)
                    w['category'] = 'trusted'
                elif w['trust'] <= theta_low:
                    Um.add(wid)
                    Uu.discard(wid)
                    w['category'] = 'malicious'
    return Uc, Uu, Um

def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx):
    """
    执行一轮 CMAB 招募，返回选中的工人列表及更新后的状态。
    返回: (round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost)
    """
    # 当前轮可用工人
    candidates = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0

    # 当前轮可用任务（从候选工人的覆盖任务中收集，并按 start_time 判断）
    available_tasks = set()
    for w in candidates:
        for task in w['covered_tasks']:
            if (task['start_time'] // 3600) == round_idx:
                available_tasks.add(task['task_id'])

    # 去除已完成的可用任务
    unfinished_available = [tid for tid in available_tasks if task_covered_count[tid] < required_workers[tid]]
    if not unfinished_available:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0

    round_selected = []
    round_cost = 0.0
    for _ in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        for w in candidates:
            if w['total_cost'] > remaining_budget:
                continue
            ucb_q = ucb_quality(w, total_learned_counts, K)
            gain = 0.0
            for task in w['covered_tasks']:
                tid = task['task_id']
                if tid not in available_tasks:
                    continue
                if task_covered_count[tid] < required_workers[tid]:
                    gain += required_workers[tid] * ucb_q
            if gain <= 0:
                ratio = 0
            else:
                ratio = gain / w['total_cost']
            if ratio > best_ratio:
                best_ratio = ratio
                best_worker = w
        if best_worker is None:
            break
        round_selected.append(best_worker['worker_id'])
        round_cost += best_worker['total_cost']
        remaining_budget -= best_worker['total_cost']
        # 更新任务覆盖计数
        for task in best_worker['covered_tasks']:
            tid = task['task_id']
            if tid in available_tasks and task_covered_count[tid] < required_workers[tid]:
                task_covered_count[tid] += 1
        # 更新工人档案
        learned_tasks = len([task for task in best_worker['covered_tasks'] if task['task_id'] in available_tasks])
        if learned_tasks > 0:
            best_worker['n_i'] += learned_tasks
            observed = best_worker['avg_quality']
            prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
            new_sum = prev_sum + observed * learned_tasks
            best_worker['avg_quality'] = new_sum / best_worker['n_i']
            total_learned_counts += learned_tasks
        candidates.remove(best_worker)
    return round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost

def greedy_recruitment(workers, task_covered_count, required_workers, total_learned_counts, B, K, R, task_grid_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW):
    """
    执行多轮贪心招募，同时进行信任度验证。
    """
    # 初始化工人分类集合
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

    total_cost = 0
    remaining_budget = B
    all_selected = []
    greedy_selected = []
    greedy_rounds = 0

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        # 当前轮可用工人
        available_workers = [w for w in workers if int(w['worker_id'][1:3]) == r]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 终止条件检查
        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break
        # 检查是否所有当前轮任务已完成（简化：检查所有任务是否完成，实际应只检查当前轮任务）
        # 这里简单检查所有任务，但可以优化。
        if all(task_covered_count[tid] >= required_workers[tid] for tid in required_workers):
            print("所有任务已完成，终止")
            break

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, Uc, Uu, r, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r
)
        total_cost += round_cost
        if not round_selected:
            print("本轮未选中任何工人")
        else:
            greedy_selected.extend(round_selected)
            greedy_rounds += 1
            print(f"招募工人: {round_selected}")

        # 信任度更新
        if validation_tasks:
            Uc, Uu, Um = update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, r, ETA, THETA_HIGH, THETA_LOW)

        # 统计
        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(required_workers)}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    result = {
        'total_rounds': greedy_rounds,
        'total_cost': total_cost,
        'remaining_budget': remaining_budget,
        'selected_workers': greedy_selected,
        'init_select': len(workers),
        'later_select': len(greedy_selected),
        'covered_task_count': covered_task_count,
        'trusted_count': len(Uc),
        'malicious_count': len(Um),
        'unknown_count': len(Uu),
        'trusted_workers_list': list(Uc)
    }
    return result

# ========== 主函数 ==========
def main():
    # 第一阶段：数据准备
    generate_worker_options_and_task_weights(
        worker_segments_path='step1_worker_segments.json',
        task_segments_path='step1_task_segments.json',
        output_worker_options_path='step3_worker_option_set.json',
        output_task_weights_path='step3_task_weight_list.json',
        output_task_grid_path='step3_tasks_grid_num.json',
        random_seed=RANDOM_SEED
    )

    # 第二阶段：初始化
    workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um = initialize_cmab(
        'step5_worker_option_set.json', 'step5_task_weight_list.json'
    )
    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")

    # 第三阶段：贪心轮次
    task_grid_map = load_json('step5_tasks_grid_num.json')
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid_map}

    result = greedy_recruitment(
        workers, task_covered_count, required_workers, total_learned_counts,
        BUDGET, K, R, task_grid_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW
    )

    print("\n=== 最终结果 ===")
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 10:
            print(f"{k}: {v[:10]}... (共{len(v)})")
        else:
            print(f"{k}: {v}")

    save_json(result, 'final_result.json')
    print("结果已保存至 final_result.json")

if __name__ == '__main__':
    main()