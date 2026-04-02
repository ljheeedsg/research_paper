
"""
群智感知双阶段工人招募与信任度验证算法（B4 方案：CMAB + 信任 + PGRD，无 LGSC）
输入：step6_worker_segments.json, step6_task_segments.json
输出：step9_worker_option_set_B4.json, step9_task_weight_list_B4.json, step9_tasks_grid_num_B4.json,
      step9_tasks_classification_B4.json, step9_lgsc_params_B4.json（可不用）, step9_final_result_B4.json
      experiment1_step1_B4_taskcover.json（覆盖率记录）
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# 预算与招募参数
BUDGET = 5000
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
PSI_TH = 0.4
FEE = 2
MEMBER_VALIDITY = 6

# 任务分类参数
MEMBER_RATIO = 0.5
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# LGSC 参数（B4 不使用，但保留定义以免报错）
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

    # LGSC 参数文件（B4 不使用，但保留以兼容）
    lgsc_params = {
        'sunk_threshold': SUNK_THRESHOLD,
        'member_bonus': MEMBER_BONUS,
        'rho_init': RHO_INIT
    }
    save_json(lgsc_params, 'step9_lgsc_params_B4.json')
    print("已保存 LGSC 参数 step9_lgsc_params_B4.json")

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

        # 保留 LGSC 字段（B4 不使用但避免报错）
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

def pgrd_decision(workers, task_class, R_m, R_n, round_idx, fee, alpha, beta, zeta, lam, sigma, psi_th):
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    available_workers = [w for w in workers if round_idx in w['available_rounds']]

    bid_tasks = {}
    new_member_set = set()
    total_fee = 0.0

    for w in sorted(available_workers, key=lambda x: x['worker_id']):
        wid = w['worker_id']
        if w['category'] == 'malicious':
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

        if w['is_member'] and w['member_until'] >= round_idx:
            bid_tasks[wid] = member_tasks + normal_tasks
            continue

        if not member_tasks and not normal_tasks:
            bid_tasks[wid] = []
            continue

        if w['category'] == 'unknown':
            bid_tasks[wid] = normal_tasks
            continue

        if len(member_tasks) == 0:
            bid_tasks[wid] = normal_tasks
            continue

        N_m = len(member_tasks)
        N_n = len(normal_tasks)
        b_m = alpha * w['hist_reward_m'] + beta * R_m
        b_n = alpha * w['hist_reward_n'] + beta * R_n
        delta = R_m - R_n
        loss = lam * (delta ** sigma) if delta > 0 else 0.0
        cost_m = sum(task_cost[tid] for tid in member_tasks) / N_m
        cost_n = sum(task_cost[tid] for tid in normal_tasks) / N_n if N_n > 0 else 0.0

        U_mem = N_m * (b_m + loss - cost_m) - fee
        U_nor = N_n * (b_n - cost_n) if N_n > 0 else -1e9

        U_mem = min(max(U_mem, -100), 100)
        U_nor = min(max(U_nor, -100), 100)

        exp_m = math.exp(zeta * U_mem)
        exp_n = math.exp(zeta * U_nor)
        psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

        if psi >= psi_th:
            new_member_set.add(wid)
            if not w['is_member']:
                w['sunk_value'] = 0.0
                w['sunk_rate'] = RHO_INIT
                w['bonus_count'] = 0
                w['last_period_cost'] = 0.0
            w['is_member'] = True
            w['member_until'] = round_idx + MEMBER_VALIDITY
            bid_tasks[wid] = member_tasks + normal_tasks
            total_fee += fee
        else:
            bid_tasks[wid] = normal_tasks

    return bid_tasks, new_member_set, total_fee

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

def update_history_and_avg(workers, member_set, completed_tasks_per_worker, task_class):
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_price = {t['task_id']: t['task_price'] for t in task_class}
    total_member_reward = 0.0
    total_member_count = 0
    total_normal_reward = 0.0
    total_normal_count = 0

    for w, task_list in completed_tasks_per_worker:
        member_prices = []
        normal_prices = []
        for tid in task_list:
            price = task_price[tid]
            if task_type[tid] == 'member':
                member_prices.append(price)
                total_member_reward += price
                total_member_count += 1
            else:
                normal_prices.append(price)
                total_normal_reward += price
                total_normal_count += 1

        w['hist_reward_m'] = sum(member_prices) / len(member_prices) if member_prices else 0.0
        w['hist_reward_n'] = sum(normal_prices) / len(normal_prices) if normal_prices else 0.0

    R_m = total_member_reward / total_member_count if total_member_count > 0 else 0
    R_n = total_normal_reward / total_normal_count if total_normal_count > 0 else 0
    return R_m, R_n

# ========== B4 主循环（无 LGSC）==========
def greedy_recruitment_B4(workers, task_covered_count, required_workers, total_learned_counts,
                          Uc, Uu, Um, R_m, R_n, B, K, R, task_grid_map, task_time_map,
                          M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
                          PGRD_PARAMS, task_class):
    """B4 方案：CMAB + 信任 + PGRD，无 LGSC"""
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    total_fee = 0.0
    round_details = []

    # ========== 新增 ==========
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}
    total_system_income = 0.0

    # 记录覆盖率
    task_coverage_records = []
    task_completion_records = []   # 存储 (task_id, worker_id, is_trusted)
    trusted_ratio_per_round = []   # 记录每轮的可信任务占比

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if r in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break

        if all(cnt >= required_workers[tid] for tid, cnt in task_covered_count.items()):
            print("所有任务已完成，终止")
            break

        # PGRD 决策
        bid_tasks, new_member_set, fee_income = pgrd_decision(
            workers, task_class, R_m, R_n, r,
            PGRD_PARAMS['fee'], PGRD_PARAMS['alpha'], PGRD_PARAMS['beta'],
            PGRD_PARAMS['zeta'], PGRD_PARAMS['lam'], PGRD_PARAMS['sigma'], PGRD_PARAMS['psi_th']
        )
        total_fee += fee_income
        print(f"新会员人数: {len(new_member_set)}，会费收入: {fee_income:.2f}")

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, task_time_map, Uc, Uu, r, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, completed_tasks = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r, bid_tasks
        )

        total_cost += round_cost
        # ========== 新增 ==========
        for w, task_list in completed_tasks:
            for tid in task_list:
                total_system_income += task_system_income_map[tid]

        # 记录本轮完成的任务
        for w, task_list in completed_tasks:
            is_trusted = (w['worker_id'] in Uc)
            for tid in task_list:
                task_completion_records.append((tid, w['worker_id'], is_trusted))

        if not round_selected:
            print("本轮未选中任何工人")
        else:
            greedy_selected.extend(round_selected)
            greedy_rounds += 1
            print(f"招募工人: {round_selected}")

        # 信任度更新
        if validation_tasks:
            Uc, Uu, Um = update_trust(workers, validation_tasks, task_grid_map, Uc, Uu, Um, r, ETA, THETA_HIGH, THETA_LOW)

        # 更新历史报酬与平均报酬
        R_m, R_n = update_history_and_avg(workers, new_member_set, completed_tasks, task_class)

        # 统计
        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        total_task_num = len(required_workers)
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{total_task_num}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")
        print(f"平均报酬: 会员任务 R_m={R_m:.2f}, 普通任务 R_n={R_n:.2f}")

        # 记录本轮覆盖率
        task_coverage_records.append({
            "round": r,
            "completed_tasks": completed,
            "total_tasks": total_task_num,
            "coverage_rate": round(completed / total_task_num, 4) if total_task_num > 0 else 0.0
        })
        # 统计本轮完成的任务中，由可信工人完成的比例
        if completed_tasks:
            round_total = 0
            round_trusted = 0
            for w, task_list in completed_tasks:
                for tid in task_list:
                    round_total += 1
                    if w['worker_id'] in Uc:
                        round_trusted += 1
            ratio = round_trusted / round_total if round_total > 0 else 0.0
        else:
            ratio = 0.0
        trusted_ratio_per_round.append({
            "round": r,
            "trusted_task_ratio": round(ratio, 4)
        })

        # 记录本轮详情（无 LGSC 字段）
        round_details.append({
            'round': r,
            'member_set': list(new_member_set),
            'non_member_set': [w['worker_id'] for w in available_workers if not w['is_member']],
            'R_m': round(R_m, 2),
            'R_n': round(R_n, 2),
            'member_count': len([w for w in available_workers if w['is_member']]),
            'non_member_count': len([w for w in available_workers if not w['is_member']])
        })

    # 保存覆盖率文件
    save_json(task_coverage_records, "experiment1_step1_B4_taskcover.json")
    save_json(trusted_ratio_per_round, "experiment1_step1_B4_trusted_ratio_per_round.json")
    print(f"✅ 每轮可信任务占比文件已保存：experiment1_step1_B4_trusted_ratio_per_round.json")
    print(f"\n✅ 覆盖率文件已保存：experiment1_step1_B4_taskcover.json")

    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    # ========== 新增 ==========
    platform_utility = total_system_income + total_fee - total_cost

    total_tasks = len(task_completion_records)
    trusted_tasks = sum(1 for _, _, is_trusted in task_completion_records if is_trusted)
    trusted_task_ratio = trusted_tasks / total_tasks if total_tasks > 0 else 0.0
    result = {
        'platform_utility': platform_utility,   # 新增
        'trusted_task_ratio': trusted_task_ratio, # 新增
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
        'round_details': round_details,
        
    }
    return result

# ========== 主函数 ==========
def main():
    random.seed(RANDOM_SEED)

    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    # B4 专用输出文件名
    OUTPUT_WORKER_OPTIONS = 'step9_worker_option_set_B4.json'
    OUTPUT_TASK_WEIGHTS = 'step9_task_weight_list_B4.json'
    OUTPUT_TASK_GRID = 'step9_tasks_grid_num_B4.json'
    OUTPUT_TASK_CLASS = 'step9_tasks_classification_B4.json'
    OUTPUT_FINAL = 'step9_final_result_B4.json'

    # 第一阶段
    worker_options, tasks, task_weights, task_grid = data_preparation(
        WORKER_SEGMENTS, TASK_SEGMENTS,
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
        OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS
    )

    # 第二阶段
    workers, task_covered_count, required_workers, total_learned_counts, \
    Uc, Uu, Um, R_m, R_n, task_time_map = initialize_cmab(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS, 'step9_lgsc_params_B4.json'
    )

    # 准备 PGRD 参数
    task_class = load_json(OUTPUT_TASK_CLASS)
    PGRD_PARAMS = {
        'fee': FEE,
        'alpha': ALPHA,
        'beta': BETA,
        'zeta': ZETA,
        'lam': LAMBDA,
        'sigma': SIGMA,
        'psi_th': PSI_TH
    }

    # 第三阶段（B4）
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid}
    result = greedy_recruitment_B4(
        workers, task_covered_count, required_workers, total_learned_counts,
        Uc, Uu, Um, R_m, R_n,
        BUDGET, K, R, task_grid_map, task_time_map,
        M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
        PGRD_PARAMS, task_class
    )

    save_json(result, OUTPUT_FINAL)
    print(f"\n最终结果已保存至 {OUTPUT_FINAL}")

    # 打印简要结果
    print("\n=== 最终结果 ===")
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 10:
            print(f"{k}: {v[:10]}... (共{len(v)})")
        elif k == 'round_details':
            print(f"{k}:")
            for rd in v[:3]:
                print(f"  轮次 {rd['round']}: 会员人数 {rd['member_count']}, 非会员人数 {rd['non_member_count']}, R_m={rd['R_m']:.2f}, R_n={rd['R_n']:.2f}")
        else:
            print(f"{k}: {v}")

if __name__ == '__main__':
    main()