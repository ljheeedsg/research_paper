# 北京出租车轨迹数据处理完整文档

## 1. 概述

本项目处理北京市300辆出租车在2008年2月3日的GPS轨迹数据，通过网格化、时空分段、工人属性生成、任务生成等步骤，为众包任务分配算法提供输入。整个流程分为三个主要阶段：

1. **轨迹预处理**：从原始GPS点生成车辆时空段（含成本、可信度属性）
2. **工人数据导出**：将车辆段转换为按区域分组的JSON格式
3. **任务生成**：基于工人时空容量生成模拟任务并可视化分布

---

## 2. 文件结构

```
project/
├── dataset/
│   └── beijing_300_cars_2008-02-03.csv    # 原始数据
├── step1_generate_segments.py             # 第一阶段：轨迹分段
├── step2_generate_worker_json.py          # 第二阶段：导出工人JSON
├── step3_generate_tasks.py                # 第三阶段：生成任务
├── run_all.py                             # 一键运行脚本（可选）
└── 输出文件（运行后生成）：
    ├── step6_vehicle.csv                  # 车辆轨迹段
    ├── step6_grid_partition.png           # 网格划分及密度图
    ├── step6_worker_segments.json         # 工人时空段（按区域）
    ├── step6_tasks.csv                    # 任务列表
    ├── step6_task_segments.json           # 任务时空段（按区域）
    └── step6_tasks_distribution.png       # 任务分布图（叠加工人密度）
```

---

## 3. 运行环境与依赖

- Python 3.7+
- 依赖库：
  - `numpy`
  - `matplotlib`
  - `csv`（内置）
  - `json`（内置）
  - `collections`（内置）
  - `random`（内置）

安装依赖：
```bash
pip install numpy matplotlib
```

---

## 4. 数据说明

### 原始输入：`beijing_300_cars_2008-02-03.csv`
必须包含以下列（列名不区分大小写）：
- `taxi_id` / `taxiid` / `id`：车辆标识符（字符串或整数）
- `time_sec` / `time` / `timestamp`：时间（秒，从当日0点起）
- `lat` / `latitude`：纬度
- `lon` / `longitude` / `lon`：经度

示例行：
```
taxi_id,time_sec,lat,lon
1,3600,39.9042,116.4074
```

---

## 5. 详细步骤

### 5.1 第一阶段：轨迹分段 (`step1_generate_segments.py`)

**目的**：将原始GPS点转换为连续的时间段，每个时间段对应车辆停留在某个网格内，并赋予成本(`cost`)和可信度(`is_trusted`)。

**核心算法**：

1. **读取数据**：自动识别列名，提取车辆ID、时间、经纬度。
2. **确定研究区域**：
   - 计算所有点的1%和99%分位数作为初始矩形
   - 将矩形中心偏移 `SHIFT_LON`, `SHIFT_LAT`（默认-0.08°, -0.08°）
3. **网格划分**：将矩形划分为 `GRID_X_NUM × GRID_Y_NUM`（默认10×10）个网格，每个网格分配唯一 `region_id`（0~99）。
4. **为每个点分配 region_id**：基于经纬度落在的网格。
5. **构建原始轨迹段**：按车辆分组，按时间排序，相邻两点之间生成一个段 `(region_id, start_time, end_time)`。  
   *注：start_time为前一个点的时间（第一个点）或前一段结束时间+1，end_time为后一个点的时间。*
6. **合并同区域连续段**：如果同一车辆连续多个段都在同一网格内，则合并为一个更长的时间段。
7. **按小时切分**：确保每个段不跨小时边界（跨小时则拆分为多个段）。
8. **车辆ID重编号**：
   - 仅保留有轨迹段的车辆
   - 按原始ID数值升序映射为 `1, 2, 3, ...`
9. **生成随机属性**：
   - `cost`：均匀分布 `[COST_MIN, COST_MAX]`（默认5~20）
   - `is_trusted`：以 `TRUSTED_RATIO`（默认0.5）概率为True
