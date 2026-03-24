import json
import random

def generate_task_classification(
    t=0.3,                      # 会员任务比例
    member_multiplier=1.5,      # 会员任务报酬倍数
    normal_multiplier=1.0,      # 普通任务报酬倍数
    member_cost_range=(0.4, 0.6),   # 会员任务成本占报酬的比例范围
    normal_cost_range=(0.7, 0.9),   # 普通任务成本占报酬的比例范围
    profit_range=(1.2, 2.0),    # 系统收益占报酬的比例范围
    random_seed=42
):
    """
    从 step2_worker_option_set.json 生成 step4_tasks_classification.json
    """
    if random_seed is not None:
        random.seed(random_seed)

    # 加载数据
    with open('step2_worker_option_set.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    worker_options = data['worker_options']

    # 收集每个任务的原始报价列表
    task_prices = {}
    for worker in worker_options:
        for task in worker['covered_tasks']:
            tid = task['task_id']
            price = task['task_price']
            task_prices.setdefault(tid, []).append(price)

    # 计算每个任务的平均原始报价
    tasks_info = []
    for tid, prices in task_prices.items():
        base_price = sum(prices) / len(prices)
        tasks_info.append({
            'task_id': tid,
            'base_price': base_price,
        })

    # 按原始报价降序排序，确定类型
    tasks_info.sort(key=lambda x: x['base_price'], reverse=True)
    m = len(tasks_info)
    k = int(t * m)

    # 生成最终数据
    final_tasks = []
    for idx, info in enumerate(tasks_info):
        tid = info['task_id']
        base_price = info['base_price']
        is_member = idx < k

        # 确定报酬
        if is_member:
            task_price = base_price * member_multiplier
            cost_ratio = random.uniform(*member_cost_range)
        else:
            task_price = base_price * normal_multiplier
            cost_ratio = random.uniform(*normal_cost_range)

        # 工人成本
        worker_cost = task_price * cost_ratio
        # 系统收益
        system_income = task_price * random.uniform(*profit_range)
        pure_income = task_price - worker_cost

        final_tasks.append({
            'task_id': tid,
            'task_price': round(task_price, 2),
            'worker_cost': round(worker_cost, 2),
            'system_income': round(system_income, 2),
            'pure_worker_income': round(pure_income, 2),
            'type': 'member' if is_member else 'normal'
        })

    # 按工人净收益降序排序（可选）
    final_tasks.sort(key=lambda x: x['pure_worker_income'], reverse=True)

    # 保存结果
    with open('step4_tasks_classification.json', 'w', encoding='utf-8') as f:
        json.dump(final_tasks, f, indent=2, ensure_ascii=False)

    # 输出统计信息
    print(f"step4_tasks_classification.json 已生成，共 {m} 个任务，会员任务 {k} 个。")
    member_prices = [t['task_price'] for t in final_tasks if t['type'] == 'member']
    normal_prices = [t['task_price'] for t in final_tasks if t['type'] == 'normal']
    member_incomes = [t['pure_worker_income'] for t in final_tasks if t['type'] == 'member']
    normal_incomes = [t['pure_worker_income'] for t in final_tasks if t['type'] == 'normal']
    if member_prices:
        print(f"会员任务平均报酬: {sum(member_prices)/len(member_prices):.2f}")
        print(f"会员任务平均净收益: {sum(member_incomes)/len(member_incomes):.2f}")
    if normal_prices:
        print(f"普通任务平均报酬: {sum(normal_prices)/len(normal_prices):.2f}")
        print(f"普通任务平均净收益: {sum(normal_incomes)/len(normal_incomes):.2f}")

if __name__ == '__main__':
    generate_task_classification()