# -*- coding: utf-8 -*-
"""
第二步：CMAB 初始化 + 贪心迭代招募（时间轮次约束）
输入：
  - step7_worker_option_set.json
  - step7_task_weight_list.json
输出：
  - step7_final_recruit.json
"""

import json
import math
from collections import defaultdict

# ==================== 参数配置 ====================
B = 5000          # 总预算
K = 7               # 每轮招募人数
R = 24              # 总轮数（全天24小时）
# =================================================

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def compute_avg_quality(worker):
    """计算工人的平均感知质量"""
    if not worker['covered_tasks']:
        return 0.0
    total_q = sum(task['quality'] for task in worker['covered_tasks'])
    return total_q / len(worker['covered_tasks'])

def ucb_quality(worker, total_learned_counts, K):
    """计算工人的 UCB 质量值"""
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def main():
    # 1. 加载数据
    print("加载数据...")
    worker_data = load_json('step7_worker_option_set.json')
    workers = worker_data['worker_options']
    task_weights_all = load_json('step7_task_weight_list.json')['task_weights']

    # 从工人选项中提取每个任务的时间信息（只保留有工人覆盖的任务）
    task_time_map = {}
    task_weights = {}   # 只包含有工人覆盖的任务的权重
    for w in workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            if tid not in task_time_map:
                task_time_map[tid] = task['start_time']
                task_weights[tid] = task_weights_all[tid]

    # 2. 初始化阶段（学习阶段）
    print("\n=== 初始化阶段 ===")
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        w['avg_quality'] = compute_avg_quality(w)
        w['available_rounds'] = {task['start_time'] // 3600 for task in w['covered_tasks']}

    # 任务覆盖计数（只针对有工人覆盖的任务）
    task_covered_count = {tid: 0 for tid in task_time_map}
    total_learned_counts = sum(w['n_i'] for w in workers)

    print(f"工人总数: {len(workers)}")
    print(f"有工人覆盖的任务总数: {len(task_time_map)}")
    print(f"总学习次数: {total_learned_counts}")

    # 3. 贪心选择阶段
    print("\n=== 贪心选择阶段 ===")
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0

    for t in range(R):
        print(f"\n--- 第 {t} 轮 ---")
        available_workers = [w for w in workers if t in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 当前轮可用的任务（属于该小时且未完成）
        available_tasks = []
        for tid, cnt in task_covered_count.items():
            if cnt >= task_weights[tid]:
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

        selected_this_round = []
        candidates = available_workers[:]
        for _ in range(K):
            if not candidates:
                break
            best_ratio = -1
            best_worker = None
            best_bid_tasks = None
            for w in candidates:
                bid_tasks = []
                for task in w['covered_tasks']:
                    tid = task['task_id']
                    if task['start_time'] // 3600 != t:
                        continue
                    if task_covered_count[tid] >= task_weights[tid]:
                        continue
                    bid_tasks.append(tid)
                if not bid_tasks:
                    continue

                cost = len(bid_tasks) * w['covered_tasks'][0]['task_price']
                if cost > remaining_budget:
                    continue

                ucb_q = ucb_quality(w, total_learned_counts, K)
                gain = sum(task_weights[tid] for tid in bid_tasks) * ucb_q
                ratio = gain / cost if gain > 0 else 0

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_worker = w
                    best_bid_tasks = bid_tasks

            if best_worker is None:
                break

            selected_this_round.append(best_worker['worker_id'])
            greedy_selected.append(best_worker['worker_id'])
            cost = len(best_bid_tasks) * best_worker['covered_tasks'][0]['task_price']
            total_cost += cost
            remaining_budget -= cost

            for tid in best_bid_tasks:
                if task_covered_count[tid] < task_weights[tid]:
                    task_covered_count[tid] += 1

            learned_tasks = len(best_bid_tasks)
            if learned_tasks > 0:
                best_worker['n_i'] += learned_tasks
                observed = best_worker['avg_quality']
                prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
                new_sum = prev_sum + observed * learned_tasks
                best_worker['avg_quality'] = new_sum / best_worker['n_i']
                total_learned_counts += learned_tasks

            candidates.remove(best_worker)

        if selected_this_round:
            greedy_rounds += 1
            # 计算当前已完成的任务数
            completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= task_weights[tid])
            print(f"招募工人: {selected_this_round}, 本轮成本: {cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(task_covered_count)}")
        else:
            print("本轮未招募到工人")

        # 检查所有任务是否完成
        if all(task_covered_count[tid] >= task_weights[tid] for tid in task_covered_count):
            print("所有可完成的任务已完成，终止")
            break

    # 统计最终覆盖的任务数
    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= task_weights[tid])

    # 输出结果
    result = {
        "total_rounds": greedy_rounds,
        "total_cost": total_cost,
        "remaining_budget": remaining_budget,
        "selected_workers": greedy_selected,
        "init_select": len(workers),
        "later_select": len(greedy_selected),
        "covered_task_count": covered_task_count
    }
    save_json(result, 'step7_final_recruit.json')
    print("\n最终结果已保存至 step7_final_recruit.json")
    print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 覆盖任务数: {covered_task_count}/{len(task_covered_count)}")
    print(f"贪心轮数: {greedy_rounds}, 招募工人总人次: {len(greedy_selected)}")

if __name__ == '__main__':
    main()