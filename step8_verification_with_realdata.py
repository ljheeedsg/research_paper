"""
群智感知双阶段工人招募与信任度验证算法（含空间一致性验证）
本代码实现：
- 第一阶段：数据准备（生成工人可选项、任务权重、网格映射）
- 第二阶段：初始化（学习阶段，招募所有工人，初始化CMAB档案，计算工人可用轮次）
- 第三阶段：贪心轮次（多轮迭代，含信任度验证）

使用前请确保已有 step6_worker_segments.json 和 step6_task_segments.json。
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42

# 预算与招募参数
BUDGET = 100000          # 总预算
K = 7                   # 每轮招募人数（增大以确保覆盖）
R = 24                   # 总轮数（全天24小时）
M_VERIFY = 3             # 每轮验证任务数

# 信任度参数
ETA = 0.4                # 信任度更新步长
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
    """
    将按区域分组的工人轨迹段，按工人序号聚合。
    工人序号从 vehicle_id 中提取（如 v00_000 -> 000）。
    """
    workers = defaultdict(list)
    for region_key, seg_list in segments_by_region.items():
        region = int(region_key.split('_')[1])
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

def generate_worker_options(workers, tasks, random_seed=None):
    if random_seed is not None:
        random.seed(random_seed)

    worker_options = []
    for worker_id, segs in workers.items():
        # 取第一个段的属性（假设同一工人所有段一致）
        is_trusted = segs[0]['is_trusted']
        base_cost = segs[0]['cost']
        trust = 1.0 if is_trusted else 0.5
        category = 'trusted' if is_trusted else 'unknown'

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
                task_data = random.uniform(0, 1)       # 随机上报数据
                covered.append({
                    'task_id': task['task_id'],
                    'quality': quality,
                    'task_price': base_cost,
                    'start_time': start,                # 实际可执行窗口起始
                    'end_time': end,                    # 实际可执行窗口结束
                    'task_start_time': task['start_time'],  # 任务原始开始时间
                    'task_data': task_data
                })
                break   # 一个任务只需记录一次

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
    task_grid = generate_task_grid_map(task_segments)

    save_json({'worker_options': worker_options}, output_worker_options_path)
    save_json({'task_weights': task_weights}, output_task_weights_path)
    save_json(task_grid, output_task_grid_path)

    print(f"✅ 已生成 {output_worker_options_path}、{output_task_weights_path}、{output_task_grid_path}")

# ========== 第二阶段：初始化（学习阶段） ==========
def initialize_cmab(worker_options_path, task_weights_path):
    """初始化 CMAB 档案、任务覆盖、工人分类，并计算工人可用轮次"""
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']

    # 从工人选项中提取每个任务的开始时间（构建 task_id -> start_time 映射，只保留有工人覆盖的任务）
    task_time_map = {}
    for w in workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            if tid not in task_time_map:
                task_time_map[tid] = task['task_start_time']

    # 初始化 CMAB 档案
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        if w['n_i'] > 0:
            total_q = sum(t['quality'] for t in w['covered_tasks'])
            w['avg_quality'] = total_q / w['n_i']
        else:
            w['avg_quality'] = 0.0
        w['judge_count'] = 1

        # 计算工人可用的轮次（基于任务的原始开始时间）
        w['available_rounds'] = set()
        for t in w['covered_tasks']:
            hour = t['task_start_time'] // 3600
            w['available_rounds'].add(hour)

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

    # 任务覆盖计数（只针对有工人覆盖的任务）
    task_covered_count = {tid: 0 for tid in task_time_map}
    required_workers = {tid: task_weights[tid] for tid in task_time_map}

    total_learned_counts = sum(w['n_i'] for w in workers)

    return workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, task_time_map

# ========== 第三阶段：贪心轮次 ==========
def ucb_quality(worker, total_learned_counts, K):
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def generate_validation_tasks(workers, task_grid_map, task_time_map, Uc, Uu, round_idx, M):
    """
    生成验证任务：只从有 Uc 工人经过的网格中，按 Uu 出现次数排序取前 M 个。
    返回验证任务列表（每个元素为 task_id）。
    """
    # 当前轮可用工人（根据 available_rounds）
    available_workers = [w for w in workers if round_idx in w['available_rounds']]
    if not available_workers:
        return []

    # 统计每个网格中 Uc 和 Uu 的出现次数，并收集该网格属于当前轮的任务
    grid_uc = defaultdict(int)
    grid_uu = defaultdict(int)
    grid_tasks = defaultdict(set)   # 网格 -> 该网格当前轮的任务ID集合

    for w in available_workers:
        wid = w['worker_id']
        for task in w['covered_tasks']:
            # 只考虑当前轮次的任务
            if task['task_start_time'] // 3600 != round_idx:
                continue
            tid = task['task_id']
            gid = task_grid_map.get(tid)
            if gid is None:
                continue
            grid_tasks[gid].add(tid)
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

    # 为每个选中网格随机选取一个任务
    validation_tasks = []
    for g in selected_grids:
        if grid_tasks[g]:
            task = random.choice(list(grid_tasks[g]))
            validation_tasks.append(task)
    return validation_tasks

def update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, round_idx, eta, theta_high, theta_low):
    """
    根据验证任务更新信任度。
    注意：只更新本轮可用工人（即其轨迹覆盖当前轮次）的信任度。
    """
    # 本轮可用工人
    available_workers = [w for w in workers if round_idx in w['available_rounds']]

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
                error = abs(data - base) / base if base != 0 else abs(data - base)
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
    # 当前轮可用工人（根据 available_rounds）
    candidates = [w for w in workers if round_idx in w['available_rounds'] and w['category'] in ('trusted', 'unknown')]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0

    # 调试：打印未完成任务相关工人的信息
    debug_workers = ['073', '149', '104']   # 你关心的工人ID
    for w in candidates:
        if w['worker_id'] in debug_workers:
            bid_tasks = [t for t in w['covered_tasks']
                         if t['task_start_time'] // 3600 == round_idx
                         and task_covered_count[t['task_id']] < required_workers[t['task_id']]]
            if not bid_tasks:
                continue
            cost = len(bid_tasks) * w['covered_tasks'][0]['task_price']
            ucb_q = ucb_quality(w, total_learned_counts, K)
            gain = 0.0
            for t in bid_tasks:
                gain += required_workers[t['task_id']] * ucb_q
            ratio = gain / cost if gain > 0 else 0
            print(f"  调试轮次 {round_idx}: 工人 {w['worker_id']}, bid_tasks={[t['task_id'] for t in bid_tasks]}, cost={cost:.2f}, ucb_q={ucb_q:.4f}, gain={gain:.2f}, ratio={ratio:.4f}")

    round_selected = []
    round_cost = 0.0

    for _ in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        best_bid_tasks = None
        for w in candidates:
            # 找出该工人本轮可以执行的任务（属于当前轮次且未完成）
            bid_tasks = [t for t in w['covered_tasks']
                         if t['task_start_time'] // 3600 == round_idx
                         and task_covered_count[t['task_id']] < required_workers[t['task_id']]]
            if not bid_tasks:
                continue
            # 成本 = 投标任务数 × 工人报价（这里用工人固定报价，每个任务相同）
            cost = len(bid_tasks) * w['covered_tasks'][0]['task_price']
            if cost > remaining_budget:
                continue
            ucb_q = ucb_quality(w, total_learned_counts, K)
            gain = 0.0
            for t in bid_tasks:
                gain += required_workers[t['task_id']] * ucb_q
            ratio = gain / cost if gain > 0 else 0
            if ratio > best_ratio:
                best_ratio = ratio
                best_worker = w
                best_bid_tasks = bid_tasks

        if best_worker is None:
            break
        round_selected.append(best_worker['worker_id'])
        cost = len(best_bid_tasks) * best_worker['covered_tasks'][0]['task_price']
        round_cost += cost
        remaining_budget -= cost

        # 更新任务覆盖计数
        for t in best_bid_tasks:
            tid = t['task_id']
            if task_covered_count[tid] < required_workers[tid]:
                task_covered_count[tid] += 1

        # 更新工人档案
        learned_tasks = len(best_bid_tasks)
        if learned_tasks > 0:
            best_worker['n_i'] += learned_tasks
            # 使用当前平均质量作为新观测（简化）
            observed = best_worker['avg_quality']
            prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
            new_sum = prev_sum + observed * learned_tasks
            best_worker['avg_quality'] = new_sum / best_worker['n_i']
            total_learned_counts += learned_tasks

        candidates.remove(best_worker)

    return round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost

def greedy_recruitment(workers, task_covered_count, required_workers, total_learned_counts,
                       B, K, R, task_grid_map, task_time_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW):
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
    greedy_selected = []
    greedy_rounds = 0

    for t in range(R):
        print(f"\n--- 第 {t} 轮 ---")
        # 打印目标工人的类别和信任度（用于调试）
        for wid in ['073', '149', '104']:
            w = next((w for w in workers if w['worker_id'] == wid), None)
            if w:
                print(f"  工人 {wid}: 类别={w['category']}, trust={w['trust']:.3f}")

        available_workers = [w for w in workers if t in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 当前轮可用任务
        available_tasks = []
        for tid, cnt in task_covered_count.items():
            if cnt >= required_workers[tid]:
                continue
            if task_time_map[tid] // 3600 == t:
                available_tasks.append(tid)

        if not available_tasks:
            print("当前轮无可用任务，终止")
            break

        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, task_time_map,
                                                     Uc, Uu, t, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, t
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
            Uc, Uu, Um = update_trust(workers, validation_tasks, task_grid_map,
                                      Uc, Uu, Um, t, ETA, THETA_HIGH, THETA_LOW)

        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(task_covered_count)}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])

    # 打印最终工人分类
    print("\n最终工人分类统计:")
    print(f"可信工人 ({len(Uc)}): {list(Uc)[:20]}...")
    print(f"未知工人 ({len(Uu)}): {list(Uu)[:20]}...")
    print(f"恶意工人 ({len(Um)}): {list(Um)}")

    # 分析未完成任务
    unfinished_tasks = [tid for tid, cnt in task_covered_count.items() if cnt < required_workers[tid]]
    if unfinished_tasks:
        print("\n" + "="*50)
        print("未完成任务详细分析")
        print("="*50)
        for tid in unfinished_tasks:
            hour = task_time_map[tid] // 3600
            required = required_workers[tid]
            current = task_covered_count[tid]
            print(f"\n任务 {tid}:")
            print(f"  开始时间: {task_time_map[tid]} 秒 -> 第 {hour} 轮")
            print(f"  所需工人数: {required}, 实际覆盖: {current}")
            covering_workers = []
            for w in workers:
                for task in w['covered_tasks']:
                    if task['task_id'] == tid:
                        covering_workers.append(w)
                        break
            print(f"  能覆盖该任务的工人: {[w['worker_id'] for w in covering_workers]}")
            avail_in_hour = [w for w in covering_workers if hour in w['available_rounds']]
            print(f"  在第 {hour} 轮可用的工人: {[w['worker_id'] for w in avail_in_hour]}")
            if len(avail_in_hour) < required:
                print(f"  → 原因：该小时可用工人数不足所需工人数")
            else:
                print(f"  → 原因：虽然可用工人足够，但未在招募中选中足够多的工人（可能是性价比低或预算不足）")

    # 构建结果字典
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
        worker_segments_path='step6_worker_segments.json',
        task_segments_path='step6_task_segments.json',
        output_worker_options_path='step8_worker_option_set.json',
        output_task_weights_path='step8_task_weight_list.json',
        output_task_grid_path='step8_tasks_grid_num.json',
        random_seed=RANDOM_SEED
    )

    # 第二阶段：初始化
    workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, task_time_map = initialize_cmab(
        'step8_worker_option_set.json', 'step8_task_weight_list.json'
    )
    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")

    # 第三阶段：贪心轮次
    task_grid_map = load_json('step8_tasks_grid_num.json')
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid_map}

    result = greedy_recruitment(
        workers, task_covered_count, required_workers, total_learned_counts,
        BUDGET, K, R, task_grid_map, task_time_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW
    )

    print("\n=== 最终结果 ===")
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 10:
            print(f"{k}: {v[:10]}... (共{len(v)})")
        else:
            print(f"{k}: {v}")

    save_json(result, 'step8_final_result.json')
    print("结果已保存至 step8_final_result.json")

if __name__ == '__main__':
    main()