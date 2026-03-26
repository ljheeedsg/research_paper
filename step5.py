"""
群智感知双阶段工人招募与信任度验证算法（含 PGRD 会员激励）

本代码实现：
- 第一阶段：数据准备（生成工人可选项、任务权重、网格映射、任务分类）
- 第二阶段：初始化（学习阶段，招募所有工人，初始化CMAB档案、PGRD历史）
- 第三阶段：贪心轮次（多轮迭代，含信任度验证和PGRD会员决策）

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
ETA = 0.4                # 信任度更新步长
THETA_HIGH = 0.8         # 可信阈值
THETA_LOW = 0.2          # 恶意阈值

# PGRD 参数
ALPHA = 0.1              # 历史报酬权重
BETA = 0.9               # 平均报酬权重
ZETA = 1.0               # 差异敏感度
LAMBDA = 2.25            # 损失厌恶系数
SIGMA = 0.88             # 价值函数曲率
PSI_TH = 0.5             # 会员概率阈值
FEE = 3                 # 会费

# 任务分类参数
MEMBER_RATIO = 0.3
MEMBER_MULTIPLIER = 1.5
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

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

def generate_task_classification(worker_options_path, output_task_class_path, random_seed=RANDOM_SEED):
    """根据工人选项生成任务分类（会员/普通）"""
    if random_seed is not None:
        random.seed(random_seed)

    data = load_json(worker_options_path)
    worker_options = data['worker_options']

    # 收集每个任务的所有报价
    task_prices = defaultdict(list)
    for w in worker_options:
        for task in w['covered_tasks']:
            tid = task['task_id']
            task_prices[tid].append(task['task_price'])

    # 计算每个任务的平均原始报价
    tasks_info = []
    for tid, prices in task_prices.items():
        base_price = sum(prices) / len(prices)
        tasks_info.append({'task_id': tid, 'base_price': base_price})

    # 按原始报价降序排序，确定类型
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

    save_json(final_tasks, output_task_class_path)
    print(f"✅ 已生成任务分类 {output_task_class_path}")

def generate_worker_options_and_task_weights(
    worker_segments_path,
    task_segments_path,
    output_worker_options_path,
    output_task_weights_path,
    output_task_grid_path,
    output_task_class_path,
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
    generate_task_classification(output_worker_options_path, output_task_class_path, random_seed)

    print(f"✅ 已生成 {output_worker_options_path}、{output_task_weights_path}、{output_task_grid_path}、{output_task_class_path}")

# ========== 第二阶段：初始化（学习阶段） ==========
def initialize_cmab(worker_options_path, task_weights_path, task_class_path):
    """初始化 CMAB 档案、任务覆盖、工人分类、PGRD 历史报酬"""
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)

    # 初始化 CMAB 档案
    for w in workers:
        w['n_i'] = len(w['covered_tasks'])
        if w['n_i'] > 0:
            total_q = sum(t['quality'] for t in w['covered_tasks'])
            w['avg_quality'] = total_q / w['n_i']
        else:
            w['avg_quality'] = 0.0
        w['judge_count'] = 1
        # PGRD 历史报酬
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0

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

    # 初始化平均报酬 R_m, R_n
    member_prices = [t['task_price'] for t in task_class if t['type'] == 'member']
    normal_prices = [t['task_price'] for t in task_class if t['type'] == 'normal']
    R_m = sum(member_prices) / len(member_prices) if member_prices else 0
    R_n = sum(normal_prices) / len(normal_prices) if normal_prices else 0

    return workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, R_m, R_n

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
    """生成验证任务：只从有 Uc 工人经过的网格中，按 Uu 出现次数排序取前 M 个。"""
    available_workers = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]
    if not available_workers:
        return []

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

    valid_grids = [g for g in grid_uc if grid_uc[g] > 0]
    if not valid_grids:
        return []
    valid_grids.sort(key=lambda g: grid_uu.get(g, 0), reverse=True)
    selected_grids = valid_grids[:M]

    grid_to_tasks_current = defaultdict(list)
    for w in available_workers:
        for task in w['covered_tasks']:
            tid = task['task_id']
            if (task['start_time'] // 3600) == round_idx:
                gid = task_grid_map.get(tid)
                if gid is not None and tid not in grid_to_tasks_current[gid]:
                    grid_to_tasks_current[gid].append(tid)

    validation_tasks = []
    for g in selected_grids:
        if grid_to_tasks_current[g]:
            validation_tasks.append(random.choice(grid_to_tasks_current[g]))
    return validation_tasks

def update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, round_idx, eta, theta_high, theta_low):
    available_workers = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]
    for vtask in validation_tasks:
        uc_data = []
        for w in available_workers:
            if w['worker_id'] in Uc:
                for task in w['covered_tasks']:
                    if task['task_id'] == vtask:
                        uc_data.append(task['task_data'])
                        break
        if not uc_data:
            continue
        base = sorted(uc_data)[len(uc_data)//2]
        for w in available_workers:
            wid = w['worker_id']
            if wid in Uu:
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

# ========== 修改后的 pgrd_decision 函数（确保会费累计） ==========
def pgrd_decision(workers, task_class, R_m, R_n, round_idx, fee, alpha, beta, zeta, lam, sigma, psi_th):
    """
    PGRD 会员决策，返回投标任务字典、会员集合、会费总收入。
    """
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    available_workers = [w for w in workers if int(w['worker_id'][1:3]) == round_idx]

    bid_tasks = {}
    members = set()
    total_fee = 0.0

    for w in available_workers:
        wid = w['worker_id']
        if w['category'] == 'malicious':
            continue
        # 获取该工人覆盖且属于本轮的任务
        member_tasks = []
        normal_tasks = []
        for task in w['covered_tasks']:
            if (task['start_time'] // 3600) != round_idx:
                continue
            tid = task['task_id']
            if task_type[tid] == 'member':
                member_tasks.append(tid)
            else:
                normal_tasks.append(tid)

        if not member_tasks and not normal_tasks:
            bid_tasks[wid] = []
            continue

        # 未知工人不能成为会员
        if w['category'] == 'unknown':
            bid_tasks[wid] = normal_tasks
            continue

        # 可信工人：计算成为会员的概率
        b_m = alpha * w['hist_reward_m'] + beta * R_m
        b_n = alpha * w['hist_reward_n'] + beta * R_n
        delta = beta * (R_m - R_n)
        loss = lam * (delta ** sigma) if delta > 0 else 0.0
        cost_m = sum(task_cost[tid] for tid in member_tasks) / len(member_tasks) if member_tasks else 0.0
        cost_n = sum(task_cost[tid] for tid in normal_tasks) / len(normal_tasks) if normal_tasks else 0.0
        U_mem = b_m + loss - cost_m - fee
        U_nor = b_n - cost_n
        # 防止溢出
        U_mem = min(max(U_mem, -100), 100)
        U_nor = min(max(U_nor, -100), 100)
        exp_m = math.exp(zeta * U_mem)
        exp_n = math.exp(zeta * U_nor)
        psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0
        if psi >= psi_th:
            members.add(wid)
            bid_tasks[wid] = member_tasks
            total_fee += fee          # 累加会费
            # 可选：打印调试信息
            # print(f"Worker {wid} becomes member, fee {fee}, total_fee now {total_fee}")
        else:
            bid_tasks[wid] = normal_tasks
    return bid_tasks, members, total_fee

# ========== 修改后的 cmab_round 函数（增加系统收益累计） ==========
def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx, bid_tasks, task_system_income_map):
    """
    执行一轮 CMAB 招募，工人只能从 bid_tasks 中选择任务。
    返回: (round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, round_system_income)
    """
    candidates = [w for w in workers if int(w['worker_id'][1:3]) == round_idx and bid_tasks.get(w['worker_id'])]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, 0.0

    available_tasks = set()
    for w in candidates:
        for tid in bid_tasks[w['worker_id']]:
            available_tasks.add(tid)

    unfinished_available = [tid for tid in available_tasks if task_covered_count[tid] < required_workers[tid]]
    if not unfinished_available:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, 0.0

    round_selected = []
    round_cost = 0.0
    round_system_income = 0.0
    for _ in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        for w in candidates:
            cost_w = len(bid_tasks[w['worker_id']]) * w['covered_tasks'][0]['task_price']
            if cost_w > remaining_budget:
                continue
            ucb_q = ucb_quality(w, total_learned_counts, K)
            gain = 0.0
            for tid in bid_tasks[w['worker_id']]:
                if task_covered_count[tid] < required_workers[tid]:
                    gain += required_workers[tid] * ucb_q
            if gain <= 0:
                ratio = 0
            else:
                ratio = gain / cost_w
            if ratio > best_ratio:
                best_ratio = ratio
                best_worker = w
        if best_worker is None:
            break
        round_selected.append(best_worker['worker_id'])
        cost_w = len(bid_tasks[best_worker['worker_id']]) * best_worker['covered_tasks'][0]['task_price']
        round_cost += cost_w
        remaining_budget -= cost_w
        # 更新任务覆盖和累计系统收益
        for tid in bid_tasks[best_worker['worker_id']]:
            if task_covered_count[tid] < required_workers[tid]:
                task_covered_count[tid] += 1
                # 累计系统收益（仅当任务第一次完成？实际上每个任务可能被多次覆盖，但系统收益只应计一次？论文中是任务完成后平台获得收益，通常任务只完成一次，这里按任务完成时累加一次）
                # 这里简化：每次覆盖增加计数，但系统收益只在任务刚完成时累加（即从未完成变为完成）。
                # 由于任务可能被多个工人覆盖，只有达到所需工人数才真正完成，所以系统收益应该在达到所需工人数时累加。
                # 但为简单，我们可以在任务计数达到 required_workers 时累加一次 system_income。
                # 这里我们实现为：当任务覆盖计数刚好达到 required_workers 时，累加 system_income。
                if task_covered_count[tid] == required_workers[tid]:
                    round_system_income += task_system_income_map[tid]
        # 更新工人档案
        learned_tasks = len(bid_tasks[best_worker['worker_id']])
        if learned_tasks > 0:
            best_worker['n_i'] += learned_tasks
            observed = best_worker['avg_quality']
            prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned_tasks)
            new_sum = prev_sum + observed * learned_tasks
            best_worker['avg_quality'] = new_sum / best_worker['n_i']
            total_learned_counts += learned_tasks
        candidates.remove(best_worker)
    return round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, round_system_income

# ========== 修改后的 greedy_recruitment 函数（加入系统收益累计和效用计算） ==========
def greedy_recruitment(workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, R_m, R_n, B, K, R, task_grid_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW, PGRD_PARAMS, task_system_income_map):
    total_cost = 0
    remaining_budget = B
    all_selected = []
    greedy_selected = []
    greedy_rounds = 0
    total_fee = 0.0
    total_system_income = 0.0

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if int(w['worker_id'][1:3]) == r]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break
        if all(task_covered_count[tid] >= required_workers[tid] for tid in required_workers):
            print("所有任务已完成，终止")
            break

        # PGRD 决策
        bid_tasks, members, fee_income = pgrd_decision(
            workers, PGRD_PARAMS['task_class'], R_m, R_n, r,
            PGRD_PARAMS['fee'], PGRD_PARAMS['alpha'], PGRD_PARAMS['beta'],
            PGRD_PARAMS['zeta'], PGRD_PARAMS['lam'], PGRD_PARAMS['sigma'], PGRD_PARAMS['psi_th']
        )
        total_fee += fee_income
        print(f"会员人数: {len(members)}，会费收入: {fee_income:.2f}")

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, Uc, Uu, r, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, round_system_income = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r, bid_tasks, task_system_income_map
        )
        total_cost += round_cost
        total_system_income += round_system_income
        if not round_selected:
            print("本轮未选中任何工人")
        else:
            greedy_selected.extend(round_selected)
            greedy_rounds += 1
            print(f"招募工人: {round_selected}")

        # 信任度更新
        if validation_tasks:
            Uc, Uu, Um = update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, r, ETA, THETA_HIGH, THETA_LOW)

        # 更新历史报酬（基于本轮实际完成的任务）
        for wid in round_selected:
            w = next(w for w in workers if w['worker_id'] == wid)
            reward_m = 0
            reward_n = 0
            for tid in bid_tasks.get(wid, []):
                t_info = next(t for t in PGRD_PARAMS['task_class'] if t['task_id'] == tid)
                if t_info['type'] == 'member':
                    reward_m += t_info['task_price']
                else:
                    reward_n += t_info['task_price']
            w['hist_reward_m'] = reward_m
            w['hist_reward_n'] = reward_n

        # 更新平均报酬 R_m, R_n
        member_rewards = [w['hist_reward_m'] for w in workers if w['worker_id'] in members and w['hist_reward_m'] > 0]
        normal_rewards = [w['hist_reward_n'] for w in workers if w['worker_id'] not in members and w['hist_reward_n'] > 0]
        if member_rewards:
            R_m = sum(member_rewards) / len(member_rewards)
        if normal_rewards:
            R_n = sum(normal_rewards) / len(normal_rewards)

        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(required_workers)}")
        print(f"本轮系统收益: {round_system_income:.2f}, 累计系统收益: {total_system_income:.2f}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    platform_utility = total_system_income + total_fee - total_cost
    user_utility = total_cost - total_fee  # 简化：工人总报酬减去会费（因为成本已包含在报酬中，但这里total_cost是支付给工人的总报酬，工人实际成本未统计，可再计算工人成本）
    # 更准确的用户效用 = 工人报酬 - 工人成本 - 会费，但工人成本需要从任务数据中获取，暂时简化。

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
        'trusted_workers_list': list(Uc),
        'total_fee': total_fee,
        'total_system_income': total_system_income,
        'platform_utility': platform_utility,
        'user_utility': user_utility
    }
    return result

# ========== 主函数 ==========
# ========== 修改后的 main 函数（传递 task_system_income_map） ==========
def main():
    # 第一阶段：数据准备
    generate_worker_options_and_task_weights(
        worker_segments_path='step1_worker_segments.json',
        task_segments_path='step1_task_segments.json',
        output_worker_options_path='step5_worker_option_set.json',
        output_task_weights_path='step5_task_weight_list.json',
        output_task_grid_path='step5_tasks_grid_num.json',
        output_task_class_path='step5_tasks_classification.json',
        random_seed=RANDOM_SEED
    )

    # 第二阶段：初始化
    workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, R_m, R_n = initialize_cmab(
        'step5_worker_option_set.json', 'step5_task_weight_list.json', 'step5_tasks_classification.json'
    )
    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")
    print(f"初始平均报酬 R_m={R_m:.2f}, R_n={R_n:.2f}")

    # 加载任务分类和系统收益映射
    task_class = load_json('step5_tasks_classification.json')
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}

    # 第三阶段：贪心轮次
    task_grid_map = load_json('step5_tasks_grid_num.json')
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid_map}

    PGRD_PARAMS = {
        'task_class': task_class,
        'fee': FEE,
        'alpha': ALPHA,
        'beta': BETA,
        'zeta': ZETA,
        'lam': LAMBDA,
        'sigma': SIGMA,
        'psi_th': PSI_TH
    }

    result = greedy_recruitment(
        workers, task_covered_count, required_workers, total_learned_counts,
        Uc, Uu, Um, R_m, R_n,
        BUDGET, K, R, task_grid_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
        PGRD_PARAMS, task_system_income_map
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