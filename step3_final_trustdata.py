import json
import math
import random
from collections import defaultdict

# ========== 可调参数 ==========
B = 150000          # 总预算
K = 3               # 每轮招募人数
MAX_ROUNDS = 10     # 最大贪心轮数
M = 3               # 每轮验证任务数
ETA = 0.2           # 信任度更新步长
THETA_HIGH = 0.8    # 可信阈值
THETA_LOW = 0.2     # 恶意阈值
# =============================

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def compute_avg_quality(worker):
    """计算工人的平均感知质量（总质量/可覆盖任务数）"""
    if not worker['covered_tasks']:
        return 0.0
    total_q = sum(task['quality'] for task in worker['covered_tasks'])
    return total_q / len(worker['covered_tasks'])

def ucb_quality(worker, total_learned_counts):
    """UCB 质量估计（公式10）"""
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def generate_validation_tasks(workers, task_grid_map, Uc_ids, Uu_ids, M):
    """
    生成验证任务：选择 Uu 工人最多的前 M 个网格，每个网格随机选一个任务
    workers: 工人列表（含 covered_tasks, category 等）
    task_grid_map: {task_id: grid_id}
    Uc_ids, Uu_ids: 集合
    M: 验证任务数量
    返回验证任务 ID 列表
    """
    # 统计每个网格中 Uc 和 Uu 工人出现次数
    grid_uc_count = {}
    grid_uu_count = {}
    for w in workers:
        wid = w['worker_id']
        # 获取该工人覆盖的所有任务的网格集合（一个工人可能覆盖多个任务，但只计一次？这里计每个任务一次）
        for task in w['covered_tasks']:
            tid = task['task_id']
            gid = task_grid_map.get(tid)
            if gid is None:
                continue
            if wid in Uc_ids:
                grid_uc_count[gid] = grid_uc_count.get(gid, 0) + 1
            elif wid in Uu_ids:
                grid_uu_count[gid] = grid_uu_count.get(gid, 0) + 1

    # 筛选有 Uc 的网格
    valid_grids = [g for g in grid_uc_count if grid_uc_count[g] > 0]
    # 按 Uu 数量降序排序
    valid_grids.sort(key=lambda g: grid_uu_count.get(g, 0), reverse=True)
    selected_grids = valid_grids[:M]
    # 为每个选中的网格选择一个任务（取该网格的第一个任务，简化）
    validation_tasks = []
    # 构建网格到任务列表的映射
    grid_to_tasks = defaultdict(list)
    for tid, gid in task_grid_map.items():
        grid_to_tasks[gid].append(tid)
    for g in selected_grids:
        if grid_to_tasks[g]:
            # 随机选一个任务作为验证任务
            task = random.choice(grid_to_tasks[g])
            validation_tasks.append(task)
    return validation_tasks

