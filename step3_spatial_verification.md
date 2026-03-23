 
 
 # 总体思路
就是让可信工人先做任务记为task_done集合 然后记录下可信工人的轨迹（用grid来记录）。然后选出最多不可信工人经过的前M个grid。 然后也记录下来这些不可信工人做的任务数据 这样同时有可信工人数据和不可信工人的数据 再设定一个阈值 比较不同grid可信与不可信工人所做的任务数据  如果相差小就提高不可信工人的可信度 相差大就降低 （要设一个标准 可信度为多少叫可信 多少叫不可信 低于多少叫永远不可信）

参数设置： 可信阈值 不可信阈值 恶意工人阈值 验证轮数 可信与不可信工人数据相差阈值大小
第一轮 发布任务 
选了可信工人做任务 记录下grid 

第二轮 发布新的真任务加验证任务 
选出不可信工人经过最多的M个grid（根据不可信工人轨迹经过的数量来排序） 然后采集数据跟第一轮可信工人做的任务数据比较 同时也让上一轮可信工人集合做这些新任务（通过智能招募）也记录下grid（提供数据給下一轮验证）   更新可信工人集合 

第三轮
第四轮
......

---

# 信任度增强的未知工人招募算法设计文档

## 1. 概述
本算法在原有 UWR（Combinatorial Multi-Armed Bandit）招募算法的基础上，引入**空间一致性验证**机制。利用已知可信工人的数据作为基准，通过发布验证任务对比未知工人的上报数据，动态调整信任度，逐步识别并淘汰恶意工人，从而在有限预算下提高任务完成质量。

整个流程分为两个主要步骤：
- **第一步：初始化工人信任度与任务数据**
- **第二步：信任度验证与工人招募集成算法**

---

# 第一步：初始化工人信任度与任务数据

## 1.1 目标
- 为每个工人设置初始信任度与类别（可信/未知）。
- 为每个工人覆盖的任务随机生成模拟上报数据（用于后续验证）。
- 建立任务到网格的映射，为空间验证提供基础。

## 1.2 输入文件
- `step1_vehicles.csv`：工人轨迹，含 `vehicle_id`, `region_id`, `start_time`, `end_time`, `cost`, `is_trusted`
- `step1_tasks.csv`：任务信息，含 `task_id`, `region_id`, `start_time`, `end_time`, `required_workers`
- `step1_worker_segments.json`：按区域分组的工人轨迹（已存在，用于覆盖判断）
- `step1_task_segments.json`：按区域分组的任务窗口（已存在，用于生成网格映射）
- `step2_worker_option_set.json`：由之前算法生成的工人选项（含 `worker_id`, `total_cost`, `covered_tasks` 等）

## 1.3 输出文件
- `step3_worker_option_set.json`：在原有工人选项基础上增加 `trust`、`category`、`task_data` 字段。
- `step3_tasks_grid_num.json`：任务到网格的映射文件（当前网格 ID = region_id）。
- 保留原有 `step2_task_weight_list.json`（任务权重，不重新生成）。

## 1.4 处理步骤

### 1.4.1 读取数据
- 从 `step1_vehicles.csv` 读取每个工人的 `is_trusted` 字段，建立字典 `worker_is_trusted`。
- 从 `step2_worker_option_set.json` 读取工人选项列表，获取每个工人的 `worker_id`, `total_cost`, `covered_tasks`。
- 从 `step1_task_segments.json` 读取每个任务的 `region_id`，用于生成网格映射。

### 1.4.2 初始化信任度与类别
对每个工人：
- 若 `is_trusted == True`：
  - `trust = 1.0`
  - `category = "trusted"`
- 若 `is_trusted == False`：
  - `trust = 0.5`
  - `category = "unknown"`
- 恶意集合 `Um` 初始为空（后续验证中低于阈值时移入）。

### 1.4.3 添加任务数据
对每个工人的每个覆盖任务：
- 随机生成 `task_data`（均匀分布 `[0,1]`），模拟该工人对该任务的上报数据。
- 将该值添加到对应任务的字典中。

**为什么随机生成？**  
我们假设所有工人（无论可信与否）在初始阶段都没有被验证，因此数据随机生成，后续通过验证来区分好坏。

### 1.4.4 生成网格映射
- 遍历 `step1_task_segments.json` 中的所有任务，提取 `task_id` 和 `region_id`。
- 设置 `grid_id = region_id`（直接用区域 ID 作为网格 ID）。**注意**：这是简化版，后续可扩展为更细粒度网格。
- 输出为 JSON 列表。

