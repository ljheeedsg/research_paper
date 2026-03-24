import json
import math

# ========== 可调参数 ==========
alpha = 0.6
beta = 0.4
zeta = 1.0
lambda_ = 2.25
sigma = 0.88
psi_th = 0.5
fee = 5.0           # 手动设置会费（根据打印的上下界调整）
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

def get_worker_cost(worker, task_type, task_type_map, task_cost_map):
    tasks = get_worker_covered_tasks(worker, task_type, task_type_map)
    if not tasks:
        return 0.0
    costs = [task_cost_map[tid] for tid in tasks]
    return sum(costs) / len(costs)

def main():
    # 加载数据
    worker_data = load_json('step2_worker_option_set.json')
    task_class = load_json('step4_tasks_classification.json')

    task_type_map = {t['task_id']: t['type'] for t in task_class}
    task_price_map = {t['task_id']: t['task_price'] for t in task_class}
    task_cost_map = {t['task_id']: t['worker_cost'] for t in task_class}
    task_system_income_map = {t['task_id']: t['system_income'] for t in task_class}

    # 计算会费上下界（仅用于参考）
    lower_bound = sum(t['task_price'] - t['system_income'] for t in task_class) / len(task_class)
    upper_bound = sum(t['task_price'] - t['worker_cost'] for t in task_class) / len(task_class)
    print(f"会费下界 (平均 task_price - system_income) = {lower_bound:.2f}")
    print(f"会费上界 (平均 task_price - worker_cost)   = {upper_bound:.2f}")
    print(f"当前手动设置会费 = {fee:.2f}")

    R_m, R_n = compute_avg_reward_by_type(task_class)
    print(f"R_m = {R_m:.2f}, R_n = {R_n:.2f}")

    workers = worker_data['worker_options']
    for w in workers:
        w['hist_reward_m'] = 0.0
        w['hist_reward_n'] = 0.0

    members = []
    normals = []
    selected_tasks = set()
    total_fee = 0.0
    total_reward = 0.0
    total_system_income = 0.0
    total_worker_cost = 0.0

    debug = True
    printed = 0
    for w in workers:
        member_tasks = get_worker_covered_tasks(w, 'member', task_type_map)
        normal_tasks = get_worker_covered_tasks(w, 'normal', task_type_map)

        if not member_tasks and not normal_tasks:
            continue

        b_m = alpha * w['hist_reward_m'] + beta * R_m
        b_n = alpha * w['hist_reward_n'] + beta * R_n

        delta = beta * (R_m - R_n)
        if delta <= 0:
            loss = 0.0
        else:
            loss = lambda_ * (delta ** sigma)

        cost_m = get_worker_cost(w, 'member', task_type_map, task_cost_map) if member_tasks else 0.0
        cost_n = get_worker_cost(w, 'normal', task_type_map, task_cost_map) if normal_tasks else 0.0

        U_member = b_m + loss - cost_m - fee
        U_normal = b_n - cost_n

        U_member = min(max(U_member, -100), 100)
        U_normal = min(max(U_normal, -100), 100)
        exp_m = math.exp(zeta * U_member)
        exp_n = math.exp(zeta * U_normal)
        psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

        if debug and printed < 5:
            printed += 1
            print(f"\n工人 {w['worker_id']}:")
            print(f"  member_tasks={member_tasks}, normal_tasks={normal_tasks}")
            print(f"  b_m={b_m:.2f}, b_n={b_n:.2f}")
            print(f"  delta={delta:.4f}, loss={loss:.4f}")
            print(f"  cost_m={cost_m:.2f}, cost_n={cost_n:.2f}")
            print(f"  U_member={U_member:.2f}, U_normal={U_normal:.2f}")
            print(f"  psi={psi:.6f}")

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
        'fee_lower_bound': lower_bound,
        'fee_upper_bound': upper_bound
    }
    save_json(result, 'step4_algorithm32_result.json')
    print("结果已保存至 step4_algorithm32_result.json")

if __name__ == '__main__':
    main()