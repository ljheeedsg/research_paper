"""
群智感知双阶段工人招募与信任度验证算法（OURS 完整方案：CMAB + 信任 + PGRD + LGSC）
多次重复实验取平均，输出平均结果到原文件名。
输入：step6_worker_segments.json, step6_task_segments.json
输出：step9_final_result_ours.json, experiment1_step1_ours_taskcover.json,
      experiment1_step1_ours_cumulative_trusted_ratio.json,
      experiment1_step1_ours_std_results.json（标准差）
"""

import json
import random
import math
import numpy as np
from collections import defaultdict
import csv

# ========== 参数配置 ==========
RANDOM_SEED = 2
BUDGET = 10000
K = 7
R = 24
M_VERIFY = 7

# 信任度参数
ETA = 0.6
THETA_HIGH = 0.75
THETA_LOW = 0.3

# PGRD 参数
ALPHA = 0.6
BETA = 0.4
ZETA = 1.2
LAMBDA = 1.8
SIGMA = 0.85
PSI_TH = 0.6
FEE = 2
MEMBER_VALIDITY = 3

# 任务分类参数
MEMBER_RATIO = 0.8
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# LGSC 参数
SUNK_THRESHOLD = 20
MEMBER_BONUS = 20
RHO_INIT = 1.0

# 重复次数
NUM_SEEDS = 30

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

    # 同时保存 LGSC 参数（供后续使用）
    lgsc_params = {
        'sunk_threshold': SUNK_THRESHOLD,
        'member_bonus': MEMBER_BONUS,
        'rho_init': RHO_INIT
    }
    save_json(lgsc_params, 'step9_lgsc_params.json')
    print("已保存 LGSC 参数 step9_lgsc_params.json")

    return worker_options, tasks, task_weights, task_grid

# ========== 第二阶段：初始化 ==========
def initialize_cmab(worker_options_path, task_weights_path, task_class_path, lgsc_params_path):
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)
    lgsc = load_json(lgsc_params_path)

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
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0
        w['available_rounds'] = set()
        for t in w['covered_tasks']:
            hour = t['task_start_time'] // 3600
            w['available_rounds'].add(hour)

        w['is_member'] = False
        w['member_until'] = -1
        w['sunk_value'] = 0.0
        w['sunk_rate'] = lgsc['rho_init']
        w['bonus_count'] = 0
        w['last_period_cost'] = 0.0

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

    member_prices = [t['task_price'] for t in task_class if t['type'] == 'member']
    normal_prices = [t['task_price'] for t in task_class if t['type'] == 'normal']
    R_m = sum(member_prices) / len(member_prices) if member_prices else 0
    R_n = sum(normal_prices) / len(normal_prices) if normal_prices else 0

    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")
    print(f"初始平均报酬 R_m={R_m:.2f}, R_n={R_n:.2f}")

    return workers, task_covered_count, required_workers, total_learned_counts, \
           Uc, Uu, Um, R_m, R_n, task_time_map

# ========== 第三阶段：核心函数 ==========
def ucb_quality(worker, total_learned_counts):
    if worker['n_i'] == 0:
        return 1.0
    exploration = math.sqrt((K + 1) * math.log(total_learned_counts) / worker['n_i'])
    return worker['avg_quality'] + exploration

def generate_validation_tasks(workers, task_grid_map, task_time_map, Uc, Uu, round_idx, M):
    available_workers = [w for w in workers if round_idx in w['available_rounds']]
    if not available_workers:
        return []

    grid_uc = defaultdict(int)
    grid_uu = defaultdict(int)
    grid_tasks = defaultdict(set)

    for w in sorted(available_workers, key=lambda x: x['worker_id']):
        wid = w['worker_id']
        for task in w['covered_tasks']:
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

    valid_grids = [g for g in grid_uc if grid_uc[g] > 0]
    if not valid_grids:
        return []
    valid_grids.sort(key=lambda g: (-grid_uu.get(g, 0), g))
    selected_grids = valid_grids[:M]

    validation_tasks = []
    for g in selected_grids:
        if grid_tasks[g]:
            validation_tasks.append(random.choice(list(grid_tasks[g])))
    return validation_tasks

def update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, round_idx, eta, theta_high, theta_low):
    available_workers = [w for w in workers if round_idx in w['available_rounds']]
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

        for w in sorted(available_workers, key=lambda x: x['worker_id']):
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

