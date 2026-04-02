以下是为您提供的代码文档，完整解释了 `step6_generate_task_segments.py`（从车辆轨迹直接生成任务时空段 JSON）的每个部分。

---

# 任务时空段生成器（基于车辆密度） – 代码文档

## 概述

本脚本根据车辆轨迹文件 `step6_vehicle.csv` 中各区域的活动密度（轨迹段数量），按比例分配总任务数，为每个区域随机生成指定数量的感知任务。每个任务具有固定1小时的时间窗口、随机所需工人数，并分配唯一任务ID。最终输出按区域分组的 JSON 文件，供后续招募算法使用。

**特点**：任务分布与工人活动密度正相关（高密度区域获得更多任务），时间窗口均匀分布于全天，保证不跨午夜。

---

## 输入文件

| 文件名 | 必需字段 | 说明 |
|--------|----------|------|
| `step6_vehicle.csv` | `region_id`（整数） | 车辆轨迹段文件，脚本仅使用 `region_id` 列统计各区域出现次数作为密度。其他字段（`vehicle_id`, `start_time`, `end_time`, `cost`, `is_trusted`）不参与计算。 |

---

## 输出文件

| 文件名 | 格式 | 说明 |
|--------|------|------|
| `step6_task_segments.json` | JSON | 按区域分组的任务列表。结构示例见后。 |

### JSON 结构示例

```json
{
  "region_0": [
    {"task_id": "t00_00", "start_time": 12345, "end_time": 15945, "required_workers": 2},
    {"task_id": "t00_01", "start_time": 23456, "end_time": 27056, "required_workers": 1}
  ],
  "region_5": [
    {"task_id": "t05_00", "start_time": 5678, "end_time": 9278, "required_workers": 3}
  ]
}
```

- **键**：`"region_{region_id}"`，`region_id` 为 0~99 的整数。
- **值**：该区域的任务列表，每个任务包含：
  - `task_id`：字符串，格式 `t{region:02d}_{seq:02d}`，例如 `t00_00`。
  - `start_time`：整数，任务开始时间（秒），范围 0~82800。
  - `end_time`：整数，`start_time + 3600`，保证 ≤86400。
  - `required_workers`：整数，1~3 之间随机。

---

## 配置参数（可修改）

脚本顶部定义了以下常量：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VEHICLE_FILE` | `'step6_vehicle.csv'` | 输入车辆轨迹文件名 |
| `OUTPUT_JSON` | `'step6_task_segments.json'` | 输出 JSON 文件名 |
| `TOTAL_TASKS` | `200` | 需要生成的总任务数 |
| `TIME_MIN` | `0` | 任务起始时间最小值（秒），0 对应 00:00 |
| `TIME_MAX` | `82800` | 任务起始时间最大值（秒），82800 对应 23:00，保证 `end_time ≤ 86400` |
| `random.seed(42)` | 固定随机种子 | 保证每次运行结果可重复 |

---

## 核心逻辑详解

### 步骤1：统计区域活动密度

```python
region_density = defaultdict(int)
with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        region = int(row['region_id'])
        region_density[region] += 1
```

- 遍历 `step6_vehicle.csv` 每一行，累加每个 `region_id` 的出现次数。
- `region_density[r]` 表示区域 `r` 的车辆轨迹段数量（即工人活动强度）。
- 若文件为空或无有效区域，脚本报错退出。

### 步骤2：按密度分配任务数量

```python
total_density = sum(region_density.values())
tasks_per_region_float = {r: (d / total_density) * TOTAL_TASKS for r, d in region_density.items()}
tasks_per_region = {r: int(round(val)) for r, val in tasks_per_region_float.items()}
remainder = TOTAL_TASKS - sum(tasks_per_region.values())
```

- 计算各区域应得的任务数（浮点数，比例分配）。
- 四舍五入取整得到初步整数分配。
- 计算余数 `remainder`（可能正、负或零）。

**余数处理**：

```python
region_list = list(tasks_per_region.keys())
for _ in range(abs(remainder)):
    r = random.choice(region_list)
    tasks_per_region[r] += 1 if remainder > 0 else -1
