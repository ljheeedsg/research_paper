import json
import math

# ========== 可调参数 ==========
alpha = 0.6
beta = 0.4
zeta = 1.0
lambda_ = 2.25
sigma = 0.88
psi_th = 0.5
fee =30          # 手动设置会费
# =============================

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def compute_avg_reward_by_type(task_class):
    member_prices = [t['task_price'] for t in task_class if t['type'] == 'member']
    normal_prices = [t['task_price'] for t in task_class if t['type'] == 'normal']
    R_m = sum(member_prices) / len(member_prices) if member_prices else 0
    R_n = sum(normal_prices) / len(normal_prices) if normal_prices else 0
    return R_m, R_n

def get_worker_covered_tasks(worker, task_type, task_type_map):
    tasks = []
    for task in worker['covered_tasks']:
        tid = task['task_id']
        if task_type_map.get(tid) == task_type:
            tasks.append(tid)
    return tasks

def main():
    worker_data = load_json('step2_worker_option_set.json')
    task_class = load_json('step4_tasks_classification.json')

    task_type_map = {t['task_id']: t['type'] for t in task_class}
    task_price_map = {t['task_id']: t['task_price'] for t in task_class}
    task_cost_map = {t['task_id']: t['worker_cost'] for t in task_class}
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}

    R_m, R_n = compute_avg_reward_by_type(task_class)
    print(f"R_m = {R_m:.2f}, R_n = {R_n:.2f}")

    workers = worker_data['worker_options']
    # 第一轮历史报酬均为0
    for w in workers:
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0

    # 统计工人任务类型分布
    only_member = 0
    only_normal = 0
    both = 0
    personal_lower_bounds = []
    personal_upper_bounds = []

    for w in workers:
        member_tasks = get_worker_covered_tasks(w, 'member', task_type_map)
        normal_tasks = get_worker_covered_tasks(w, 'normal', task_type_map)

        if member_tasks and normal_tasks:
            both += 1
        elif member_tasks:
            only_member += 1
        elif normal_tasks:
            only_normal += 1
        else:
            continue

        # 计算个人上下界（基于所有可覆盖任务，求和）
        lower = sum(task_price_map[tid] - task_system_income_map[tid] for tid in member_tasks + normal_tasks)
        upper = sum(task_price_map[tid] - task_cost_map[tid] for tid in member_tasks + normal_tasks)
        if upper > lower:
            personal_lower_bounds.append(lower)
            personal_upper_bounds.append(upper)

    print(f"\n工人任务覆盖分布：只有会员任务: {only_member}, 只有普通任务: {only_normal}, 两类都有: {both}")
    if personal_lower_bounds:
        lower_max = max(personal_lower_bounds)
        upper_min = min(personal_upper_bounds)
        if lower_max < upper_min:
            print(f"全体工人公共会费区间: [{lower_max:.2f}, {upper_min:.2f}]")
        else:
            print(f"全体工人公共会费区间为空，建议调整数据生成参数")
    else:
        print("无工人同时拥有两类任务，会费无意义")

    members = []
    normals = []
    selected_tasks = set()
    total_fee = 0.0
    total_reward = 0.0
    total_system_income = 0.0
    total_worker_cost = 0.0

    for w in workers:
        member_tasks = get_worker_covered_tasks(w, 'member', task_type_map)
        normal_tasks = get_worker_covered_tasks(w, 'normal', task_type_map)

        if not member_tasks and not normal_tasks:
            continue

        # 只有普通任务
        if not member_tasks:
            psi = 0.0
        # 只有会员任务
        elif not normal_tasks:
            psi = 1.0
        else:
            # 两类任务都有，按公式计算
            # 计算每个任务的预估收益（公式3-2）
            # 对于会员任务，每个任务的预估收益 = alpha * hist_reward_m + beta * R_m
            # 由于第一轮 hist_reward_m=0，所以每个任务 = beta * R_m，总预估收益 = len(member_tasks) * beta * R_m
            # 这里显式计算总预估收益
            total_b_m = sum(alpha * w['hist_reward_m'] + beta * R_m for _ in member_tasks)
            total_b_n = sum(alpha * w['hist_reward_n'] + beta * R_n for _ in normal_tasks)

            delta = beta * (R_m - R_n)
            loss = lambda_ * (delta ** sigma) if delta > 0 else 0.0

            # 计算总成本（求和）
            total_cost_m = sum(task_cost_map[tid] for tid in member_tasks)
            total_cost_n = sum(task_cost_map[tid] for tid in normal_tasks)

            U_member = total_b_m + loss - total_cost_m - fee
            U_normal = total_b_n - total_cost_n

            U_member = min(max(U_member, -100), 100)
            U_normal = min(max(U_normal, -100), 100)
            exp_m = math.exp(zeta * U_member)
            exp_n = math.exp(zeta * U_normal)
            psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

        if psi >= psi_th:
            members.append(w['worker_id'])
            for tid in member_tasks:
                selected_tasks.add(tid)
                total_reward += task_price_map[tid]
                total_system_income += task_system_income_map[tid]
                total_worker_cost += task_cost_map[tid]
            total_fee += fee
        else:
            normals.append(w['worker_id'])
            for tid in normal_tasks:
                selected_tasks.add(tid)
                total_reward += task_price_map[tid]
                total_system_income += task_system_income_map[tid]
                total_worker_cost += task_cost_map[tid]

    platform_utility = total_system_income + total_fee - total_reward
    user_utility = total_reward - total_worker_cost - total_fee

    print("\n=== 算法3-2 单轮结果 ===")
    print(f"会员人数: {len(members)}")
    print(f"普通人数: {len(normals)}")
    print(f"选中任务数: {len(selected_tasks)}")
    print(f"平台效用: {platform_utility:.2f}")
    print(f"用户效用: {user_utility:.2f}")

    result = {
        'members': members,
        'normals': normals,
        'selected_tasks': list(selected_tasks),
        'platform_utility': platform_utility,
        'user_utility': user_utility,
        'fee': fee,
        'only_member_count': only_member,
        'only_normal_count': only_normal,
        'both_count': both,
        'public_lower_max': lower_max if personal_lower_bounds else None,
        'public_upper_min': upper_min if personal_lower_bounds else None
    }
    save_json(result, 'step4_algorithm32_result.json')
    print("结果已保存至 step4_algorithm32_result.json")

if __name__ == '__main__':
    main()