def pgrd_decision(workers, task_class, R_m, R_n, round_idx, fee, alpha, beta, zeta, lam, sigma, psi_th, member_validity):
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    available_workers = [w for w in workers if round_idx in w['available_rounds']]

    bid_tasks = {}
    new_member_set = set()
    total_fee = 0.0

    for w in available_workers:
        wid = w['worker_id']
        if w['category'] == 'malicious':
            continue

        if w['is_member'] and w['member_until'] >= round_idx:
            member_tasks = []
            for task in w['covered_tasks']:
                if task['task_start_time'] // 3600 == round_idx:
                    tid = task['task_id']
                    if task_type[tid] == 'member':
                        member_tasks.append(tid)
            bid_tasks[wid] = member_tasks
            continue

        member_tasks = []
        normal_tasks = []
        for task in w['covered_tasks']:
            if task['task_start_time'] // 3600 != round_idx:
                continue
            tid = task['task_id']
            if task_type[tid] == 'member':
                member_tasks.append(tid)
            else:
                normal_tasks.append(tid)

        if not member_tasks and not normal_tasks:
            bid_tasks[wid] = []
            continue

        if w['category'] == 'unknown':
            bid_tasks[wid] = normal_tasks
            continue

        b_m = alpha * w['hist_reward_m'] + beta * R_m
        b_n = alpha * w['hist_reward_n'] + beta * R_n
        delta = beta * (R_m - R_n)
        loss = lam * (delta ** sigma) if delta > 0 else 0.0
        cost_m = sum(task_cost[tid] for tid in member_tasks) / len(member_tasks) if member_tasks else 0.0
        cost_n = sum(task_cost[tid] for tid in normal_tasks) / len(normal_tasks) if normal_tasks else 0.0
        U_mem = b_m + loss - cost_m - fee
        U_nor = b_n - cost_n
        U_mem = min(max(U_mem, -100), 100)
        U_nor = min(max(U_nor, -100), 100)
        exp_m = math.exp(zeta * U_mem)
        exp_n = math.exp(zeta * U_nor)
        psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

        if psi >= psi_th:
            new_member_set.add(wid)
            w['is_member'] = True
            w['member_until'] = round_idx + member_validity
            bid_tasks[wid] = member_tasks + normal_tasks
            total_fee += fee
        else:
            bid_tasks[wid] = normal_tasks

    return bid_tasks, new_member_set, total_fee

def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx, bid_tasks, task_price_map):
    candidates = [w for w in workers if round_idx in w['available_rounds']
                  and w['category'] in ('trusted', 'unknown')
                  and bid_tasks.get(w['worker_id'])]
    if not candidates:
        print("CMAB: 无候选工人")
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, []

    print(f"\n=== CMAB 招募开始，候选工人数: {len(candidates)} ===")
    round_selected = []
    round_cost = 0.0
    completed_tasks_per_worker = []

    for step in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        best_bid_tasks = None
        best_cost = 0
        for w in candidates:
            wid = w['worker_id']
            tid_list = bid_tasks[wid]
            actual_bid = [tid for tid in tid_list if task_covered_count[tid] < required_workers[tid]]
            if not actual_bid:
                continue
            cost = sum(task_price_map[tid] for tid in actual_bid)
            if cost > remaining_budget:
                continue
            ucb_q = ucb_quality(w, total_learned_counts)
            gain = sum(required_workers[tid] for tid in actual_bid) * ucb_q
            ratio = gain / cost if gain > 0 else 0
            if ratio > best_ratio:
                best_ratio = ratio
                best_worker = w
                best_bid_tasks = actual_bid
                best_cost = cost
        if best_worker is None:
            break
        round_selected.append(best_worker['worker_id'])
        round_cost += best_cost
        remaining_budget -= best_cost
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

def update_history_and_avg(workers, member_set, completed_tasks_per_worker, task_class):
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_price = {t['task_id']: t['task_price'] for t in task_class}
    for w, task_list in completed_tasks_per_worker:
        reward_m = 0.0
        reward_n = 0.0
        for tid in task_list:
            price = task_price[tid]
            if task_type[tid] == 'member':
                reward_m += price
            else:
                reward_n += price
        w['hist_reward_m'] = reward_m
        w['hist_reward_n'] = reward_n
    member_rewards = []
    normal_rewards = []
    for w in workers:
        if w['is_member'] and w['member_until'] >= 0:
            if w['hist_reward_m'] > 0:
                member_rewards.append(w['hist_reward_m'])
        else:
            if w['hist_reward_n'] > 0:
                normal_rewards.append(w['hist_reward_n'])
    R_m = sum(member_rewards) / len(member_rewards) if member_rewards else 0
    R_n = sum(normal_rewards) / len(normal_rewards) if normal_rewards else 0
    return R_m, R_n