10. **输出CSV**：列包括 `vehicle_id`, `region_id`, `start_time`, `end_time`, `cost`, `is_trusted`。

**可视化输出**：`step6_grid_partition.png`  
- 左子图：矩形内的所有GPS点 + 网格线
- 右子图：每个网格内的点数量热力图

**配置参数**（脚本开头可修改）：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_CSV` | `dataset/beijing_300_cars_2008-02-03.csv` | 输入文件路径 |
| `OUTPUT_SEG` | `step6_vehicle.csv` | 输出CSV路径 |
| `OUTPUT_PLOT` | `step6_grid_partition.png` | 输出图片路径 |
| `LOW_PERCENTILE` | 1 | 裁剪下界百分位 |
| `HIGH_PERCENTILE` | 99 | 裁剪上界百分位 |
| `SHIFT_LON` | -0.08 | 经度偏移量（度） |
| `SHIFT_LAT` | -0.08 | 纬度偏移量（度） |
| `GRID_X_NUM` | 10 | 经向网格数 |
| `GRID_Y_NUM` | 10 | 纬向网格数 |
| `COST_MIN` | 5 | 最小成本 |
| `COST_MAX` | 20 | 最大成本 |
| `TRUSTED_RATIO` | 0.5 | 可信工人比例 |
| `POINT_SIZE` | 1 | 散点图点大小 |
| `POINT_ALPHA` | 0.5 | 散点透明度 |
| `random.seed` | 42 | 随机种子 |

---

### 5.2 第二阶段：生成工人JSON (`step2_generate_worker_json.py`)

**目的**：将车辆段文件按 `region_id` 分组，生成符合算法输入的JSON格式。

**输入**：`step6_vehicle.csv`（由第一阶段生成）  
**输出**：`step6_worker_segments.json`

**JSON结构**：
```json
{
  "region_0": [
    {
      "vehicle_id": "v01_001",
      "start_time": 3600,
      "end_time": 5400,
      "cost": 12.5,
      "is_trusted": true
    },
    ...
  ],
  "region_1": [...]
}
```

**运行命令**：
```bash
python step2_generate_worker_json.py
```

**注意**：此脚本无配置参数，直接读取当前目录下的 `step6_vehicle.csv`。

---

### 5.3 第三阶段：生成任务 (`step3_generate_tasks.py`)

**目的**：基于工人的时空容量（每个区域每小时可用的不同车辆数）生成模拟任务，每个任务要求1个工人，持续1小时。

**核心算法**：

1. **读取车辆段文件**，构建容量字典：  
   `capacity[region][hour] = 该小时该区域内出现的不重复车辆数`
2. **生成候选时空单元列表**：`(region, hour, cap)`，权重 = 容量（高容量区域更易被选中）
3. **循环生成任务**直到达到目标数量或尝试次数上限：
   - 按容量加权随机选择一个时空单元 `(region, hour, cap)`
   - 检查该单元已生成任务数是否超过容量限制（每个任务至少需要1个工人，故最多 `cap` 个任务）
   - 随机生成任务起始秒：`[hour*3600, (hour+1)*3600 - 3600]` 区间内
   - 结束时间 = 起始时间 + 3600（固定1小时）
   - 生成任务ID：`t{region:02d}_{seq:02d}`
4. **输出**：
   - CSV：`task_id, region_id, start_time, end_time, required_workers`（`required_workers` 固定为1）
   - JSON：按 `region_id` 分组的任务列表
5. **可视化**：生成 `step6_tasks_distribution.png`
   - 背景热力图：工人活动密度（每个网格内的轨迹段数量）
   - 叠加紫色圆点：圆半径与任务数量成正比
   - 圆内白色数字：任务数量

**配置参数**（脚本开头可修改）：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VEHICLE_FILE` | `step6_vehicle.csv` | 车辆段文件路径 |
| `TASK_CSV` | `step6_tasks.csv` | 任务CSV输出路径 |
| `TASK_JSON` | `step6_task_segments.json` | 任务JSON输出路径 |
| `PLOT_FILE` | `step6_tasks_distribution.png` | 分布图输出路径 |
| `TOTAL_TASKS` | 500 | 目标任务总数（实际可能因容量不足而少于该值） |
| `random.seed` | 1 | 随机种子 |

