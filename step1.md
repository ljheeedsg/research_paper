# 1. 车辆模拟数据生成
## 1. step1_vehicles.csv（车辆原始轨迹）字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| vehicle_id | string | 车辆 ID，格式：v{hour}_{idx}，hour 为小时（补两位，如 00/01），idx 为车辆序号（补三位，如 000/001） |
| region_id | int | 区域 ID，取值 0~5 |
| start_time | int | 进入时间（秒），基于整点：0点车辆范围0~3599，1点车辆范围3600~7199，依此类推 |
| end_time | int | 离开时间，end_time = start_time + 停留时间 |
| cost | float | 报价，5~20，保留1位小数，单辆车固定 |
| is_trusted | bool | 可信度，70% True、30% False，单辆车固定 |

## 2. 数据生成规则（核心）

1. 总时长：6小时（0~5点，每小时段独立）
2. 总车辆：900辆（6小时 × 150辆/小时）
3. 区域数量：6个（0~5）
4. 单辆车访问区域数：2~4个（随机，不重复）
5. 第一个区域进入时间：整点后 0~600秒内随机
6. 区域停留时间：60~300秒随机
7. 跨区域行驶时间：0~60秒随机
8. 后续区域start_time = 上一区域end_time + 行驶时间
9. 车辆报价：5~20，保留1位小数，单车全程固定
10. 可信度：70% 为 True，30% 为 False，单车全程固定

## 3. 生成结果验收标准

- ✅ 总记录数：约2000~3000条（900辆 × 每辆2~4区域）
- ✅ 独立车辆数：严格900辆
- ✅ 可信度比例：约70% True（可±5%）
- ✅ 区域覆盖：region_id 0~5 均有分布
- ✅ 时间合理：start_time/end_time 全部在 0~21599 秒内，且 end_time > start_time
- ✅ 报价范围：cost 全部在 [5.0, 20.0] 内

## 4. 示例数据

```csv
vehicle_id,region_id,start_time,end_time,cost,is_trusted
v00_000,0,120,380,12.5,True
v00_000,2,420,680,12.5,True
v00_001,1,300,520,8.3,False
v00_001,3,560,800,8.3,False
```

---


# 2. 任务模拟数据生成

## 2.1 step1_tasks.csv 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 ID，格式：t{region}_{idx}，如 t00_01，region 补两位，idx 补两位 |
| region_id | int | 区域 ID，取值 0~5 |
| start_time | int | 任务开始时间（秒），[0, 18000] |
| end_time | int | 任务结束时间（秒），end_time = start_time + 3600 |
| required_workers | int | 所需工人数，1~3 |

## 2.2 生成规则（核心）

- 区域分配：6个区域（0~5），每个区域20个任务，共120个任务。
- 时间窗口：每个任务固定1小时（3600秒）。
- 时间分布：任务随机分配到6小时内，start_time ∈ [0, 18000]，并保证 end_time ≤ 21600。
- 工人数：随机选 1~3。
- 任务 ID：按区域+序号生成，格式 `t{region_id补两位}_{任务序号补两位}`。

## 2.3 生成结果验收标准

- ✅ 总记录数：120条（6区域 × 20任务）
- ✅ 区域分布：每个区域任务数=20
- ✅ 时间窗口：end_time - start_time = 3600
- ✅ 时间范围：start_time ∈ [0, 18000]，end_time ∈ [3600, 21600]
- ✅ 工人数：required_workers ∈ {1,2,3}

## 2.4 示例数据

```csv
task_id,region_id,start_time,end_time,required_workers
t00_00,0,0,3600,2
t00_01,0,500,4100,1
t01_00,1,3600,7200,2
...```

## 三、step1_worker_segments.json（轨迹时空段）

**作用**：算法输入——按区域分组的车辆轨迹

### 期望格式

```json
{
  "region_0": [
    {
      "vehicle_id": "v00_000",
      "start_time": 120,
      "end_time": 380,
      "cost": 12.5,
      "is_trusted": true
    },
    {
      "vehicle_id": "v00_001",
      "start_time": 300,
      "end_time": 520,
      "cost": 8.3,
      "is_trusted": false
    },
    ...
  ],
  "region_1": [...],
  "region_2": [...],
  "region_3": [...],
  "region_4": [...],
  "region_5": [...]
}
```

### 统计要求

- 6个区域（region_0 ~ region_5）
- 每个区域的 segment 数量应与 `vehicles.csv` 中访问次数一致
- 每个 segment 的 `start_time < end_time`
- `start_time`/`end_time` 均在 [0, 21599] 范围内

## 四、step1_task_segments.json（任务时空段）

**作用**：算法输入——按区域分组的任务窗口

### 期望格式

```json
{
  "region_0": [
    {"task_id": "t00_00", "start_time": 0, "end_time": 3600, "required_workers": 2},
    {"task_id": "t00_20", "start_time": 3600, "end_time": 7200, "required_workers": 1},
    ...
  ],
  "region_1": [...],
  ...
}
```

### 统计要求

- 6个区域（region_0 ~ region_5），每个区域20个任务
- 每个任务 `end_time - start_time = 3600`
- `start_time`在 [0, 18000]，`end_time`在 [3600, 21600]
- `required_workers` 属于 {1,2,3}

---

## 五、快速使用指南

1. 先运行 `generate_vehicles.py` 生成 `vehicles.csv`。
2. 再运行 `generate_tasks.py` 生成 `tasks.csv`。
3. 运行 `extract_segments.py`\ `build_segments.py` 将两者分别转换成 `worker_segments.json`、`task_segments.json`。
4. 将两个JSON输入调度算法进行匹配决策。

---


