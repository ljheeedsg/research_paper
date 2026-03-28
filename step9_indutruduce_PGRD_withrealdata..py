"""
群智感知双阶段工人招募与信任度验证算法（含 PGRD 会员激励）
适配真实数据（工人按序号合并、24小时轮次、任务时间筛选）
使用前请确保已有 step6_worker_segments.json 和 step6_task_segments.json。
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42

# 预算与招募参数
BUDGET = 100000          # 总预算（可根据任务规模调整）
K = 5                     # 每轮招募人数
R = 24                   # 总轮数（全天24小时）
M_VERIFY = 3             # 每轮验证任务数

# 信任度参数
ETA = 0.4                # 信任度更新步长
THETA_HIGH = 0.8         # 可信阈值
THETA_LOW = 0.2          # 恶意阈值

# PGRD 参数
ALPHA = 0.7              # 历史报酬权重
BETA = 0.3               # 平均报酬权重
ZETA = 1.0               # 差异敏感度
LAMBDA = 2.25            # 损失厌恶系数
SIGMA = 0.88             # 价值函数曲率
PSI_TH = 0.5             # 会员概率阈值
FEE = 2                  # 会费

# 任务分类参数
MEMBER_RATIO = 0.7       # 会员任务比例（可根据数据调整）
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

def generate_task_classification(worker_options_path, task_segments_path, output_task_class_path, random_seed=RANDOM_SEED):
    """
    根据工人选项和任务数据生成任务分类（会员/普通），确保包含所有任务。
    """
    if random_seed is not None:
        random.seed(random_seed)

    # 加载工人选项
    data = load_json(worker_options_path)
    worker_options = data['worker_options']

    # 加载任务数据（获取所有任务 ID）
    task_segments = load_json(task_segments_path)
    all_task_ids = []
    for region_key, tasks in task_segments.items():
        for task in tasks:
            all_task_ids.append(task['task_id'])

    # 收集每个任务的所有报价（从工人覆盖中）
    task_prices = defaultdict(list)
    for w in worker_options:
        for task in w['covered_tasks']:
            tid = task['task_id']
            task_prices[tid].append(task['task_price'])

    # 为每个任务计算平均原始报价，如果任务没有工人覆盖，则用默认值（例如所有任务平均价）
    tasks_info = []
    default_price = 10.0  # 默认报价
    for tid in all_task_ids:
        if tid in task_prices:
            base_price = sum(task_prices[tid]) / len(task_prices[tid])
        else:
            base_price = default_price
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
    print(f"✅ 已生成任务分类 {output_task_class_path}，包含 {len(final_tasks)} 个任务")

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
    task_grid = generate_task_grid_map(task_segments)

    save_json({'worker_options': worker_options}, output_worker_options_path)
    save_json({'task_weights': task_weights}, output_task_weights_path)
    save_json(task_grid, output_task_grid_path)
    generate_task_classification(output_worker_options_path, task_segments_path, output_task_class_path, random_seed)

    print(f"✅ 已生成 {output_worker_options_path}、{output_task_weights_path}、{output_task_grid_path}、{output_task_class_path}")

# ========== 第二阶段：初始化（学习阶段） ==========
def initialize_cmab(worker_options_path, task_weights_path, task_class_path):
    """初始化 CMAB 档案、任务覆盖、工人分类、PGRD 历史报酬，并计算工人可用轮次"""
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)

    # 从工人选项中提取每个任务的开始时间（构建 task_id -> start_time 映射）
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
        # PGRD 历史报酬
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0

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

    # 初始化平均报酬 R_m, R_n
    member_prices = [t['task_price'] for t in task_class if t['type'] == 'member']
    normal_prices = [t['task_price'] for t in task_class if t['type'] == 'normal']
    R_m = sum(member_prices) / len(member_prices) if member_prices else 0
    R_n = sum(normal_prices) / len(normal_prices) if normal_prices else 0

    return workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, R_m, R_n, task_time_map

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

def pgrd_decision(workers, task_class, R_m, R_n, round_idx, fee, alpha, beta, zeta, lam, sigma, psi_th):
    """
    PGRD 会员决策，返回投标任务字典、会员集合、会费总收入。
    """
    # 构建任务信息映射
    task_type = {t['task_id']: t['type'] for t in task_class}
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    # 只考虑本轮可用的工人
    available_workers = [w for w in workers if round_idx in w['available_rounds']]

    bid_tasks = {}
    member_set = set()
    total_fee = 0.0

    for w in available_workers:
        wid = w['worker_id']
        if w['category'] == 'malicious':
            continue
        # 获取该工人覆盖且属于本轮的任务
        member_tasks = []
        normal_tasks = []
        for task in w['covered_tasks']:
            if (task['task_start_time'] // 3600) != round_idx:
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
            member_set.add(wid)
            bid_tasks[wid] = member_tasks
            total_fee += fee
        else:
            bid_tasks[wid] = normal_tasks
    return bid_tasks, member_set, total_fee

def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx, bid_tasks, task_system_income_map):
    """
    执行一轮 CMAB 招募，工人只能从 bid_tasks 中选择任务。
    返回: (round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, round_system_income)
    """
    # 当前轮可用工人（且其投标任务非空）
    candidates = [w for w in workers if round_idx in w['available_rounds'] and bid_tasks.get(w['worker_id'])]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, 0.0

    # 当前轮可用任务（从 bid_tasks 中收集）
    available_tasks = set()
    for w in candidates:
        for tid in bid_tasks[w['worker_id']]:
            available_tasks.add(tid)

    # 去除已完成的可用任务
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
            # 工人投标任务的总成本 = 投标任务数 × 工人报价
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

def greedy_recruitment(workers, task_covered_count, required_workers, total_learned_counts,
                       Uc, Uu, Um, R_m, R_n, B, K, R, task_grid_map, task_time_map,
                       M_VERIFY, ETA, THETA_HIGH, THETA_LOW, PGRD_PARAMS, task_system_income_map):
    total_cost = 0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    total_fee = 0.0
    round_details = []

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        # 当前轮可用的工人（根据 available_rounds）
        available_workers = [w for w in workers if r in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break
        # 检查所有任务是否已完成
        if all(cnt >= required_workers[tid] for tid, cnt in task_covered_count.items()):
            print("所有任务已完成，终止")
            break

        # PGRD 决策
        bid_tasks, member_set, fee_income = pgrd_decision(
            workers, PGRD_PARAMS['task_class'], R_m, R_n, r,
            PGRD_PARAMS['fee'], PGRD_PARAMS['alpha'], PGRD_PARAMS['beta'],
            PGRD_PARAMS['zeta'], PGRD_PARAMS['lam'], PGRD_PARAMS['sigma'], PGRD_PARAMS['psi_th']
        )
        total_fee += fee_income
        print(f"会员人数: {len(member_set)}，会费收入: {fee_income:.2f}")

        # 生成验证任务
        validation_tasks = generate_validation_tasks(workers, task_grid_map, task_time_map, Uc, Uu, r, M_VERIFY)
        print(f"验证任务: {validation_tasks}")

        # CMAB 招募
        round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, _ = cmab_round(
            workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, r, bid_tasks, task_system_income_map
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
        member_rewards_updated = [w['hist_reward_m'] for w in workers if w['worker_id'] in member_set and w['hist_reward_m'] > 0]
        normal_rewards_updated = [w['hist_reward_n'] for w in workers if w['worker_id'] not in member_set and w['hist_reward_n'] > 0]
        if member_rewards_updated:
            R_m = sum(member_rewards_updated) / len(member_rewards_updated)
        if normal_rewards_updated:
            R_n = sum(normal_rewards_updated) / len(normal_rewards_updated)

        # 记录本轮详情
        non_member_set = [wid for w in available_workers if w['worker_id'] not in member_set]
        round_details.append({
            'round': r,
            'member_set': list(member_set),
            'non_member_set': non_member_set,
            'R_m': R_m,
            'R_n': R_n,
            'member_count': len(member_set),
            'non_member_count': len(non_member_set)
        })

        # 统计
        completed = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(required_workers)}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")
        print(f"平均报酬: 会员任务 R_m={R_m:.2f}, 普通任务 R_n={R_n:.2f}")

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
        'trusted_workers_list': list(Uc),
        'total_fee': total_fee,
        'round_details': round_details
    }
    return result

# ========== 主函数 ==========
def main():
    # 输入文件（请确保文件存在）
    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    # 输出文件
    OUTPUT_WORKER_OPTIONS = 'step8_worker_option_set.json'
    OUTPUT_TASK_WEIGHTS = 'step8_task_weight_list.json'
    OUTPUT_TASK_GRID = 'step8_tasks_grid_num.json'
    OUTPUT_TASK_CLASS = 'step8_tasks_classification.json'
    OUTPUT_FINAL = 'step8_final_result.json'

    # 第一阶段：数据准备
    generate_worker_options_and_task_weights(
        worker_segments_path=WORKER_SEGMENTS,
        task_segments_path=TASK_SEGMENTS,
        output_worker_options_path=OUTPUT_WORKER_OPTIONS,
        output_task_weights_path=OUTPUT_TASK_WEIGHTS,
        output_task_grid_path=OUTPUT_TASK_GRID,
        output_task_class_path=OUTPUT_TASK_CLASS,
        random_seed=RANDOM_SEED
    )

    # 第二阶段：初始化
    workers, task_covered_count, required_workers, total_learned_counts, Uc, Uu, Um, R_m, R_n, task_time_map = initialize_cmab(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS
    )
    print(f"初始化完成，工人总数: {len(workers)}，可信: {len(Uc)}，未知: {len(Uu)}")
    print(f"初始平均报酬 R_m={R_m:.2f}, R_n={R_n:.2f}")

    # 加载任务分类和系统收益映射
    task_class = load_json(OUTPUT_TASK_CLASS)
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}

    # 第三阶段：贪心轮次
    task_grid_map = load_json(OUTPUT_TASK_GRID)
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
        BUDGET, K, R, task_grid_map, task_time_map, M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
        PGRD_PARAMS, task_system_income_map
    )

    print("\n=== 最终结果 ===")
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 10:
            print(f"{k}: {v[:10]}... (共{len(v)})")
        elif k == 'round_details':
            print(f"{k}:")
            for rd in v:
                print(f"  轮次 {rd['round']}: 会员人数 {rd['member_count']}, 非会员人数 {rd['non_member_count']}, R_m={rd['R_m']:.2f}, R_n={rd['R_n']:.2f}")
                if rd['member_set']:
                    print(f"      会员名单（前10）: {rd['member_set'][:10]}{'...' if len(rd['member_set'])>10 else ''}")
                if rd['non_member_set']:
                    print(f"      非会员名单（前10）: {rd['non_member_set'][:10]}{'...' if len(rd['non_member_set'])>10 else ''}")
        else:
            print(f"{k}: {v}")

    save_json(result, OUTPUT_FINAL)
    print(f"结果已保存至 {OUTPUT_FINAL}")

if __name__ == '__main__':
    main()