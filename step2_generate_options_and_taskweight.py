import json
from collections import defaultdict

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def parse_worker_segments(segments_by_region):
    """将按区域分组的worker segments转换为以worker_id为键的列表"""
    workers = defaultdict(list)
    for region_id, seg_list in segments_by_region.items():
        for seg in seg_list:
            worker_id = seg['vehicle_id']
            workers[worker_id].append({
                'region_id': int(region_id.split('_')[1]),  # 从 "region_0" 提取0
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'cost': seg['cost'],
                'is_trusted': seg['is_trusted']
            })
    return workers

def parse_tasks(task_segments):
    """将按区域分组的task segments转换为所有任务的列表"""
    tasks = []
    for region_id, task_list in task_segments.items():
        for task in task_list:
            tasks.append({
                'task_id': task['task_id'],
                'region_id': int(region_id.split('_')[1]),
                'start_time': task['start_time'],
                'end_time': task['end_time'],
                'required_workers': task['required_workers']
            })
    return tasks

def compute_intersection(seg, task):
    """计算工人segment与任务的时间交集长度（秒）"""
    start = max(seg['start_time'], task['start_time'])
    end = min(seg['end_time'], task['end_time'])
    if start < end:
        return end - start
    return 0

def generate_worker_options(workers, tasks):
    """为每个工人生成可覆盖的任务列表及质量，总成本 = 覆盖的任务报价之和"""
    worker_options = []
    for worker_id, segments in workers.items():
        # 工人固定成本（取第一个segment的cost，同一工人所有segment的cost相同）
        base_cost = segments[0]['cost']
        covered = []
        for task in tasks:
            best_quality = 0.0
            for seg in segments:
                if seg['region_id'] == task['region_id']:
                    intersect = compute_intersection(seg, task)
                    if intersect > 0:
                        quality = intersect / 3600.0  # 任务固定时长3600秒
                        if quality > best_quality:
                            best_quality = quality
            if best_quality > 0:
                covered.append({
                    'task_id': task['task_id'],
                    'quality': best_quality,
                    'task_price': base_cost   # 每个任务单独报价（未来可不同）
                })
        # 总成本 = 覆盖的所有任务报价之和
        total_cost = sum(task['task_price'] for task in covered)
        worker_options.append({
            'worker_id': worker_id,
            'total_cost': total_cost,
            'covered_tasks': covered
        })
    return worker_options

def generate_task_weights(tasks):
    """生成任务权重字典，权重 = required_workers"""
    return {task['task_id']: task['required_workers'] for task in tasks}

def generate_worker_options_and_task_weights(
    worker_segments_path,
    task_segments_path,
    output_worker_options_path,
    output_task_weights_path
):
    """
    从 worker_segments.json 和 task_segments.json 生成工人选项和任务权重。
    
    参数:
        worker_segments_path (str): 输入工人段JSON路径
        task_segments_path (str): 输入任务段JSON路径
        output_worker_options_path (str): 输出工人选项JSON路径
        output_task_weights_path (str): 输出任务权重JSON路径
    """
    # 加载输入数据
    worker_segments = load_json(worker_segments_path)
    task_segments = load_json(task_segments_path)

    workers = parse_worker_segments(worker_segments)
    tasks = parse_tasks(task_segments)

    # 生成工人可选项
    worker_options = generate_worker_options(workers, tasks)

    # 生成任务权重
    task_weights = generate_task_weights(tasks)

    # 保存结果
    save_json({'worker_options': worker_options}, output_worker_options_path)
    save_json({'task_weights': task_weights}, output_task_weights_path)

    print(f"✅ {output_worker_options_path} 和 {output_task_weights_path} 已生成。")

if __name__ == '__main__':
    # 独立运行时使用默认路径
    generate_worker_options_and_task_weights(
        worker_segments_path='step1_worker_segments.json',
        task_segments_path='step1_task_segments.json',
        output_worker_options_path='step2_worker_option_set.json',
        output_task_weights_path='step2_task_weight_list.json'
    )