def update_trust(workers, validation_tasks, task_grid_map, Uc_ids, Uu_ids, Um_ids, eta, theta_high, theta_low):
    """更新信任度，并重新分类"""
    for vtask in validation_tasks:
        # 收集完成该任务的 Uc 工人的 task_data
        uc_data = []
        for w in workers:
            if w['worker_id'] in Uc_ids:
                for task in w['covered_tasks']:
                    if task['task_id'] == vtask:
                        uc_data.append(task['task_data'])
        if not uc_data:
            continue
        base = sorted(uc_data)[len(uc_data)//2]  # 中位数
        # 更新 Uu 工人
        for w in workers:
            wid = w['worker_id']
            if wid in Uu_ids:
                # 找到该任务的数据
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
                # 更新信任度
                w['trust'] += eta * (1 - 2 * error)
                w['trust'] = max(0.0, min(1.0, w['trust']))
                # 重新分类
                if w['trust'] >= theta_high:
                    Uc_ids.add(wid)
                    Uu_ids.discard(wid)
                    w['category'] = 'trusted'
                elif w['trust'] <= theta_low:
                    Um_ids.add(wid)
                    Uu_ids.discard(wid)
                    w['category'] = 'malicious'
    return Uc_ids, Uu_ids, Um_ids

def greedy_recruit(worker_options, task_weights, task_grid_map, B, K, max_rounds,
                   M, eta, theta_high, theta_low):
    """
    信任度增强的 UWR 招募算法
    """
    # 过滤掉没有覆盖任务的工人
    workers = [w for w in worker_options if w['covered_tasks']]
    if not workers:
        print("错误：没有工人能覆盖任何任务！")
        return {}

    # 初始化分类
    Uc_ids = set()
    Uu_ids = set()
    Um_ids = set()
    for w in workers:
        if w['category'] == 'trusted':
            Uc_ids.add(w['worker_id'])
        elif w['category'] == 'unknown':
            Uu_ids.add(w['worker_id'])
        else:
            Um_ids.add(w['worker_id'])

    # 任务状态
    task_covered_count = {tid: 0 for tid in task_weights.keys()}
    required_workers = task_weights

    total_cost = 0
    remaining_budget = B
    all_selected_workers = []      # 所有被招募的工人（含初始轮）
    greedy_selected_workers = []   # 仅贪心阶段招募的工人
    greedy_rounds = 0

    # ---------- 初始化阶段（探索） ----------
    print("=== 初始化阶段：招募所有工人，学习质量 ===")
    init_cost = sum(w['total_cost'] for w in workers)
    if init_cost > remaining_budget:
        print(f"预算不足（需要 {init_cost:.2f}，剩余 {remaining_budget:.2f}），无法招募所有工人！")
        return {}
    total_cost += init_cost
    remaining_budget -= init_cost

    # 初始化工人档案
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        w['avg_quality'] = compute_avg_quality(w)
        w['judge_count'] = 1
        all_selected_workers.append(w['worker_id'])

    total_learned_counts = sum(w['n_i'] for w in workers)
    print(f"初始化完成，总花费={total_cost:.2f}, 剩余预算={remaining_budget:.2f}")
    print(f"初始可信工人数: {len(Uc_ids)}, 未知工人数: {len(Uu_ids)}")

    # ---------- 贪心选择阶段 ----------
    round_idx = 1
    while round_idx <= max_rounds:
        # 终止检查
        min_cost = min(w['total_cost'] for w in workers)
        if remaining_budget < min_cost:
            print(f"第{round_idx}轮：剩余预算 {remaining_budget:.2f} 不足以支付任何工人，停止招募。")
            break

        # 检查是否还有未完成的任务
        max_gain = 0
        for w in workers:
            gain = 0.0
            for task in w['covered_tasks']:
                tid = task['task_id']
                if task_covered_count[tid] < required_workers[tid]:
                    gain += required_workers[tid] * task['quality']
            if gain > max_gain:
                max_gain = gain
        if max_gain == 0:
            print(f"第{round_idx}轮：所有工人已无新增任务增益，停止招募。")
            break

        # 生成验证任务（从第二轮开始）
        if round_idx >= 2 and Uc_ids:
            validation_tasks = generate_validation_tasks(workers, task_grid_map, Uc_ids, Uu_ids, M)
            print(f"第{round_idx}轮：生成验证任务 {validation_tasks}")
        else:
            validation_tasks = []

        # 候选工人
        candidate_workers = [w for w in workers if w['worker_id'] in Uc_ids or w['worker_id'] in Uu_ids]
        if not candidate_workers:
            print("没有可用的工人（全部为恶意），停止招募。")
            break

        round_selected = []
        candidates = candidate_workers[:]

        # 选择 K 个工人
        for _ in range(K):
            if not candidates:
                break
            best_ratio = -1
            best_worker = None
            for w in candidates:
                if w['total_cost'] > remaining_budget:
                    continue
                ucb_q = ucb_quality(w, total_learned_counts)
                gain = 0.0
                for task in w['covered_tasks']:
                    tid = task['task_id']
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
            total_cost += best_worker['total_cost']
            remaining_budget -= best_worker['total_cost']
            # 更新任务覆盖计数
            for task in best_worker['covered_tasks']:
                tid = task['task_id']
                if task_covered_count[tid] < required_workers[tid]:
                    task_covered_count[tid] += 1
            # 更新工人档案
            learned_tasks = len(best_worker['covered_tasks'])
            if learned_tasks > 0:
                best_worker['n_i'] += learned_tasks
                observed_quality = best_worker['avg_quality']
                prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
                new_sum = prev_sum + observed_quality * learned_tasks
                best_worker['avg_quality'] = new_sum / best_worker['n_i']
                total_learned_counts += learned_tasks
            candidates.remove(best_worker)

        if not round_selected:
            print(f"第{round_idx}轮：没有选中工人，停止招募。")
            break

        # 记录本轮工人
        greedy_selected_workers.extend(round_selected)
        all_selected_workers.extend(round_selected)
        greedy_rounds += 1

        # 信任度更新（如果有验证任务）
        if validation_tasks:
            Uc_ids, Uu_ids, Um_ids = update_trust(workers, validation_tasks, task_grid_map,
                                                  Uc_ids, Uu_ids, Um_ids, eta, theta_high, theta_low)

        completed_tasks = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"第{round_idx}轮：选择了 {len(round_selected)} 个工人，当前总花费={total_cost:.2f}, "
              f"剩余预算={remaining_budget:.2f}, 已完成任务数={completed_tasks}")
        print(f"  可信工人数: {len(Uc_ids)}, 未知工人数: {len(Uu_ids)}, 恶意工人数: {len(Um_ids)}")

        if remaining_budget < min_cost:
            print("本轮结束后剩余预算不足以支付任何工人，停止招募。")
            break

        if completed_tasks == len(required_workers):
            print("所有任务已完成，停止招募。")
            break

        round_idx += 1

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])

    # 最终可信工人列表
    trusted_workers_list = list(Uc_ids)

    return {
        'total_rounds': greedy_rounds,
        'total_cost': total_cost,
        'remaining_budget': remaining_budget,
        'selected_workers': greedy_selected_workers,
        'init_select': len(all_selected_workers) - len(greedy_selected_workers),
        'later_select': len(greedy_selected_workers),
        'covered_task_count': covered_task_count,
        'trusted_count': len(Uc_ids),
        'malicious_count': len(Um_ids),
        'unknown_count': len(Uu_ids),
        'trusted_workers_list': trusted_workers_list   # 新增字段
    }