**运行命令**：
```bash
python step3_generate_tasks.py
```

---

## 6. 一键运行

创建 `run_all.py`：

```python
import subprocess
import sys

scripts = [
    "step1_generate_segments.py",
    "step2_generate_worker_json.py",
    "step3_generate_tasks.py"
]

for script in scripts:
    print(f"\n=== Running {script} ===")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"Error in {script}, stopping.")
        break
print("\nAll steps completed.")
```

运行：
```bash
python run_all.py
```

---

## 7. 输出文件详解

| 文件 | 格式 | 内容说明 |
|------|------|----------|
| `step6_vehicle.csv` | CSV | 每个工人（车辆）的时空段。列：`vehicle_id`（如 `v01_001`），`region_id`（0-99），`start_time`（秒），`end_time`（秒），`cost`（浮点数），`is_trusted`（布尔值） |
| `step6_grid_partition.png` | PNG | 左右两个子图：左侧原始GPS点+网格线，右侧网格内点密度热力图 |
| `step6_worker_segments.json` | JSON | 按区域分组的工人段，与CSV内容相同但结构更利于算法读取 |
| `step6_tasks.csv` | CSV | 生成的任务列表。列：`task_id`，`region_id`，`start_time`，`end_time`，`required_workers`（固定1） |
| `step6_task_segments.json` | JSON | 按区域分组的任务列表 |
| `step6_tasks_distribution.png` | PNG | 工人密度热力图上叠加任务数量圆圈，直观展示任务分布 |

---

## 8. 常见问题与注意事项

### 8.1 原始数据路径问题
- 脚本中的输入路径默认为 `dataset/beijing_300_cars_2008-02-03.csv`，请根据实际位置修改 `INPUT_CSV` 变量，或将文件放置于正确路径。

### 8.2 列名不匹配
- 脚本会自动识别列名（不区分大小写），支持 `taxi_id`/`taxiid`/`id`，`time_sec`/`time`/`timestamp`，`lat`/`latitude`，`lon`/`longitude`。如果您的列名不同，可修改脚本中的识别逻辑。

### 8.3 任务数量不足
- 若 `TOTAL_TASKS` 超过工人容量（所有区域所有小时可用工人数之和），脚本会生成尽可能多的任务并打印警告。可降低 `TOTAL_TASKS` 或增加原始数据中的车辆数。

### 8.4 随机性可重复
- 所有脚本均设置了随机种子（`random.seed`），多次运行结果一致。

### 8.5 可视化中的网格编号
- 网格编号规则：`region_id = gy * GRID_X_NUM + gx`，其中 `gx` 从西向东递增，`gy` 从南向北递增。热力图的 `origin='lower'` 保证坐标轴方向与地图一致。

---

## 9. 扩展与定制

- **修改网格数**：调整 `GRID_X_NUM` 和 `GRID_Y_NUM`。
- **修改时间切分粒度**：在 `split_by_hour` 函数中将3600替换为其他秒数（如1800表示半小时）。
- **任务所需工人数随机化**：在 `step3_generate_tasks.py` 中将 `required = random.randint(1, 1)` 改为 `random.randint(1, max_req)`。
- **成本与可信度生成逻辑**：可在 `final_renumber_and_attributes` 函数中修改。

---

## 10. 联系与支持

如有问题，请检查：
- 原始数据是否包含所需列
- 所有依赖库是否已安装
- 输出目录是否有写入权限

本流程已在北京出租车数据集上验证通过。