def lgsc_payment(workers, completed_tasks_per_worker, task_class, sunk_threshold, member_bonus, task_price_map, round_idx):
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    total_bonus_paid = 0.0
    sunk_losses = []
    rois = []
    members_above_threshold = 0

    for w, task_list in completed_tasks_per_worker:
        total_cost_this_round = sum(task_cost[tid] for tid in task_list)
        if total_cost_this_round == 0:
            continue
        if not w['is_member'] or w['member_until'] < round_idx:
            continue

        w['sunk_value'] += w['sunk_rate'] * total_cost_this_round
        base_reward = sum(task_price_map[tid] for tid in task_list)
        expected_bonus = (member_bonus / sunk_threshold) * w['sunk_value']
        expected_reward = base_reward + expected_bonus

        if w['sunk_value'] >= sunk_threshold:
            total_bonus_paid += member_bonus
            members_above_threshold += 1
            w['sunk_value'] -= sunk_threshold
            period_cost = w['last_period_cost'] + total_cost_this_round
            w['sunk_rate'] = 1 + (member_bonus * (w['bonus_count'] + 1)) / (member_bonus * (w['bonus_count'] + 1) + period_cost)
            w['bonus_count'] += 1
            w['last_period_cost'] = 0.0
        else:
            if w['sunk_value'] > 0:
                sunk_losses.append(expected_bonus)
            w['last_period_cost'] += total_cost_this_round

        roi = (expected_reward - total_cost_this_round) / total_cost_this_round
        rois.append(roi)

    avg_sunk_loss = sum(sunk_losses) / len(sunk_losses) if sunk_losses else 0.0
    avg_roi = sum(rois) / len(rois) if rois else 0.0
    return total_bonus_paid, avg_sunk_loss, avg_roi, members_above_threshold