def main():
    # 加载数据
    worker_options_data = load_json('step3_worker_option_set.json')
    task_weights_data = load_json('step2_task_weight_list.json')
    task_grid_list = load_json('step3_tasks_grid_num.json')

    worker_options = worker_options_data['worker_options']
    task_weights = task_weights_data['task_weights']
    # 转换为字典 {task_id: grid_id}
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid_list}

    result = greedy_recruit(worker_options, task_weights, task_grid_map,
                            B, K, MAX_ROUNDS, M, ETA, THETA_HIGH, THETA_LOW)

    if result:
        print("\n=== 最终结果 ===")
        print(f"实际贪心轮数: {result['total_rounds']}")
        print(f"总成本: {result['total_cost']:.2f}")
        print(f"剩余预算: {result['remaining_budget']:.2f}")
        print(f"覆盖任务数: {result['covered_task_count']}")
        print(f"初始轮招募工人数: {result['init_select']}")
        print(f"贪心轮招募工人数: {result['later_select']}")
        print(f"可信工人数: {result['trusted_count']}")
        print(f"恶意工人数: {result['malicious_count']}")
        print(f"未知工人数: {result['unknown_count']}")
        print(f"可信工人列表（前10个）: {result['trusted_workers_list'][:10]}")

        save_json({
            'total_rounds': result['total_rounds'],
            'total_cost': result['total_cost'],
            'remaining_budget': result['remaining_budget'],
            'selected_workers': result['selected_workers'],
            'init_select': result['init_select'],
            'later_select': result['later_select'],
            'covered_task_count': result['covered_task_count'],
            'trusted_count': result['trusted_count'],
            'malicious_count': result['malicious_count'],
            'unknown_count': result['unknown_count'],
            'trusted_workers_list': result['trusted_workers_list']   # 保存到JSON
        }, 'step3_final_recruit_with_trust.json')
        print("结果已保存至 step3_final_recruit_with_trust.json")
    else:
        print("算法未能成功运行。")

if __name__ == '__main__':
    main()