### 1.4.5 保存文件
- 将更新后的工人选项保存为 `step3_worker_option_set.json`。
- 将网格映射保存为 `step3_tasks_grid_num.json`。
- 保持 `step2_task_weight_list.json` 不变（已存在，直接使用）。

## 1.5 输出文件样例

### 1.5.1 `step3_worker_option_set.json`
```json
{
  "worker_options": [
    {
      "worker_id": "v00_000",
      "total_cost": 37.5,
      "trust": 1.0,
      "category": "trusted",
      "covered_tasks": [
        {
          "task_id": "t00_00",
          "quality": 0.072,
          "task_price": 12.5,
          "task_data": 0.85
        },
        {
          "task_id": "t01_00",
          "quality": 0.112,
          "task_price": 12.5,
          "task_data": 0.92
        }
      ]
    },
    {
      "worker_id": "v00_001",
      "total_cost": 18.0,
      "trust": 0.5,
      "category": "unknown",
      "covered_tasks": [
        {
          "task_id": "t00_01",
          "quality": 0.089,
          "task_price": 18.0,
          "task_data": 0.24
        }
      ]
    }
  ]
}
```

### 1.5.2 `step3_tasks_grid_num.json`
```json
[
  {"task_id": "t00_00", "grid_id": 0},
  {"task_id": "t00_01", "grid_id": 0},
  {"task_id": "t01_00", "grid_id": 1},
  {"task_id": "t01_01", "grid_id": 1},
  ...
]
```

### 1.5.3 `step2_task_weight_list.json`（保持不变）
```json
{
  "task_weights": {
    "t00_00": 1,
    "t00_01": 2,
    "t01_00": 1,
    ...
  }
}
```

## 1.6 参数（供后续使用）
- 信任度更新步长 `η = 0.2`
- 可信阈值 `θ_high = 0.8`
- 恶意阈值 `θ_low = 0.2`
- 每轮验证任务数 `M = 3`

---

# 第二步：信任度验证与工人招募集成算法

## 2.1 目标
在每轮招募中：
- 利用已知可信工人的数据作为基准。
- 通过验证任务对比未知工人的上报数据，动态更新信任度。
- 逐步淘汰恶意工人，并基于 UCB 策略选择性价比最高的工人，最大化任务完成质量。

## 2.2 输入
- `step3_worker_option_set.json`：工人选项（含信任度、类别、任务数据）
- `step2_task_weight_list.json`：任务权重
- `step3_tasks_grid_num.json`：任务到网格的映射
- 参数：`B`（总预算）、`K`（每轮招募人数）、`MAX_ROUNDS`（最大轮数）、`M`（每轮验证任务数）、`η`、`θ_high`、`θ_low`

## 2.3 输出
- 控制台日志：每轮招募情况、信任度统计。
- JSON 文件：`step4_final_recruit_with_trust.json`（最终招募结果，含信任度统计）

## 2.4 数据结构
- **工人档案**（来自 `step3_worker_option_set.json`）：
  - `worker_id`, `total_cost`, `trust`, `category`, `covered_tasks`（含 `task_data`, `quality`, `task_price`）
  - UWR 相关：`n_i`（学习次数），`avg_quality`（平均感知质量）
- **任务状态**：
  - `task_covered_count`：每个任务已被多少个工人覆盖（初始为0）
  - `required_workers`：每个任务需要的工人数（从任务权重获取）
- **工人分类集合**：
  - `Uc`：可信工人
  - `Uu`：未知工人
  - `Um`：恶意工人（不再招募）

## 2.5 算法流程

### 2.5.1 初始化阶段（t=0）
1. 从 `step3_worker_option_set.json` 加载工人，根据 `trust` 和 `category` 初始化 `Uc`、`Uu`、`Um`。
2. **招募所有工人**（探索阶段）：
   - 支付每个工人的 `total_cost`，更新总成本 `total_cost` 和剩余预算 `remaining_budget`。
   - 初始化 UWR 档案：`n_i = len(covered_tasks)`，`avg_quality = 平均质量`（由第一步计算）。
   - 记录所有工人到 `all_selected_workers`。
3. **不更新任务覆盖**（探索阶段仅学习质量）。

### 2.5.2 贪心轮次（t = 1 至 MAX_ROUNDS）

#### 2.5.2.1 终止条件检查
- 若 `remaining_budget < min(worker.total_cost)`，终止。
- 若所有业务任务已完成（`task_covered_count[tid] >= required_workers[tid]` 对所有任务成立），终止。