# ========== OURS 主循环（单次实验，返回曲线和结果） ==========
def greedy_recruitment_ours(workers, task_covered_count, required_workers, total_learned_counts,
                            Uc, Uu, Um, R_m, R_n, B, K, R, task_grid_map, task_time_map,
                            M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
                            PGRD_PARAMS, LGSC_PARAMS, task_class, member_validity):
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    total_fee = 0.0
    total_bonus_paid = 0.0
    round_details = []

    task_price_map = {t['task_id']: t['task_price'] for t in task_class}
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}
    total_system_income = 0.0

    cumulative_total_tasks = 0
    cumulative_trusted_tasks = 0
    cumulative_trusted_ratio = []
    task_coverage_records = []

    # 新增：存储每轮的工人类别数量
    worker_category_per_round = []

    stop_recruitment = False  # 标记是否停止招募（预算不足/任务完成/无工人）

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")

        # 如果已经停止招募，直接记录当前工人数量并继续下一轮
        if stop_recruitment:
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(Uc),
                "unknown_count": len(Uu),
                "malicious_count": len(Um)
            })
            continue

        available_workers = [w for w in workers if r in w['available_rounds']]
        print(f"可用工人数: {len(available_workers)}")
        if not available_workers:
            print("当前轮无可用工人，停止招募")
            stop_recruitment = True
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(Uc),
                "unknown_count": len(Uu),
                "malicious_count": len(Um)
            })
            continue

        remaining_tasks = sum(1 for tid, cnt in task_covered_count.items() if cnt < required_workers[tid])
        print(f"当前轮未完成任务数: {remaining_tasks}")
        if remaining_tasks == 0:
            print("所有任务已完成，停止招募")
            stop_recruitment = True
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(Uc),
                "unknown_count": len(Uu),
                "malicious_count": len(Um)
            })
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
            print("本轮没有可做的任务，停止招募")
            stop_recruitment = True
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(Uc),
                "unknown_count": len(Uu),
                "malicious_count": len(Um)
            })
            continue
        if remaining_budget < min_cost:
            print("预算不足，停止招募")
            stop_recruitment = True
            worker_category_per_round.append({
                "round": r,
                "trusted_count": len(Uc),
                "unknown_count": len(Uu),
                "malicious_count": len(Um)
            })
            continue

        # PGRD 决策
        bid_tasks, new_member_set, fee_income = pgrd_decision(
            workers, task_class, R_m, R_n, r,
            PGRD_PARAMS['fee'], PGRD_PARAMS['alpha'], PGRD_PARAMS['beta'],
            PGRD_PARAMS['zeta'], PGRD_PARAMS['lam'], PGRD_PARAMS['sigma'], PGRD_PARAMS['psi_th'],
            member_validity
        )
        total_fee += fee_income
        print(f"新会员人数: {len(new_member_set)}，会费收入: {fee_income:.2f}")

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, task_time_map, Uc, Uu, r, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, completed_tasks = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r, bid_tasks, task_price_map
        )

        total_cost += round_cost

        for w, task_list in completed_tasks:
            for tid in task_list:
                total_system_income += task_system_income_map[tid]

        round_total = 0
        round_trusted = 0
        for w, task_list in completed_tasks:
            is_trusted = (w['worker_id'] in Uc)
            for tid in task_list:
                round_total += 1
                if is_trusted:
                    round_trusted += 1

        print(f"本轮完成任务数: {round_total}, 其中可信工人完成: {round_trusted}, 占比: {round_trusted/round_total if round_total>0 else 0:.2%}")

        cumulative_total_tasks += round_total
        cumulative_trusted_tasks += round_trusted
        cumulative_ratio = cumulative_trusted_tasks / cumulative_total_tasks if cumulative_total_tasks > 0 else 0.0
        print(f"累积完成任务数: {cumulative_total_tasks}, 累积可信完成: {cumulative_trusted_tasks}, 累积占比: {cumulative_ratio:.2%}")

        cumulative_trusted_ratio.append({
            "round": r,
            "cumulative_trusted_ratio": round(cumulative_ratio, 4)
        })

        if round_selected:
            recruited_trusted = [wid for wid in round_selected if wid in Uc]
            print(f"招募工人: {round_selected}, 其中可信: {recruited_trusted} (共{len(recruited_trusted)}人)")
        else:
            print("本轮未选中任何工人")

        # 信任度更新
        if validation_tasks:
            Uc, Uu, Um = update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, r, ETA, THETA_HIGH, THETA_LOW)

        # 更新历史报酬与平均报酬
        R_m, R_n = update_history_and_avg(workers, new_member_set, completed_tasks, task_class)

        # LGSC 支付
        bonus_paid, avg_sunk_loss, avg_roi, members_above = lgsc_payment(
            workers, completed_tasks, task_class, LGSC_PARAMS['sunk_threshold'], LGSC_PARAMS['member_bonus'], task_price_map, round_idx=r
        )
        total_bonus_paid += bonus_paid

        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        total_task_num = len(required_workers)
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{total_task_num}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")
        print(f"平均报酬: 会员任务 R_m={R_m:.2f}, 普通任务 R_n={R_n:.2f}")
        print(f"LGSC: 奖励金 {bonus_paid:.2f}, 平均沉没损失 {avg_sunk_loss:.2f}, 平均ROI {avg_roi:.2f}")

        task_coverage_records.append({
            "round": r,
            "completed_tasks": completed,
            "total_tasks": total_task_num,
            "coverage_rate": round(completed / total_task_num, 4) if total_task_num > 0 else 0.0
        })

        round_details.append({
            'round': r,
            'member_set': list(new_member_set),
            'non_member_set': [w['worker_id'] for w in available_workers if not w['is_member']],
            'R_m': round(R_m, 2),
            'R_n': round(R_n, 2),
            'member_count': len([w for w in available_workers if w['is_member']]),
            'non_member_count': len([w for w in available_workers if not w['is_member']]),
            'bonus_paid_this_round': bonus_paid,
            'avg_sunk_loss_this_round': avg_sunk_loss,
            'avg_roi_this_round': round(avg_roi, 2),
            'members_above_threshold': members_above
        })

        # 记录本轮结束时的工人类别数量
        worker_category_per_round.append({
            "round": r,
            "trusted_count": len(Uc),
            "unknown_count": len(Uu),
            "malicious_count": len(Um)
        })

    # 最终统计
    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    platform_utility = total_system_income + total_fee - total_cost - total_bonus_paid

    result = {
        'total_rounds': greedy_rounds,
        'platform_utility': platform_utility,
        'task_price_map': task_price_map,
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
        'total_bonus_paid': total_bonus_paid,
        'round_details': round_details
    }

    coverage_curve = [item['coverage_rate'] for item in task_coverage_records]
    cumulative_curve = [item['cumulative_trusted_ratio'] for item in cumulative_trusted_ratio]
    return result, coverage_curve, cumulative_curve, worker_category_per_round

