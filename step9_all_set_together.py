"""
群智感知双阶段工人招募与信任度验证算法（含 PGRD 会员激励 + LGSC 长期留存）
完整实现：数据准备 + 初始化 + 贪心轮次（验证+招募+激励）
输入：step6_worker_segments.json, step6_task_segments.json
输出：step9_worker_option_set.json, step9_task_weight_list.json, step9_tasks_grid_num.json,
      step9_tasks_classification.json, step9_lgsc_params.json, step9_final_result.json

      可信工人初始比例为 0.5，未知工人初始比例为 0.5，恶意工人初始比例为 0。
      每个任务的 required_workers 为1，即每个任务只需1个工人完成即可。
"""

import json
import random
import math
from collections import defaultdict

# ========== 参数配置 ==========
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# 预算与招募参数
BUDGET = 5000          # 总预算
K = 7                    # 每轮招募人数
R = 24                   # 总轮数（全天24小时）
M_VERIFY = 7             # 每轮验证任务数

# 信任度参数
ETA = 0.6                # 信任度更新步长
THETA_HIGH = 0.75         # 可信阈值
THETA_LOW = 0.3          # 恶意阈值

# PGRD 参数
ALPHA = 0.6              # 历史报酬权重
BETA = 0.4               # 平均报酬权重
ZETA = 1.2               # 差异敏感度
LAMBDA = 1.8            # 损失厌恶系数
SIGMA = 0.85             # 价值函数曲率
PSI_TH = 0.2             # 会员概率阈值
FEE = 10                 # 会费
MEMBER_VALIDITY = 6      # 会员有效期（轮数）

# 任务分类参数
MEMBER_RATIO = 0.5       # 会员任务比例
MEMBER_MULTIPLIER = 1.8
NORMAL_MULTIPLIER = 1.0
MEMBER_COST_RANGE = (0.4, 0.6)
NORMAL_COST_RANGE = (0.7, 0.9)
PROFIT_RANGE = (1.2, 2.0)

# LGSC 参数
SUNK_THRESHOLD = 20     # 沉没阈值
MEMBER_BONUS = 20       # 会员奖励金
RHO_INIT = 1.0           # 沉没值初始累计率

# ========== 工具函数 ==========
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)      # 读取 JSON 文件 并返回数据结构 （如 dict 或 list）

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)   # 将数据结构（如 dict 或 list）保存为 JSON 文件，格式化输出