#### 2.5.2.2 生成验证任务（仅当 t ≥ 2 且 Uc 非空）
- **网格统计**：  
  对每个工人，根据其覆盖的任务（每个任务对应一个网格），统计每个网格中 `Uc` 工人出现次数和 `Uu` 工人出现次数。  
  （一个工人可能覆盖多个任务，因此可能被统计多次）
- 筛选出 `Uc` 出现次数 > 0 的网格（即有可信工人经过的网格）。
- 按 `Uu` 出现次数降序排列，取前 `M` 个网格。
- 对每个选中网格，从该网格的任务列表中**随机选取一个任务**作为验证任务。
- 生成验证任务列表 `validation_tasks`。

**为什么这样选？**  
- 选取 `Uu` 出现最多的网格，是因为这些网格有大量未知工人经过，验证他们能高效识别可信/恶意工人。
- 必须有 `Uc` 工人经过，才能提供基准数据。
- 每个网格只选一个任务，控制验证成本。

**执行范围**：验证任务将与业务任务一同发布，**所有覆盖该任务的工人（包括之前轮次招募的工人）都会执行**，并上报数据。这是因为平台已雇佣这些工人，可要求他们执行额外的验证任务。因此，每轮可能有大量工人参与验证，信任度更新可同时影响许多工人，可信工人数的单轮增长可能超过 K。这种设计能快速识别可信工人，但也会增加成本，因为每个执行验证任务的工人都需支付报酬（成本已包含在工人的 `total_cost` 中）。

#### 2.5.2.3 发布任务
- 业务任务：所有原始任务（权重为 `required_workers`）。
- 验证任务：`validation_tasks`（权重设为 0，不参与业务增益计算，但工人执行会消耗成本）。

#### 2.5.2.4 招募工人
- 候选工人 = `Uc ∪ Uu`（排除 `Um`）。
- 使用 UWR 贪心策略，每轮选择 `K` 个工人：
  1. 对每个候选工人，计算 UCB 质量：
     ```
     ucb_q = avg_quality + sqrt((K+1) * ln(total_learned_counts) / n_i)
     ```
  2. 计算边际增益：
     ```
     gain = sum_{task in covered_tasks} required_workers[task] * ucb_q
     ```
     其中仅考虑未完成的任务（`task_covered_count[tid] < required_workers[tid]`）。
  3. 性价比 = `gain / total_cost`。
  4. 选择性价比最高的工人。
- 支付成本，更新 `total_cost` 和 `remaining_budget`。
- 更新任务覆盖计数：对选中的工人，将其覆盖的任务的计数加1（但不超过 `required_workers`）。
- 更新工人档案：
  - `n_i += len(covered_tasks)`
  - 观测质量 = 工人当前 `avg_quality`（模拟）。
  - 更新 `avg_quality = (旧总和 + 观测质量 * 新增学习次数) / 新 n_i`
  - `total_learned_counts += len(covered_tasks)`

#### 2.5.2.5 信任度更新（基于验证任务）
- 对于每个验证任务 `v`：
  1. 收集所有完成该任务的 `Uc` 工人的上报数据（`task_data`），取中位数作为基准 `base`。
  2. 对于每个完成该任务的 `Uu` 工人 `i`（**包括本轮及之前招募的工人**），获取其上报数据 `data`：
     - 获取其上报数据 `data`。
     - 计算误差：
       ```
       if base != 0:
           error = |data - base| / base
       else:
           error = |data - base|
       ```
     - 更新信任度：
       ```
       trust_i = trust_i + η * (1 - 2 * error)
       trust_i = max(0, min(1, trust_i))
       ```
     - 若 `trust_i >= θ_high`，将工人从 `Uu` 移入 `Uc`，更新 `category`。
     - 若 `trust_i <= θ_low`，将工人从 `Uu` 移入 `Um`，更新 `category`。
     - 由于验证任务由所有覆盖它的工人执行，因此每轮可能有大量工人更新信任度，这是算法高效识别可信工人的关键。

**公式解释**：
- 当 `error` 较小时（数据接近基准），`1 - 2*error` 为正，信任度增加；当 `error` 较大时（数据偏离基准），信任度减少。
- 更新步长 `η` 控制调整速度。

#### 2.5.2.6 输出本轮统计
- 打印：轮次、选择工人数、当前总成本、剩余预算、已完成任务数、`|Uc|`、`|Uu|`、`|Um|`。

#### 2.5.2.7 循环继续

