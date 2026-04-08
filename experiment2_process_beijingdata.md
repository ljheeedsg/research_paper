# 北京出租车轨迹数据处理完整文档（10分钟切片版）

## 1. 概述

本项目处理北京市300辆出租车在2008年2月3日的GPS轨迹数据，通过网格化、时空分段（10分钟粒度）、工人属性生成、任务生成等步骤，为众包任务分配算法提供输入。整个流程分为三个主要阶段：

1. **轨迹预处理**（`1beijing.py`）：从原始GPS点生成车辆时空段，按10分钟切片，车辆ID纯数字编号，并赋予成本(`cost`)和可信度(`is_trusted`)。
2. **工人数据导出**（`2beijing.py`）：将车辆段文件按区域分组，输出JSON格式，供算法读取。
3. **任务生成**（`3beijing.py`）：基于工人的时空容量（每个10分钟时段每个区域可用工人数）生成模拟任务，输出CSV、JSON及分布图。

---

## 2. 环境依赖

- Python 3.7+
- 依赖库：
  - `numpy`
  - `matplotlib`
  - `csv`（内置）
  - `json`（内置）
  - `collections`（内置）
  - `random`（内置）

安装命令：
```bash
pip install numpy matplotlib
```

---

## 3. 数据准备

### 输入文件：`beijing_300_cars_2008-02-03.csv`

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

## 4. 北京出租车数据处理流程

### 4.1 步骤1：轨迹分段（`1beijing.py`）

**目的**：将原始GPS点转换为连续的时间段，每个时间段对应车辆停留在某个网格内，按10分钟切片，车辆ID重编号为纯数字（1,2,3,…），并随机生成成本和可信度。

**核心算法**：

1. **读取数据**：自动识别列名，提取车辆ID、时间、经纬度。
2. **确定研究区域**：
   - 计算所有点的1%和99%分位数作为初始矩形
   - 将矩形中心偏移 `SHIFT_LON`, `SHIFT_LAT`（默认-0.08°, -0.08°）
3. **网格划分**：将矩形划分为 `GRID_X_NUM × GRID_Y_NUM`（默认10×10）个网格，每个网格分配唯一 `region_id`（0~99）。
4. **为每个点分配 region_id**：基于经纬度落在的网格。
5. **构建原始轨迹段**：按车辆分组，按时间排序，相邻两点之间生成一个段 `(region_id, start_time, end_time)`。
   - `start_time` 为前一个点的时间（第一个点）或前一段结束时间+1
   - `end_time` 为后一个点的时间
6. **合并同区域连续段**：如果同一车辆连续多个段都在同一网格内，则合并为一个更长的时间段。
7. **按10分钟切片**：`split_by_slot()` 函数确保每个段不跨10分钟边界（切片长度 `SLOT_SEC = 600` 秒）。
8. **车辆ID重编号**：
   - 仅保留有轨迹段的车辆
   - 按原始ID数值升序映射为 `1, 2, 3, ...`（纯数字，无前缀）
9. **生成随机属性**：
   - `cost`：均匀分布 `[COST_MIN, COST_MAX]`（默认5~20）
   - `is_trusted`：以 `TRUSTED_RATIO`（默认0.5）概率为True
10. **输出CSV**：列包括 `vehicle_id`, `region_id`, `start_time`, `end_time`, `cost`, `is_trusted`。

**可视化输出**：`grid_plot.png`  
- 左子图：矩形内的所有GPS点 + 网格线
- 右子图：每个网格内的点数量热力图

