好，我们进入下一步：

# `experiment2_step2_generate_tasks.md`

这一步的目标是：

> **根据 Step 1 生成的车辆轨迹段数据，构造平台发布的任务数据。**

而且这一步非常关键，因为它要把前面的“车”变成后面的“任务”，同时还要和你后续的：

* 工人可选项生成
* CMAB 招募
* 覆盖率
* 完成率
* 验证任务

全部对齐。

下面我直接给你一版完整、详细、可实现的文档。

---

# experiment2_step2_generate_tasks.md

## 1. 概述

本步骤的目标是根据 `experiment2_vehicle.csv` 中的车辆轨迹段数据，生成后续实验所需的**任务数据集**。

任务生成的基本思想不是“随机造任务”，而是：

> **根据车辆在不同时间片、不同网格中的活跃情况，生成可被这些车辆覆盖和执行的任务。**

因此，本步骤生成的任务应满足两个要求：

1. 任务分布要与车辆时空分布一致；
2. 任务应尽量具有可执行性，避免大量无人可做的无效任务。

---

## 2. 本步骤职责

### 2.1 本步骤负责

1. 读取 `experiment2_vehicle.csv`；
2. 统计每个 `(region_id, slot_id)` 下的工人容量；
3. 基于容量生成任务；
4. 为每个任务分配：

   * `task_id`
   * `region_id`
   * `start_time`
   * `end_time`
   * `slot_id`
   * `required_workers`
   * `weight`
5. 输出任务 CSV 文件；
6. 输出任务 JSON 文件；
7. 输出任务空间分布图。

### 2.2 本步骤不负责

* 不生成工人对任务的执行质量 (q_{ij})
* 不生成工人可选项
* 不判断任务是否完成
* 不生成验证任务
* 不进行任务招募

---

## 3. 输入数据

### 3.1 输入文件

`experiment2_vehicle.csv`

### 3.2 输入字段

| 字段                             | 含义                   |
| ------------------------------ | -------------------- |
| `vehicle_id`                   | 工人编号                 |
| `region_id`                    | 网格编号                 |
| `start_time`                   | 轨迹段开始时间              |
| `end_time`                     | 轨迹段结束时间              |
| `cost`                         | 工人成本                 |
| `init_category` / `is_trusted` | 初始可信属性（若 Step 1 里保留） |
| `base_quality`                 | 工人真实能力（若 Step 1 里保留） |

说明：

* 本步骤生成任务时，**只直接使用时空信息**：

  * `vehicle_id`
  * `region_id`
  * `start_time`
* `cost`、`base_quality` 暂时不在本步骤中使用，但会在后续步骤中使用。

---

## 4. 输出数据

### 4.1 输出文件

* `experiment2_tasks.csv`
* `experiment2_task_segments.json`
* `experiment2_tasks_distribution.png`

### 4.2 任务 CSV 字段

| 字段                   | 含义            |
| -------------------- | ------------- |
| `task_id`            | 任务编号          |
| `region_id`          | 任务所在网格        |
| `slot_id`            | 任务所属时间片       |
| `start_time`         | 任务开始时间        |
| `end_time`           | 任务结束时间        |
| `required_workers`   | 任务所需工人数       |
| `weight`             | 任务权重          |
| `candidate_capacity` | 该时空位置下的可用工人容量 |

### 4.3 JSON 结构

建议按 `region_id` 分组保存任务，便于后续按区域读取：

```json
{
  "region_0": [
    {
      "task_id": "t00_00",
      "slot_id": 15,
      "start_time": 9000,
      "end_time": 9599,
      "required_workers": 2,
      "weight": 2,
      "candidate_capacity": 3
    }
  ]
}
```

---

## 5. 核心设计思想

## 5.1 任务不是随机生成，而是由工人容量驱动

对每一个时间片 `slot_id` 和每一个网格 `region_id`，统计该位置的活跃工人数：

[
capacity_{g,s} = \text{在网格 } g \text{ 的时间片 } s \text{ 中出现的不同工人数}
]

这个容量表示：

> 在该时空位置上，平台最多有多少工人有机会执行任务。

因此，任务生成应遵循：

* 容量越大，越容易生成任务；
* 容量越大，同一位置可生成的任务数上限也越大。

---

## 5.2 任务的时空位置必须与轨迹段对齐

由于 Step 1 已经把轨迹段按固定时间片 `SLOT_SEC` 切分，因此本步骤中任务也必须和时间片对齐：

[
slot_id = \left\lfloor \frac{start_time}{SLOT_SEC} \right\rfloor
]

任务的时间窗口直接定义为该时间片对应的时间范围：