# ========== 单次实验封装 ==========
def run_experiment_ours(seed, worker_segments_path, task_segments_path,
                        budget, K, R, M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
                        pgrd_params, lgsc_params, member_validity):
    random.seed(seed)

    OUTPUT_WORKER_OPTIONS = 'step9_worker_option_set.json'
    OUTPUT_TASK_WEIGHTS = 'step9_task_weight_list.json'
    OUTPUT_TASK_GRID = 'step9_tasks_grid_num.json'
    OUTPUT_TASK_CLASS = 'step9_tasks_classification.json'

    data_preparation(worker_segments_path, task_segments_path,
                     OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
                     OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS)

    workers, task_covered_count, required_workers, total_learned_counts, \
    Uc, Uu, Um, R_m, R_n, task_time_map = initialize_cmab(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS, 'step9_lgsc_params.json'
    )

    task_class = load_json(OUTPUT_TASK_CLASS)
    task_grid = load_json(OUTPUT_TASK_GRID)
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid}

    result, coverage_curve, cumulative_curve, worker_category_per_round = greedy_recruitment_ours(
        workers, task_covered_count, required_workers, total_learned_counts,
        Uc, Uu, Um, R_m, R_n,
        budget, K, R, task_grid_map, task_time_map,
        M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
        pgrd_params, lgsc_params, task_class, member_validity
    )

    return coverage_curve, cumulative_curve, result, worker_category_per_round

