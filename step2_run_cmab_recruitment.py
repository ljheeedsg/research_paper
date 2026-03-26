import json
import math

# ========== 可调参数（作为函数参数） ==========
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

def ucb_quality(worker, total_learned_counts, K):
    """计算工人的 UCB 质量值（论文公式10）"""
    if worker['n_i'] == 0:
        return 1.0  # 从未学习，取最大上界
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def greedy_recruit(worker_options, task_weights, B, K, max_rounds):
    """
    论文 Algorithm 1 实现，增加最大轮数限制，任务覆盖需达到 required_workers
    """
    # 过滤掉没有覆盖任务的工人
    workers = [w for w in worker_options if w['covered_tasks']]
    if not workers:
        print("错误：没有工人能覆盖任何任务！")
        return {
            'total_rounds': 0,
            'total_cost': 0,
            'remaining_budget': B,
            'selected_workers': [],
            'init_select': 0,
            'later_select': 0,
            'covered_task_count': 0
        }

    # 任务覆盖计数：每个任务当前已被多少个工人覆盖
    task_covered_count = {task_id: 0 for task_id in task_weights.keys()}
    # 记录每个任务所需工人数（从 task_weights 获取）
    required_workers = task_weights  # 字典 {task_id: required_workers}

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
        return {
            'total_rounds': 0,
            'total_cost': 0,
            'remaining_budget': B,
            'selected_workers': [],
            'init_select': 0,
            'later_select': 0,
            'covered_task_count': 0
        }
    total_cost += init_cost
    remaining_budget -= init_cost

    # 初始化工人档案
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])        # 学习次数 = 覆盖的任务数
        w['avg_quality'] = compute_avg_quality(w)
        w['judge_count'] = 1
        all_selected_workers.append(w['worker_id'])

    # 总学习次数
    total_learned_counts = sum(w['n_i'] for w in workers)

    print(f"初始化完成，总花费={total_cost:.2f}, 剩余预算={remaining_budget:.2f}")

    # ---------- 贪心选择阶段 ----------
    round_idx = 1
    while True:
        # 达到最大轮数则停止
        if round_idx > max_rounds:
            print(f"已达到最大轮数限制 {max_rounds}，停止招募。")
            break

        # 检查剩余预算是否还能支付任何工人
        min_cost = min(w['total_cost'] for w in workers)
        if remaining_budget < min_cost:
            print(f"第{round_idx}轮：剩余预算 {remaining_budget:.2f} 不足以支付任何工人，停止招募。")
            break

        # 检查是否还有未完成的任务（即当前覆盖计数 < required_workers）
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

        round_selected = []
        candidates = workers[:]

        # 在本轮中选择 K 个工人
        for _ in range(K):
            if not candidates:
                break
            best_ratio = -1
            best_worker = None
            for w in candidates:
                # 必须确保预算足够支付该工人
                if w['total_cost'] > remaining_budget:
                    continue
                # 计算该工人的 UCB 质量
                ucb_q = ucb_quality(w, total_learned_counts, K)
                # 计算边际增益（UCB质量下的加权任务质量，只考虑未完成的任务）
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
                break  # 没有符合条件的工人

            # 选择该工人
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
                # 模拟观测质量（这里使用工人当前平均质量作为新观测值）
                observed_quality = best_worker['avg_quality']
                prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
                new_sum = prev_sum + observed_quality * learned_tasks
                best_worker['avg_quality'] = new_sum / best_worker['n_i']
                total_learned_counts += learned_tasks

            candidates.remove(best_worker)

        if not round_selected:
            print(f"第{round_idx}轮：没有选中工人，停止招募。")
            break

        # 记录本轮选中的工人
        greedy_selected_workers.extend(round_selected)
        all_selected_workers.extend(round_selected)
        greedy_rounds += 1

        # 计算已完成任务数（计数达到 required_workers 的任务）
        completed_tasks = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"第{round_idx}轮：选择了 {len(round_selected)} 个工人，当前总花费={total_cost:.2f}, 剩余预算={remaining_budget:.2f}, 已完成任务数={completed_tasks}")

        # 再次检查剩余预算是否还能支付任何工人
        if remaining_budget < min_cost:
            print("本轮结束后剩余预算不足以支付任何工人，停止招募。")
            break

        # 如果所有任务都已完成，停止
        if completed_tasks == len(required_workers):
            print("所有任务已完成，停止招募。")
            break

        round_idx += 1

    # 最终统计已完成任务数
    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])

    return {
        'total_rounds': greedy_rounds,
        'total_cost': total_cost,
        'remaining_budget': remaining_budget,
        'selected_workers': greedy_selected_workers,      # 仅贪心阶段工人
        'init_select': len(all_selected_workers) - len(greedy_selected_workers),  # 初始轮人数
        'later_select': len(greedy_selected_workers),
        'covered_task_count': covered_task_count
    }

def run_cmab_recruitment(
    worker_options_path,
    task_weights_path,
    output_path,
    B=118000,
    K=3,
    max_rounds=15
):
    """
    执行 CMAB 招募算法，从输入文件读取数据，输出结果到 JSON 文件。
    
    参数:
        worker_options_path (str): 工人选项文件路径 (step2_worker_option_set.json)
        task_weights_path (str): 任务权重文件路径 (step2_task_weight_list.json)
        output_path (str): 输出结果文件路径 (step2_final_recruit.json)
        B (float): 总预算
        K (int): 每轮招募人数
        max_rounds (int): 最大贪心轮数
    返回:
        dict: 结果字典，包含 total_rounds, total_cost, remaining_budget, selected_workers, 
              init_select, later_select, covered_task_count
    """
    worker_options_data = load_json(worker_options_path)
    task_weights_data = load_json(task_weights_path)

    worker_options = worker_options_data['worker_options']
    task_weights = task_weights_data['task_weights']

    result = greedy_recruit(worker_options, task_weights, B, K, max_rounds)

    print("\n=== CMAB 招募结果 ===")
    print(f"实际贪心轮数: {result['total_rounds']}")
    print(f"总成本: {result['total_cost']:.2f}")
    print(f"剩余预算: {result['remaining_budget']:.2f}")
    print(f"覆盖任务数: {result['covered_task_count']}")
    print(f"初始轮招募工人数: {result['init_select']}")
    print(f"贪心轮招募工人数: {result['later_select']}")

    save_json({
        'total_rounds': result['total_rounds'],
        'total_cost': result['total_cost'],
        'remaining_budget': result['remaining_budget'],
        'selected_workers': result['selected_workers'],
        'init_select': result['init_select'],
        'later_select': result['later_select'],
        'covered_task_count': result['covered_task_count']
    }, output_path)
    print(f"结果已保存至 {output_path}")

    return result

if __name__ == '__main__':
    # 独立运行时使用默认参数
    run_cmab_recruitment(
        worker_options_path='step2_worker_option_set.json',
        task_weights_path='step2_task_weight_list.json',
        output_path='step2_final_recruit.json',
        B=118000,
        K=3,
        max_rounds=15
    )