[
start_time = slot_id \times SLOT_SEC
]

[
end_time = (slot_id + 1)\times SLOT_SEC - 1
]

任务的空间位置则直接对应某个 `region_id`。

---

## 5.3 任务生成遵循“可执行优先”原则

任务生成不能脱离工人分布，否则会出现大量根本无人可做的任务，导致后续：

* 覆盖率失真
* 完成率过低
* 验证任务难以构造
* 预算被无效任务浪费

因此，本步骤只在以下位置生成任务：

> **仅在 `capacity_{g,s} > 0` 的 `(region, slot)` 位置生成任务**

---

## 6. 参数设置

| 参数                     |  默认值 | 含义          |
| ---------------------- | ---: | ----------- |
| `TOTAL_TASKS`          | 2000 | 总目标任务数      |
| `SLOT_SEC`             |  600 | 时间片长度       |
| `SLOTS_PER_DAY`        |  144 | 一天的时间片总数    |
| `MAX_REQUIRED_WORKERS` |    3 | 单个任务最大所需工人数 |
| `RANDOM_SEED`          |    1 | 随机种子        |

说明：

* 当可用容量不足时，实际生成任务数可能小于 `TOTAL_TASKS`；
* 任务数量最终由工人时空容量共同决定。你原来的代码也是这样处理的：当容量不够时，只能生成少于目标值的任务。

---

## 7. 处理流程

## 7.1 读取车辆轨迹数据

读取 `experiment2_vehicle.csv`，对每一条轨迹段记录：

* `vehicle_id`
* `region_id`
* `start_time`

根据 `start_time` 计算其所属时间片：

[
slot_id = \left\lfloor \frac{start_time}{SLOT_SEC} \right\rfloor
]

说明：

* 由于 Step 1 已经保证每个轨迹段不跨时间片，因此直接使用 `start_time` 对应的时间片即可。
* 你的原代码也是这么简化的。

---

## 7.2 统计时空容量

构造：

[
capacity[g][s] = {\text{在 }(g,s)\text{ 中活跃的不同车辆}}
]

然后得到：

[
capacity_count[g][s] = |capacity[g][s]|
]

该值表示：

> 在网格 (g)、时间片 (s) 中，平台有多少不同工人可供使用。

---

## 7.3 构造任务候选位置集合

遍历所有满足 `capacity_count[g][s] > 0` 的位置，形成候选集合：

[
CandidateSlots = {(g,s,capacity_{g,s})}
]

这些候选位置就是“有资格生成任务”的地方。

---

## 7.4 以容量为权重进行任务采样

为了让任务分布与工人分布一致，对每个候选位置赋予权重：

[
w_{g,s} = capacity_{g,s}
]

然后在生成任务时，以这些权重进行随机采样。
含义是：

> 工人越多的时空位置，越容易生成任务。

这和你原来的代码逻辑一致：`weights = [cap for ...]`。

---

## 7.5 控制同一位置的任务上限

对于每个 `(g,s)`，定义该位置最多生成的任务数为：

[
max_tasks_{g,s} = capacity_{g,s}
]

即：

> 某个位置最多生成的任务数不超过该位置的工人容量。

这条规则可以防止某些位置任务过多，导致后续任务大量不可完成。
你原代码里已经有这一思想：`max_tasks_in_slot = cap`。

---

## 7.6 生成任务的时间窗口

对于被抽中的 `(region, slot)`，任务时间窗口直接定义为该时间片：

[
start_time = slot \times SLOT_SEC
]

[
end_time = (slot + 1)\times SLOT_SEC - 1
]

说明：

* 不建议在当前版本中再对片内时间做随机微调；
* 直接与 slot 对齐最清晰，也更方便后续做工人与任务的重叠判断。

因此，这里建议比你原代码更简洁地固定为整个 slot 窗口，而不是随机片内起点。你原代码里这部分实际上也几乎等价于固定 slot 起点。

---

## 7.7 生成任务所需工人数

每个任务的 `required_workers` 表示任务至少需要多少个工人才能被视为有效完成。

为了兼顾可执行性与任务多样性，定义：

[
max_req = \min(3, capacity_{g,s})
]

然后从区间：

[
[1, max_req]
]

中随机采样一个整数作为 `required_workers`。

说明：

* 若容量只有 1，则该任务只能要求 1 个工人；
* 若容量较高，则可以生成更高需求的任务；
* 这样后续“完成率”和“覆盖率”才能真正区分开。

这里建议你不要再像旧代码那样固定为 1，否则任务完成会过于容易。你原代码当前是 `required = 1`，这个地方确实建议修改。

---

## 7.8 生成任务权重

