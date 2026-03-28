import json
data = json.load(open('step8_worker_option_set.json'))
for w in data['worker_options']:
    for task in w['covered_tasks']:
        if task['task_id'] == 't52_04':
            print(f"工人 {w['worker_id']} 覆盖该任务，其 available_rounds 根据任务 start_time 计算")
            # 需要结合任务 start_time 和工人的轨迹段计算可用轮次