**配置参数**（脚本开头可修改）：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_CSV` | `beijing_300_cars_2008-02-03.csv` | 输入文件路径 |
| `OUTPUT_SEG` | `beijing_300_cars_segments_final.csv` | 输出CSV路径 |
| `OUTPUT_PLOT` | `grid_plot.png` | 输出图片路径 |
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
| `SLOT_SEC` | 600 | 时间切片长度（秒），10分钟 |
| `random.seed` | 42 | 随机种子 |

---

### 4.2 步骤2：生成工人JSON（`2beijing.py`）

**目的**：将车辆段文件按 `region_id` 分组，生成符合算法输入的JSON格式。

**输入**：`beijing_300_cars_segments_final.csv`（由步骤1生成）  
**输出**：`step6_worker_segments.json`

**JSON结构**：
```json
{
  "region_0": [
    {
      "vehicle_id": "1",
      "start_time": 3600,
      "end_time": 4200,
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
python 2beijing.py
```

**注意**：此脚本无配置参数，直接读取当前目录下的 `beijing_300_cars_segments_final.csv`。

---

### 4.3 步骤3：生成任务（`3beijing.py`）

**目的**：基于工人的时空容量（每个10分钟时段每个区域可用的不同车辆数）生成模拟任务，每个任务要求1个工人，持续10分钟。

**核心算法**：

1. **读取车辆段文件**，构建容量字典：  
   `capacity[region][slot] = 该10分钟时段该区域内出现的不重复车辆数`  
   （`slot` 索引：0~143，对应一天144个10分钟片）
2. **生成候选时空单元列表**：`(region, slot, cap)`，权重 = 容量（高容量区域更易被选中）
3. **循环生成任务**直到达到目标数量或尝试次数上限：
   - 按容量加权随机选择一个时空单元 `(region, slot, cap)`
   - 检查该单元已生成任务数是否超过容量限制（每个任务至少需要1个工人，故最多 `cap` 个任务）
   - 随机生成任务起始秒：`[slot*SLOT_SEC, (slot+1)*SLOT_SEC - SLOT_SEC]` 区间内
   - 结束时间 = 起始时间 + `SLOT_SEC`（固定10分钟）
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
| `VEHICLE_FILE` | `beijing_300_cars_segments_final.csv` | 车辆段文件路径 |
| `TASK_CSV` | `step6_tasks.csv` | 任务CSV输出路径 |
| `TASK_JSON` | `step6_task_segments.json` | 任务JSON输出路径 |
| `PLOT_FILE` | `step6_tasks_distribution.png` | 分布图输出路径 |
| `TOTAL_TASKS` | 500 | 目标任务总数（实际可能因容量不足而少于该值） |
| `SLOT_SEC` | 600 | 任务时长（秒），10分钟 |
| `random.seed` | 1 | 随机种子 |

**运行命令**：
```bash
python 3beijing.py
```

---

## 5. 输出文件说明

| 文件 | 格式 | 内容说明 |
|------|------|----------|
| `beijing_300_cars_segments_final.csv` | CSV | 每个工人（车辆）的时空段。列：`vehicle_id`（纯数字1,2,3…），`region_id`（0-99），`start_time`（秒），`end_time`（秒），`cost`（浮点数），`is_trusted`（布尔值） |
| `grid_plot.png` | PNG | 左右两个子图：左侧原始GPS点+网格线，右侧网格内点密度热力图 |
| `step6_worker_segments.json` | JSON | 按区域分组的工人段，与CSV内容相同但结构更利于算法读取 |
| `step6_tasks.csv` | CSV | 生成的任务列表。列：`task_id`，`region_id`，`start_time`，`end_time`，`required_workers`（固定1） |
| `step6_task_segments.json` | JSON | 按区域分组的任务列表 |
| `step6_tasks_distribution.png` | PNG | 工人密度热力图上叠加任务数量圆圈，直观展示任务分布 |

---

## 6. 一键运行（可选）

创建 `run_all_beijing.py`：

```python
import subprocess
import sys

scripts = ["1beijing.py", "2beijing.py", "3beijing.py"]
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
python run_all_beijing.py
```

---

## 7. 附加：芝加哥共享单车数据处理（提取2020-04-01数据）

若需要处理芝加哥共享单车数据（`Chicago.xlsx`），可使用以下脚本提取2020-04-01的记录，并将 `ride_id` 替换为纯数字ID（从1开始），输出CSV。

```python
import pandas as pd

df = pd.read_excel('Chicago.xlsx')
df['started_at'] = pd.to_datetime(df['started_at'])
df_apr1 = df[df['started_at'].dt.date == pd.to_datetime('2020-04-01').date()]

# 检查重复ride_id
unique_ride_ids = df_apr1['ride_id'].unique()
unique_count = len(unique_ride_ids)
total_rows = len(df_apr1)
print(f"总记录数: {total_rows}")
print(f"唯一车辆数: {unique_count}")
if df_apr1['ride_id'].duplicated().any():
    print("警告: ride_id 存在重复！")

# 映射为纯数字ID
id_mapping = {orig: i+1 for i, orig in enumerate(sorted(unique_ride_ids))}
df_apr1['ride_id'] = df_apr1['ride_id'].map(id_mapping)

# 按新ID排序
df_apr1 = df_apr1.sort_values('ride_id')

# 选择所需列
selected_columns = ['ride_id', 'started_at', 'ended_at', 'start_lat', 'start_lng', 'end_lat', 'end_lng']
df_output = df_apr1[selected_columns]

output_file = 'Chicago_2020-04-01.csv'
df_output.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"已保存 {len(df_output)} 条记录到 {output_file}")
```

**依赖**：`pandas`, `openpyxl`  
**运行**：`python extract_chicago.py`

---

## 8. 注意事项

1. **时间切片粒度**：所有时间相关操作（轨迹段切片、任务时段）均基于10分钟（600秒）。一天共有144个时段，索引0~143。
2. **车辆ID格式**：步骤1输出中 `vehicle_id` 为纯数字（如 `1`, `2`, `3`），不再包含小时信息。
3. **容量限制**：任务生成时每个10分钟时段最多生成 `cap` 个任务（`cap` 为该时段该区域的不重复工人数）。若 `TOTAL_TASKS` 超过总容量，脚本会生成尽可能多的任务并打印警告。
4. **随机性可重复**：所有脚本均设置了随机种子（`random.seed`），多次运行结果一致。
5. **数据范围**：研究区域基于1%和99%分位数裁剪并偏移，确保覆盖大部分点且避开边缘异常点。
6. **性能**：10分钟切片会导致轨迹段数量增加，但仍在可接受范围（原1小时切片约产生数千段，10分钟切片可能增加数倍）。

---

## 9. 常见问题

**Q1: 输入CSV列名不匹配怎么办？**  
脚本自动识别常见列名（不区分大小写），若仍失败，可手动修改 `read_input_data()` 中的列名字典。

**Q2: 任务生成数量不足500怎么办？**  
降低 `TOTAL_TASKS` 或增加原始数据中的车辆数/轨迹点密度。

**Q3: 如何修改网格数量？**  
修改 `GRID_X_NUM` 和 `GRID_Y_NUM` 即可，但需注意 `region_id` 范围为 `0` 到 `GRID_X_NUM*GRID_Y_NUM-1`。

**Q4: 任务时长可以改为其他值吗？**  
修改 `3beijing.py` 中的 `SLOT_SEC` 变量，但需确保与轨迹段切片粒度一致（建议保持一致）。

**Q5: 生成的JSON文件用于什么？**  
供后续任务分配算法读取，例如基于二分图匹配的工人-任务分配。

---

## 10. 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2025-04 | 初始版本，1小时切片，车辆ID带小时前缀 |
| 2.0 | 2025-04 | 改为10分钟切片，车辆ID纯数字，任务时长10分钟 |

---

**文档结束**