# ========== 第一阶段：数据准备 ==========
def parse_worker_segments(segments_by_region):
    """按工人序号聚合，工人序号从 vehicle_id 提取（如 v00_000 -> 000）"""
    workers = defaultdict(list) # 创建一个默认值是空列表的字典
    for region_key, seg_list in sorted(segments_by_region.items()):
        region = int(region_key.split('_')[1]) # 从 "region_0" 中提取数字部分作为区域ID
        for seg in seg_list:
            vid = seg['vehicle_id']
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
    """生成任务分类（PGRD专用）"""
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
    """第一阶段：生成所有基础数据"""
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
    """初始化 CMAB 档案、任务覆盖、工人分类、PGRD历史、LGSC状态"""
    data = load_json(worker_options_path)
    workers = data['worker_options']
    task_weights = load_json(task_weights_path)['task_weights']
    task_class = load_json(task_class_path)
    lgsc = load_json(lgsc_params_path)

    # 构建任务时间映射
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

        # 可用轮次
        w['available_rounds'] = set()
        for t in w['covered_tasks']:
            hour = t['task_start_time'] // 3600
            w['available_rounds'].add(hour)

        # LGSC 状态
        w['is_member'] = False           # 是否为会员
        w['member_until'] = -1           # 会员有效期截止轮次
        w['sunk_value'] = 0.0            # 沉没值
        w['sunk_rate'] = lgsc['rho_init']  # 沉没累计率
        w['bonus_count'] = 0             # 奖励金提现次数
        w['last_period_cost'] = 0.0      # 上次提现期间总成本

    # 工人分类集合
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

    # PGRD 平均报酬
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
    """生成验证任务"""
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
    """信任度更新"""
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
    """
    PGRD 会员决策
    返回: (bid_tasks, new_member_set, total_fee)
        bid_tasks: dict, worker_id -> list of task_ids (本轮投标的任务)
        new_member_set: set of worker_id (本轮新成为会员的工人)
        total_fee: float (本轮会费总收入)
    """
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

        # 收集本轮可执行的任务（按类型）
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

        # 已经会员且未过期
        if w['is_member'] and w['member_until'] >= round_idx:
            # 会员可以投标所有任务（会员+普通）
            bid_tasks[wid] = member_tasks + normal_tasks
            continue

        # 非会员：没有任务可做则跳过
        if not member_tasks and not normal_tasks:
            bid_tasks[wid] = []
            continue

        # 未知工人不能成为会员，只能投标普通任务
        if w['category'] == 'unknown':
            bid_tasks[wid] = normal_tasks
            continue

        # 可信工人：计算成为会员的概率
        N_m = len(member_tasks)
        N_n = len(normal_tasks)

        # 如果没有会员任务，则不能成为会员（直接投标普通任务）
        if N_m == 0:
            bid_tasks[wid] = normal_tasks
            continue

        # 计算单任务指标
        b_m = alpha * w['hist_reward_m'] + beta * R_m
        b_n = alpha * w['hist_reward_n'] + beta * R_n
        delta = R_m - R_n
        loss = lam * (delta ** sigma) if delta > 0 else 0.0
        cost_m = sum(task_cost[tid] for tid in member_tasks) / N_m
        cost_n = sum(task_cost[tid] for tid in normal_tasks) / N_n if N_n > 0 else 0.0

        # 计算总效用（仅基于会员任务决策，普通任务不计入决策比较）
        U_mem = N_m * (b_m + loss - cost_m) - fee
        U_nor = N_n * (b_n - cost_n) if N_n > 0 else -1e9  # 若无普通任务，则选择普通任务效用极低

        # 防止溢出
        U_mem = min(max(U_mem, -100), 100)
        U_nor = min(max(U_nor, -100), 100)

        exp_m = math.exp(zeta * U_mem)
        exp_n = math.exp(zeta * U_nor)
        psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

        if psi >= psi_th:
            new_member_set.add(wid)
            # ✅【关键】只有 不是会员 的人，才是新会员，才初始化
            if not w['is_member']:  # <--- 你要的判断就在这里！
        # 新会员第一次开通，重置状态
                w['sunk_value'] = 0.0
                w['sunk_rate'] = RHO_INIT
                w['bonus_count'] = 0
                w['last_period_cost'] = 0.0
            w['is_member'] = True
            w['member_until'] = round_idx + MEMBER_VALIDITY   # MEMBER_VALIDITY 为全局常量
            bid_tasks[wid] = member_tasks + normal_tasks      # 成为会员后投标所有任务
            total_fee += fee
        else:
            bid_tasks[wid] = normal_tasks

    return bid_tasks, new_member_set, total_fee

def cmab_round(workers, task_covered_count, required_workers, remaining_budget, K, total_learned_counts, round_idx, bid_tasks):
    """CMAB 招募，返回选中的工人列表、更新后的状态及实际完成的任务列表"""
    candidates = [w for w in workers if round_idx in w['available_rounds']
                  and w['category'] in ('trusted', 'unknown')
                  and bid_tasks.get(w['worker_id'])]
    if not candidates:
        return [], remaining_budget, task_covered_count, total_learned_counts, 0.0, []

    round_selected = []
    round_cost = 0.0
    completed_tasks_per_worker = []  # 记录每个选中工人实际完成的任务列表

    for _ in range(K):
        if not candidates:
            break
        best_ratio = -1
        best_worker = None
        best_bid_tasks = None
        for w in candidates:
            tid_list = bid_tasks[w['worker_id']]
            # 筛选本轮实际未完成的任务
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

        # 记录完成的任务
        completed_tasks_per_worker.append((best_worker, best_bid_tasks))

        # 更新任务覆盖
        for tid in best_bid_tasks:
            if task_covered_count[tid] < required_workers[tid]:
                task_covered_count[tid] += 1

        # 更新工人档案
        learned = len(best_bid_tasks)
        if learned > 0:
            best_worker['n_i'] += learned
            # ========== 唯一核心修改点（cost计算完全保留原写法未改动） ==========
            # 原错误逻辑：用历史平均质量充当本轮观测值，导致质量无法迭代更新，与文档公式不符
            # 修正后：取本轮实际完成任务的真实质量平均值，与文档中加权平均更新公式完全对齐
            task_quality_map = {t['task_id']: t['quality'] for t in best_worker['covered_tasks']}
            observed = sum(task_quality_map[tid] for tid in best_bid_tasks) / learned
            prev_sum = best_worker['avg_quality'] * (best_worker['n_i'] - learned)
            new_sum = prev_sum + observed * learned
            best_worker['avg_quality'] = new_sum / best_worker['n_i']
            total_learned_counts += learned

        candidates.remove(best_worker)

    return round_selected, remaining_budget, task_covered_count, total_learned_counts, round_cost, completed_tasks_per_worker