```

- 若 `remainder > 0`，随机选择区域增加1个任务（补足不足）；若 `remainder < 0`，随机选择区域减少1个任务（抵消多余）。
- 最终 `sum(tasks_per_region.values()) == TOTAL_TASKS`。

### 步骤3：生成任务并分组

```python
tasks_by_region = defaultdict(list)
seq_counter = defaultdict(int)

for region, num_tasks in tasks_per_region.items():
    for _ in range(num_tasks):
        start = random.randint(TIME_MIN, TIME_MAX)
        end = start + 3600
        required = random.randint(1, 3)
        seq = seq_counter[region]
        task_id = f"t{region:02d}_{seq:02d}"
        tasks_by_region[region].append({
            'task_id': task_id,
            'start_time': start,
            'end_time': end,
            'required_workers': required
        })
        seq_counter[region] += 1
```

- 对每个区域，按分配数量生成任务。
- **时间窗口**：起始时间在 `[TIME_MIN, TIME_MAX]` 内均匀随机，结束时间 = 起始 + 3600 秒（1小时）。
- **所需工人数**：从 `{1,2,3}` 中等概率随机。
- **任务ID**：区域内部序号从0开始递增，格式 `t{region:02d}_{seq:02d}`（例如区域5的第一个任务为 `t05_00`）。
- 每个任务以字典形式存入 `tasks_by_region[region]` 列表。

### 步骤4：构建最终 JSON 结构

```python
result = {}
for region_id, tasks in tasks_by_region.items():
    result[f"region_{region_id}"] = tasks
```

- 将键名统一为 `"region_X"` 字符串。

### 步骤5：写入 JSON 文件

```python
with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
```

- `indent=2` 使输出可读。
- `ensure_ascii=False` 允许非 ASCII 字符（本例中无，但保留通用性）。

### 步骤6：输出统计信息

```python
print(f"已生成 {OUTPUT_JSON}，共 {sum(len(v) for v in tasks_by_region.values())} 个任务，涉及 {len(tasks_by_region)} 个区域。")
```

---

## 运行示例

```bash
python step6_generate_task_segments.py
```

控制台输出：
```
已生成 step6_task_segments.json，共 200 个任务，涉及 85 个区域。
```

---

## 注意事项

1. **网格假设**：脚本假设 `region_id` 范围为 0~99（10×10 网格），但实际不强制校验，仅作为整数处理。若 `region_id` 超出此范围，JSON 键仍为 `region_{id}`，不影响功能。
2. **无任务区域**：若某区域 `region_density[r] = 0`，则不会生成任何任务。
3. **时间边界**：`TIME_MAX = 82800` 对应 23:00，保证 `end_time = start + 3600 ≤ 86400`，不会跨午夜。
4. **随机性**：通过 `random.seed(42)` 保证每次运行结果一致。若要改变分布，可修改种子或 `TOTAL_TASKS`。
5. **与 CSV 生成脚本的关系**：本脚本独立生成 JSON，不依赖 `step6_generate_tasks.py`。两者任务分配逻辑相同，但输出格式不同。

---

## 扩展修改建议

- **改变时间窗口长度**：修改 `end = start + 3600` 中的 `3600`。
- **非均匀时间分布**：可替换 `random.randint` 为自定义概率分布（如高峰期权重更高）。
- **所需工人数分布**：修改 `random.randint(1,3)` 为加权随机。
- **增加任务属性**：在任务字典中添加字段（如 `priority`, `reward`），并在生成时赋值。

---

## 常见问题

**Q：为什么总任务数可能不等于 `TOTAL_TASKS`？**  
A：不会。通过余数分配步骤保证了精确等于 `TOTAL_TASKS`。

**Q：如果某个区域密度极大，分配的任务数会超过合理范围吗？**  
A：按比例分配，最大值受 `TOTAL_TASKS` 和总密度限制。例如总密度 1000，某区域密度 500，则分配约 `(500/1000)*200 = 100` 个任务，合理。

**Q：能否生成跨午夜的任务？**  
A：当前设计不允许。若需要跨午夜，可设置 `TIME_MAX = 86400`，并处理 `end_time` 可能超过 86400 的情况（例如取模或拆分任务）。

---

以上文档覆盖了脚本的全部功能、逻辑和配置。如有特定行需要进一步解释，请指出。