任务权重 `weight` 用于表示任务的重要程度，后续可用于 CMAB 中的收益计算。

推荐使用以下简单规则：

[
weight = required_workers
]

原因：

1. 规则简单；
2. 与任务强度一致；
3. 后续更容易解释。

如果你后面希望更复杂，也可以改成与 `capacity` 相关，但当前版本先不复杂化。

---

## 7.9 生成任务编号

按区域单独计数，为每个任务生成：

[
task_id = t{region:02d}_{seq:02d}
]

例如：

* `t00_00`
* `t00_01`
* `t15_03`

这样做的好处是：

* 一眼能看出任务所在区域；
* 后续按区域查任务更方便；
* 与你原代码保持一致。

---

## 7.10 写入输出文件

### CSV

输出所有任务到 `experiment2_tasks.csv`

### JSON

按区域分组输出到 `experiment2_task_segments.json`

### 分布图

输出任务分布与工人活动热力图叠加图：

* 背景：工人轨迹段密度
* 圆点：任务数

你原代码已经做了这个可视化，建议保留。

---

## 8. 输出数据的性质

本步骤输出的任务具有以下特点：

1. 每个任务只属于一个 `region_id`；
2. 每个任务只属于一个 `slot_id`；
3. 每个任务的时间窗口和时间片严格对齐；
4. 任务分布与工人分布一致；
5. 同一位置的任务数量不会超过当地工人容量；
6. 后续可自然用于：

   * 覆盖率统计
   * 完成率判定
   * 验证任务选择

---

## 9. 为什么这样生成任务是合理的

这一步最重要的理论直觉是：

> 平台发布任务时，不应脱离工人的可达性与活跃性。

如果任务完全随机生成，则可能出现：

* 大量无人可达的任务
* 覆盖率极低
* 完成率无参考意义

而当前方法通过容量驱动任务生成，保证了：

* 任务具有现实可执行性；
* 任务空间分布与工人时空分布一致；
* 后续招募算法有优化空间，而不是被“无效任务”主导。

---

## 10. 与下一步的接口

下一步将基于：

* `experiment2_vehicle.csv`
* `experiment2_tasks.csv`

生成工人可选项（worker options）。

后续会使用：

### 来自车辆文件

* `vehicle_id`
* `region_id`
* `start_time`
* `end_time`
* `cost`
* `base_quality`

### 来自任务文件

* `task_id`
* `region_id`
* `slot_id`
* `start_time`
* `end_time`
* `required_workers`
* `weight`

下一步要做的事情就是：

> 判断每个工人能覆盖哪些任务，并为每个“工人-任务”对生成执行质量与任务数据。

---

## 11. 伪代码

```text
读取 experiment2_vehicle.csv

对每个轨迹段：
    计算 slot_id = start_time // SLOT_SEC
    统计 capacity[region_id][slot_id] 中的不同车辆数

构造所有 candidate (region, slot, capacity)

根据 capacity 作为权重，反复采样候选位置：
    若该位置生成任务数已达到 capacity 上限，则跳过
    否则生成一个任务：
        task_id
        region_id
        slot_id
        start_time = slot_id * SLOT_SEC
        end_time = (slot_id + 1) * SLOT_SEC - 1
        required_workers = random(1, min(3, capacity))
        weight = required_workers
        candidate_capacity = capacity

直到达到 TOTAL_TASKS 或候选容量耗尽

输出 CSV
输出 JSON
输出任务分布图
```

---

## 12. 当前版本建议修改点

基于你原来的代码，我建议你下一版做这几个修改：

### 修改 1

把 `required_workers` 从固定 1 改成：

```python
max_req = min(3, cap)
required = random.randint(1, max_req)
```

### 修改 2

把任务时间窗口改成直接对齐 slot：

```python
start_sec = slot_idx * SLOT_SEC
end_sec = (slot_idx + 1) * SLOT_SEC - 1
```

### 修改 3

在任务文件中增加两个字段：

* `slot_id`
* `weight`

---

## 13. 备注

这一步仍然只是“任务生成”，还没有进入“任务质量”层面。
也就是说：

* 本步骤决定任务在哪里、何时出现、需要多少工人；
* 下一步才会决定：

  * 哪些工人能做这些任务
  * 工人执行任务的质量是多少
  * 工人提交的数据是什么

所以，**任务生成先解决“有没有任务”和“任务能不能做”，下一步再解决“做得好不好”。**

---

如果你愿意，下一步我就接着帮你写：

# `experiment2_step3_generate_worker_options.md`

这一步会把：

* 车
* 任务
* base_quality
* 工人可执行任务
* 每个任务的执行质量 (q_{ij})

真正全部接起来。