def update_history_and_avg(workers, member_set, completed_tasks_per_worker, task_class):
    """
    更新工人的历史报酬（平均）和平台平均报酬 R_m, R_n
    参数：
        workers: 工人列表
        member_set: 本轮新会员集合（本函数未使用，保留签名兼容）
        completed_tasks_per_worker: 列表，每个元素为 (worker, task_list)
        task_class: 任务分类列表，每个任务含 task_id, type, task_price
    返回：
        R_m, R_n: 平台平均报酬（基于本轮完成的所有任务）
    """
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

        # 工人历史报酬（平均），按类型分别计算
        w['hist_reward_m'] = sum(member_prices) / len(member_prices) if member_prices else 0.0
        w['hist_reward_n'] = sum(normal_prices) / len(normal_prices) if normal_prices else 0.0

    # 平台平均报酬
    R_m = total_member_reward / total_member_count if total_member_count > 0 else 0
    R_n = total_normal_reward / total_normal_count if total_normal_count > 0 else 0

    return R_m, R_n

def lgsc_payment(workers, completed_tasks_per_worker, task_class, sunk_threshold, member_bonus, task_price_map, round_idx):
    """LGSC 沉没成本激励支付（修复版：正确扣减沉没值、正确计算实际报酬）"""
    task_cost = {t['task_id']: t['worker_cost'] for t in task_class}
    total_bonus_paid = 0.0
    sunk_losses = []
    rois = []
    members_above_threshold = 0

    for w, task_list in completed_tasks_per_worker:
        # 1. 计算本轮完成任务的总成本（对应算法Σc_i^j）
        total_cost_this_round = sum(task_cost[tid] for tid in task_list)
        if total_cost_this_round == 0:
            continue

        # 2. 仅有效会员参与激励
        if not w['is_member'] or w['member_until'] < round_idx:
            continue

        # 3. 算法第9行：更新沉没值 M_i ← M_i + ρ_i * Σc_i^j
        w['sunk_value'] += w['sunk_rate'] * total_cost_this_round

        # 4. 算法第10行：计算预期回报 R_p = Σb_i^j + (Θ/γ)*M_i
        base_reward = sum(task_price_map[tid] for tid in task_list)
        expected_bonus = (member_bonus / sunk_threshold) * w['sunk_value']
        expected_reward = base_reward + expected_bonus

        # 5. 算法第11行：判断是否达到沉没阈值（先判断，再更新状态！）
        if w['sunk_value'] >= sunk_threshold:
            # ✅ 先计算实际报酬（此时sunk_value还未修改，能正确加bonus）
            actual_reward = base_reward + member_bonus
            # ✅ 累加本轮奖励金到总发放额
            total_bonus_paid += member_bonus
            members_above_threshold += 1

            # ✅ 核心修复：不是清零，而是减去阈值！剩余沉没值保留
            w['sunk_value'] = w['sunk_value'] - sunk_threshold

            # ✅ 更新沉没率ρ_i（算法第13行）
            period_cost = w['last_period_cost'] + total_cost_this_round
            w['sunk_rate'] = 1 + (member_bonus * (w['bonus_count'] + 1)) / (member_bonus * (w['bonus_count'] + 1) + period_cost)
            w['bonus_count'] += 1
            w['last_period_cost'] = 0.0  # 周期成本清零，用于下一轮累计
        else:
            # 未达到阈值：仅发放基础报酬，计算沉没损失
            actual_reward = base_reward
            if w['sunk_value'] > 0:
                sunk_loss = expected_bonus  # 算法第15行：H_i = (Θ/γ)*M_i
                sunk_losses.append(sunk_loss)
            # 累计周期成本，用于下一轮更新沉没率
            w['last_period_cost'] += total_cost_this_round

        # 6. 算法第17行：计算投资回报率（基于预期回报，完全对齐公式）
        roi = (expected_reward - total_cost_this_round) / total_cost_this_round
        rois.append(roi)

    # 7. 计算本轮平均统计指标（返回值和原函数完全一致，不影响外部调用）
    avg_sunk_loss = sum(sunk_losses) / len(sunk_losses) if sunk_losses else 0.0
    avg_roi = sum(rois) / len(rois) if rois else 0.0
    return total_bonus_paid, avg_sunk_loss, avg_roi, members_above_threshold