# ========== 主函数：多次重复实验取平均 ==========
def main():
    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    PGRD_PARAMS = {
        'fee': FEE,
        'alpha': ALPHA,
        'beta': BETA,
        'zeta': ZETA,
        'lam': LAMBDA,
        'sigma': SIGMA,
        'psi_th': PSI_TH
    }
    LGSC_PARAMS = {
        'sunk_threshold': SUNK_THRESHOLD,
        'member_bonus': MEMBER_BONUS,
        'rho_init': RHO_INIT
    }

    base_seed = RANDOM_SEED
    seeds = [base_seed + i for i in range(NUM_SEEDS)]

    all_coverage_curves = []
    all_cumulative_curves = []
    all_platform_utils = []
    all_final_coverages = []
    all_total_costs = []
    all_remaining_budgets = []
    all_trusted_counts = []
    all_malicious_counts = []
    all_unknown_counts = []
    all_total_fees = []
    all_total_bonus_paid = []
    # 新增：存储每次实验的工人类别序列
    all_worker_categories = []  # 每个元素是列表，列表元素为字典{'round', 'trusted_count', ...}

    print("获取总任务数...")
    temp_seed = seeds[0]
    random.seed(temp_seed)
    temp_worker_options = 'step9_worker_option_set.json'
    temp_task_weights = 'step9_task_weight_list.json'
    temp_task_grid = 'step9_tasks_grid_num.json'
    temp_task_class = 'step9_tasks_classification.json'
    data_preparation(WORKER_SEGMENTS, TASK_SEGMENTS,
                     temp_worker_options, temp_task_weights,
                     temp_task_grid, temp_task_class)
    task_class_temp = load_json(temp_task_class)
    TOTAL_TASKS = len(task_class_temp)
    print(f"总任务数: {TOTAL_TASKS}")

    for idx, seed in enumerate(seeds):
        print(f"\n========== 运行实验 {idx+1}/{NUM_SEEDS}，随机种子 {seed} ==========")
        coverage_curve, cumulative_curve, result, worker_cat = run_experiment_ours(
            seed, WORKER_SEGMENTS, TASK_SEGMENTS,
            BUDGET, K, R, M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
            PGRD_PARAMS, LGSC_PARAMS, MEMBER_VALIDITY
        )
        all_coverage_curves.append(coverage_curve)
        all_cumulative_curves.append(cumulative_curve)
        all_platform_utils.append(result['platform_utility'])
        all_total_costs.append(result['total_cost'])
        all_remaining_budgets.append(result['remaining_budget'])
        all_trusted_counts.append(result['trusted_count'])
        all_malicious_counts.append(result['malicious_count'])
        all_unknown_counts.append(result['unknown_count'])
        all_total_fees.append(result['total_fee'])
        all_total_bonus_paid.append(result['total_bonus_paid'])
        final_coverage = result['covered_task_count'] / TOTAL_TASKS
        all_final_coverages.append(final_coverage)
        all_worker_categories.append(worker_cat)  # 存储工人类别序列

    # 计算平均覆盖率曲线等（与之前相同）
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

    # 计算工人类别平均数量（每轮）
    # 假设所有实验的 worker_cat 长度都是 R（因为我们已经强制记录R轮）
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

    # 写入工人类别CSV文件
    with open("experiment1_step1_worker_category.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "trusted_count", "unknown_count", "malicious_count"])
        for r in range(num_rounds):
            writer.writerow([r, avg_trusted_per_round[r], avg_unknown_per_round[r], avg_malicious_per_round[r]])
    print("✅ 工人类别变化曲线已保存至 experiment1_step1_worker_category.csv")

    # 其余指标的平均值和保存代码与之前相同
    avg_platform = np.mean(all_platform_utils)
    avg_final_coverage = np.mean(all_final_coverages)
    avg_cost = np.mean(all_total_costs)
    avg_remaining = np.mean(all_remaining_budgets)
    avg_trusted = np.mean(all_trusted_counts)
    avg_malicious = np.mean(all_malicious_counts)
    avg_unknown = np.mean(all_unknown_counts)
    avg_fee = np.mean(all_total_fees)
    avg_bonus = np.mean(all_total_bonus_paid)

    # 保存平均覆盖率曲线
    avg_coverage_records = [
        {
            "round": r,
            "completed_tasks": int(round(avg_coverage[r] * TOTAL_TASKS)),
            "total_tasks": TOTAL_TASKS,
            "coverage_rate": round(avg_coverage[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_coverage_records, "experiment1_step1_ours_taskcover.json")
    print("✅ 平均覆盖率曲线已保存至 experiment1_step1_ours_taskcover.json")

    # 保存平均累积可信任务占比曲线
    avg_cumulative_records = [
        {
            "round": r,
            "cumulative_trusted_ratio": round(avg_cumulative[r], 4)
        }
        for r in range(num_rounds)
    ]
    save_json(avg_cumulative_records, "experiment1_step1_ours_cumulative_trusted_ratio.json")
    print("✅ 平均累积可信任务占比曲线已保存至 experiment1_step1_ours_cumulative_trusted_ratio.json")

    # 保存平均最终结果
    avg_result = {
        'total_rounds': num_rounds,
        'platform_utility': round(avg_platform, 2),
        'total_cost': round(avg_cost, 2),
        'remaining_budget': round(avg_remaining, 2),
        'covered_task_count': int(round(avg_final_coverage * TOTAL_TASKS)),
        'trusted_count': int(round(avg_trusted)),
        'malicious_count': int(round(avg_malicious)),
        'unknown_count': int(round(avg_unknown)),
        'init_select': len(load_json(temp_worker_options)['worker_options']),
        'later_select': int(round(avg_trusted)),
        'trusted_workers_list': [],
        'total_fee': round(avg_fee, 2),
        'total_bonus_paid': round(avg_bonus, 2),
        'round_details': []
    }
    save_json(avg_result, "step9_final_result_ours.json")
    print("✅ 平均最终结果已保存至 step9_final_result_ours.json")

    # 保存标准差结果
    std_result = {
        "std_coverage_per_round": [round(x, 4) for x in std_coverage],
        "std_cumulative_trusted_ratio_per_round": [round(x, 4) for x in std_cumulative],
        "std_platform_utility": round(np.std(all_platform_utils), 2),
        "std_final_coverage_rate": round(np.std(all_final_coverages), 4),
        "std_total_cost": round(np.std(all_total_costs), 2),
        "std_trusted_count": round(np.std(all_trusted_counts), 2),
        "std_malicious_count": round(np.std(all_malicious_counts), 2),
        "std_unknown_count": round(np.std(all_unknown_counts), 2),
        "std_total_fee": round(np.std(all_total_fees), 2),
        "std_total_bonus_paid": round(np.std(all_total_bonus_paid), 2)
    }
    save_json(std_result, "experiment1_step1_ours_std_results.json")
    print("✅ 标准差结果已保存至 experiment1_step1_ours_std_results.json")

if __name__ == '__main__':
    main()