### 2.5.3 最终输出
返回结果字典，包含：
- `total_rounds`：实际贪心轮数（不含初始化）
- `total_cost`：总花费
- `remaining_budget`：剩余预算
- `selected_workers`：贪心阶段招募的工人 ID 列表
- `init_select`：初始轮招募工人数
- `later_select`：贪心阶段招募工人数
- `covered_task_count`：已完成业务任务数
- `trusted_count`：最终可信工人数
- `malicious_count`：最终恶意工人数
- `unknown_count`：最终未知工人数
- `trusted_workers_list`：最终可信工人 ID 列表（便于查看）

保存为 `step4_final_recruit_with_trust.json`。

## 2.6 输出文件样例（`step4_final_recruit_with_trust.json`）
```json
{
  "total_rounds": 5,
  "total_cost": 19850.0,
  "remaining_budget": 150.0,
  "selected_workers": ["v00_000", "v00_001", "v00_005"],
  "init_select": 900,
  "later_select": 15,
  "covered_task_count": 38,
  "trusted_count": 120,
  "malicious_count": 5,
  "unknown_count": 775,
  "trusted_workers_list": ["v00_000", "v00_002", "v00_005", ...]
}
```

## 2.7 参数汇总
| 参数 | 含义 | 推荐值 |
|------|------|--------|
| `B` | 总预算 | 根据数据规模设定 |
| `K` | 每轮招募工人数 | 3 |
| `MAX_ROUNDS` | 最大贪心轮数 | 10 |
| `M` | 每轮验证任务数 | 3 |
| `η` | 信任度更新步长 | 0.2 |
| `θ_high` | 可信阈值 | 0.8 |
| `θ_low` | 恶意阈值 | 0.2 |

## 2.8 注意事项
- 第一轮（t=0）为初始化，不发布验证任务。
- 验证任务仅在 `Uc` 非空时生成，否则跳过信任度更新。
- 恶意工人（`Um`）在后续轮次中不会被招募。
- 所有工人的任务数据已在第一步随机生成，验证时直接使用，无需重新模拟。
- 任务覆盖计数严格按 `required_workers` 累积，只有达到所需工人数才算完成。
- **验证任务的成本**已包含在工人的 `total_cost` 中，因为工人每覆盖一个任务（无论业务还是验证）都会按报价收费。
- 验证任务由所有覆盖该任务的工人执行，因此每轮信任度更新可能涉及大量工人，导致成本上升，但能更快扩充可信工人集合。如需控制成本，可调整参数 `M` 减少验证任务数量，或修改代码限制只有本轮招募工人执行验证任务。
- 工人离开的处理：工人的可用性由其轨迹段与任务时间窗口的交集决定。如果一个工人已经离开（其轨迹段结束时间早于验证任务开始时间），则他不会覆盖该验证任务，因此不会执行验证任务，也不会被纳入信任度更新。因此，算法天然避免了工人离开后仍被要求执行任务的情况。
---

## 3. 算法流程图（文字描述）

```
[开始] → 加载数据（step3_worker_option_set, task_weights, grid_map）
       ↓
[初始化阶段] 招募所有工人，学习质量，记录 n_i, avg_quality
       ↓
[进入贪心轮次] 循环直到终止条件
       ↓
   ┌── 检查预算和任务完成度，满足则终止
   ↓
   ┌── 生成验证任务（若 t≥2 且 Uc 非空）
   │     - 统计网格中 Uc/Uu 出现次数
   │     - 取 Uu 最多的前 M 个网格
   │     - 每个网格随机选一个任务作为验证任务
   ↓
   ┌── 招募 K 个工人（从 Uc∪Uu 中选）
   │     - 计算每个工人的 UCB 质量
   │     - 计算边际增益（仅考虑未完成业务任务）
   │     - 性价比 = 增益 / 成本
   │     - 选择性价比最高的工人
   ↓
   ┌── 执行任务
   │     - 更新业务任务覆盖计数
   │     - 更新工人档案（n_i, avg_quality）
   ↓
   ┌── 信任度更新（基于验证任务）
   │     - 对每个验证任务，取 Uc 数据中位数作为基准
   │     - 对每个完成该任务的 Uu 工人，计算误差，更新 trust
   │     - 若 trust ≥ θ_high，移入 Uc；若 ≤ θ_low，移入 Um
   ↓
   ┌── 输出本轮统计
   ↓
[循环结束] → 输出最终结果 JSON
```

---

## 4. 总结
本设计将 UWR 招募算法与空间一致性验证深度融合，通过动态信任度管理，逐步提升工人集合的可信度，同时保持原有招募策略的优化性。两步流程清晰，模块独立，便于实现与调试。


## 5. 后期优化 本模型是时间静态简化版 后期可以增加时间动态问题 使每一轮招募跟任务开始时间对其  这里只是模拟