def greedy_recruitment(workers, task_covered_count, required_workers, total_learned_counts,
                       Uc, Uu, Um, R_m, R_n, B, K, R, task_grid_map, task_time_map,
                       M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
                       PGRD_PARAMS, LGSC_PARAMS, task_class):
    """主循环：每轮执行 PGRD -> 验证 -> CMAB -> 信任更新 -> 历史更新 -> LGSC支付"""
    total_cost = 0.0
    remaining_budget = B
    greedy_selected = []
    greedy_rounds = 0
    total_fee = 0.0
    total_bonus_paid = 0.0
    round_details = []

    for r in range(R):
        print(f"\n--- 第 {r} 轮 ---")
        available_workers = [w for w in workers if r in w['available_rounds']]
        if not available_workers:
            print("当前轮无可用工人")
            continue

        # 检查预算
        min_cost = min(w['total_cost'] for w in available_workers)
        if remaining_budget < min_cost:
            print("预算不足，终止")
            break

        # 检查所有任务是否完成
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

        # 在调用 lgsc_payment 前，构建任务价格映射
        task_price_map = {t['task_id']: t['task_price'] for t in task_class}

        # LGSC 支付
        bonus_paid, avg_sunk_loss, avg_roi, members_above = lgsc_payment(
            workers, completed_tasks, task_class, LGSC_PARAMS['sunk_threshold'], LGSC_PARAMS['member_bonus'], task_price_map,round_idx=r
        )
        total_bonus_paid += bonus_paid # 累加总奖励金发放额

        # 统计
        completed = sum(1 
                for tid, cnt in task_covered_count.items() 
                if cnt >= required_workers[tid])
        print(f"总成本: {total_cost:.2f}, 剩余预算: {remaining_budget:.2f}, 已完成任务: {completed}/{len(required_workers)}")
        print(f"可信: {len(Uc)}, 未知: {len(Uu)}, 恶意: {len(Um)}")
        print(f"平均报酬: 会员任务 R_m={R_m:.2f}, 普通任务 R_n={R_n:.2f}")
        print(f"LGSC: 奖励金 {bonus_paid:.2f}, 平均沉没损失 {avg_sunk_loss:.2f}, 平均ROI {avg_roi:.2f}")

        # 记录本轮详情
        round_details.append({
            'round': r,
            'member_set': list(new_member_set),   # 本轮新成为会员的工人
            'non_member_set': [w['worker_id'] for w in available_workers if not w['is_member']],  # 修复变量名
            'R_m': round(R_m, 2),
            'R_n': round(R_n, 2),
            'member_count': len([w for w in available_workers if w['is_member']]),   # 所有会员（包括老会员）
            'non_member_count': len([w for w in available_workers if not w['is_member']]),
            'bonus_paid_this_round': bonus_paid,
            'avg_sunk_loss_this_round': avg_sunk_loss,
            'avg_roi_this_round': round(avg_roi, 2),
            'members_above_threshold': members_above
        })
    # 最终统计
    covered_task_count = sum(1 for tid, cnt in task_covered_count.items() if cnt >= required_workers[tid])
    result = {
        'total_rounds': greedy_rounds,
        # 构建任务价格映射
        'task_price_map': {t['task_id']: t['task_price'] for t in task_class},
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
    return result

# ========== 主函数 ==========
def main():
    # 输入文件
    random.seed(RANDOM_SEED)


    WORKER_SEGMENTS = 'step6_worker_segments.json'
    TASK_SEGMENTS = 'step6_task_segments.json'

    # 输出文件
    OUTPUT_WORKER_OPTIONS = 'step9_worker_option_set.json'
    OUTPUT_TASK_WEIGHTS = 'step9_task_weight_list.json'
    OUTPUT_TASK_GRID = 'step9_tasks_grid_num.json'
    OUTPUT_TASK_CLASS = 'step9_tasks_classification.json'
    OUTPUT_FINAL = 'step9_final_result.json'

    # 第一阶段
    worker_options, tasks, task_weights, task_grid = data_preparation(
        WORKER_SEGMENTS, TASK_SEGMENTS,
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS,
        OUTPUT_TASK_GRID, OUTPUT_TASK_CLASS
    )

    # 第二阶段
    workers, task_covered_count, required_workers, total_learned_counts, \
    Uc, Uu, Um, R_m, R_n, task_time_map = initialize_cmab(
        OUTPUT_WORKER_OPTIONS, OUTPUT_TASK_WEIGHTS, OUTPUT_TASK_CLASS, 'step9_lgsc_params.json'
    )

    # 准备 PGRD 和 LGSC 参数
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
    LGSC_PARAMS = {
        'sunk_threshold': SUNK_THRESHOLD,
        'member_bonus': MEMBER_BONUS,
        'rho_init': RHO_INIT
    }

    # 第三阶段
    task_grid_map = {item['task_id']: item['grid_id'] for item in task_grid}

    result = greedy_recruitment(
        workers, task_covered_count, required_workers, total_learned_counts,
        Uc, Uu, Um, R_m, R_n,
        BUDGET, K, R, task_grid_map, task_time_map,
        M_VERIFY, ETA, THETA_HIGH, THETA_LOW,
        PGRD_PARAMS, LGSC_PARAMS, task_class
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