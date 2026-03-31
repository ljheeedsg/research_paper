总体算法流程：

数据准备：

任务集合 
工人集合 
可选项集合（任务id 价格 信任度 任务数据 每个任务质量 任务开始和结束时间 ） 
权重集合 
总预算 
每轮招募人数  
任务的权重列表
任务的网格列表
高利润任务比例（感觉也可以放在数据准备阶段）
生成激励专用任务数据（任务报价 任务成本 系统收入 工人净收入 任务类型（会员或者普通））

初始化阶段：
招募所有工人得到所有任务数和全部质量 求平均得到初始平均质量
初始化任务覆盖（不覆盖任务后续才算）
工人分类集合 `Uc`, `Uu`, `Um`
PGRD 所需的历史报酬和平均报酬（第一轮历史报酬为0 只算平均报酬 用所有会员任务和普通任务的平均收益指代初始）
被选中的任务集合（一开始为空）

贪心招募阶段：
循环：
    先置可选项集合为空
    确定这一轮可用工人和任务
    生成验证任务
    发布任务
    循环选出哪些工人成为会员哪些为普通（一次遍历一个）（注意只有可信工人能够成为会员）
        
        算出这一轮该工人的预估收益（包括做会员任务收益或者做普通任务收益）（会员收益一定大于普通任务收益）

        算出参照损失
        进而算出成为会员概率

        如果这个概率大于阈值 那么本轮可以成为会员 优先选择自己的会员任务 并且交会费（会费需要累加）

        如果不大于 那么只能当普通人 选择普通任务 无法做会员任务（可能降低覆盖）



    每一轮招募k个工人（循环）
        取最大性价比工人
        加入可选项集合 记下完成的任务数

    如果超过预算 则退出循环 输出剩余钱 还有轮数
    获得本轮完成的质量 本轮完成的任务列表 用于下一轮质量估计   
    更新工人档案：被学习次数 平均质量 估计平均质量
    输出这一轮花的钱 以及剩余的钱
    根据本轮收到的数据更新信任度（更新集合Uc Uu Um）
    得到每个用户这一轮完成任务获得的实际报酬
    系统获得的真实收益
    收获的总会费值
   
    更新这一轮会员收益和和普通收益（通过任务记录可以得到 就是每个会员本轮做的全部任务收益（如果既有会员任务和普通任务加在一起） 和普通工人本轮做的任务收益（只有普通任务））注意这里所有的收益都是指系统给工人的钱 就是报价）
   
    更新上一轮所有会员任务和普通任务的平均收益（会员任务平均收益等于上一轮所有被做了的会员任务除以总会员人数， 普通任务平均收益等于上一轮做过的普通任务总收益除以普通任务总人数）（注意这里所有的收益都是指系统给工人的钱 就是报价）
    （以上两个数据用来预测下一轮的预估收益）

    下面是LGSC:
    输入为：
    选中的任务集合（刚刚才得到的本轮哪个工人完成的哪个任务） 
    用户参与各个任务的成本 （从生成激励专用任务数据获取）
    沉没阈值
    每个用户的沉没累积率
    循环遍历所有的会员：
        如果是新会员那么初始化沉没累计率为1 沉没值为0
        
    然后循环遍历所有本轮的工人（分配报酬）：
        当该工人所做任务不为空时，也就是本轮做了任务：
            如果他是会员且会员没到期    
                那么根据公式4-1计算沉没值（本轮做的任务成本×沉没累累积率）

                还有计算这个会员的预期报酬（本轮所作任务的固定收益加已累计沉没值的折现值）

                如果 本轮沉没值大于等于沉没阈值：
                    那么本轮得到的报酬就为固定报酬加奖励金
                    更新沉没累计率

                否则（本轮沉没值小于沉没阈值）：
                    报酬为所做任务的固定报酬
                    但是计算沉没累积的折现值（如果不做就会损失这一部分）

                计算该用户投资回报率

            如果不是会员或者其他情况（比如会员到期）
                该员工则只能收入完成任务的固定收入（这里的收入都是指报价不是净收入）


注意 这里先考虑会员集合就是一旦成为了会员 那么一直是会员 当天就不用再交会费也能做会员任务了


但是我有问题 怎么定义会员留存率 
预计会员留存率大于普通工人 

引入激励不影响任务覆盖

长期会员工人收入高

输出：
平台效用：
会员人数：
用户效用：（会员收益和普通会员收益（可以生成两个两个json文件分别记录每个人））
任务覆盖率

# 群智感知双阶段工人招募与信任度验证算法（含 PGRD 会员激励 + LGSC 长期留存）

## 概述

本算法在空间一致性验证和 CMAB 招募的基础上，引入行为经济学中的**参照依赖（PGRD）**和**沉没成本效应（LGSC）**，构建完整的长期激励框架。算法分为三个阶段：

- **第一阶段：数据准备** – 生成工人可选项、任务权重、任务网格映射，并**重新生成任务分类（会员/普通）**，为每个任务赋予报酬、成本、系统收益，为 PGRD 提供基础。同时配置 LGSC 参数。
- **第二阶段：初始化（学习阶段）** – 建立工人的初始 CMAB 质量档案，初始化任务覆盖状态、工人分类集合，并初始化 PGRD 所需的历史报酬和平均报酬，以及 LGSC 所需的沉没值、累计率等状态。
- **第三阶段：贪心轮次（多轮迭代）** – 按小时轮次（0~23）进行招募，每轮先执行 **PGRD 会员决策**（决定工人成为会员的概率及投标任务类型），再生成验证任务，然后进行 **CMAB 招募**，最后更新信任度和历史报酬，并在每轮结束后执行 **LGSC 报酬支付**（沉没值累积、奖励金发放）。

**核心思想**：通过空间一致性验证快速识别可信工人，利用参照依赖（PGRD）激励可信工人成为会员，提升平台效用；利用沉没成本效应（LGSC）为会员工人设计“越投入越难退出”的长期激励，提高用户留存率。验证任务只从有可信工人经过的网格中选取，确保基准可靠且成本可控。验证任务由所有覆盖该任务的工人执行，实现批量验证。

---

# 第一阶段：数据准备

## 1.1 目标
- 根据原始轨迹和任务数据，为每个工人生成可覆盖的任务列表（含质量、报酬、时间交集）。
- **将同一实体车在不同小时的轨迹段合并为一个工人**，工人 ID 使用纯数字序号（如 `"000"`）。
- 为每个工人设置初始信任度与类别（可信/未知）。
- 为每个工人覆盖的任务随机生成模拟上报数据（`task_data`），用于后续信任验证。
- 建立任务到网格的映射，为空间验证提供基础。
- **重新生成任务分类（PGRD 专用）**：为每个任务生成报酬、成本、系统收益，并划分会员/普通任务。
- 配置 LGSC 沉没成本激励参数（沉没阈值、会员奖励金、初始累计率）。

## 1.2 输入
- `step6_worker_segments.json`：按区域分组的工人轨迹段，每个段包含：
  - `vehicle_id`：格式 `v{hour}_{idx}`（如 `v00_000`）
  - `region_id`：区域 ID（0~99）
  - `start_time`：段开始时间（绝对秒数，0~86400）
  - `end_time`：段结束时间（绝对秒数，0~86400）
  - `cost`：工人固定报价（浮点数）
  - `is_trusted`：可信标记（布尔值，70% True、30% False）
- `step6_task_segments.json`：按区域分组的任务窗口，每个任务包含：
  - `task_id`：任务 ID（如 `t00_00`）
  - `region_id`：区域 ID（0~99）
  - `start_time`：任务开始时间（绝对秒数，0~86400）
  - `end_time`：任务结束时间（绝对秒数，`start_time + 3600`）
  - `required_workers`：所需工人数（1~3）

## 1.3 处理步骤

### 1.3.1 解析数据
- **解析工人**：提取 `vehicle_id` 中的序号（下划线后的部分），将同一序号的所有段合并为一个工人。每个工人的属性（`is_trusted`、`cost`）从任意一段中取（假设同一实体车所有段一致）。
- **解析任务**：将所有任务平铺为一个列表，每个任务包含 `task_id`、`region_id`、`start_time`、`end_time`、`required_workers`。

### 1.3.2 计算工人可选项
对每个实体车工人：
- 初始化空列表 `covered_tasks`。
- 遍历所有任务，判断工人是否能覆盖该任务：
  - **覆盖条件**：工人有至少一个段与任务区域相同，且时间窗口有交集（即 `seg.start_time < task.end_time` 且 `seg.end_time > task.start_time`）。
- 若满足条件：
  - 计算交集起止时间（用于记录实际可执行窗口）：
    $$ start = \max(\text{seg.start\_time}, \text{task.start\_time}) $$
    $$ end = \min(\text{seg.end\_time}, \text{task.end\_time}) $$
  - **质量**：在 `[0,1]` 内均匀随机生成（不依赖工人可信度）。
  - **报酬**：`task_price = worker.cost`（工人的固定报价）。
  - **任务数据**：随机生成 `task_data ∈ [0,1]`，模拟工人上报数据（用于信任验证）。
  - 将任务信息（`task_id`, `quality`, `task_price`, `start_time`, `end_time`, `task_start_time`, `task_data`）加入 `covered_tasks`，其中 `task_start_time` 记录任务的原始开始时间（用于后续轮次筛选）。
- **注意**：即使工人没有任何覆盖任务，也需记录该工人（`covered_tasks` 为空列表），以便算法统计所有工人。

- 计算工人总成本：`total_cost = len(covered_tasks) × worker.cost`。
- 根据工人的 `is_trusted` 初始化信任度与类别：
  - 若 `is_trusted == True`：`trust = 1.0`，`category = "trusted"`。
  - 若 `is_trusted == False`：`trust = 0.5`，`category = "unknown"`。
- 记录工人的 `worker_id`（纯数字序号）、`is_trusted`、`trust`、`category`、`total_cost`、`covered_tasks`。

### 1.3.3 生成任务利润与分类（PGRD 专用）
- 收集每个任务的所有原始报价（从工人覆盖中获取 `task_price`），计算平均原始报价 `base_price`。
- 按 `base_price` 降序排序所有任务。
- 设任务总数为 `m`，计算会员任务数量 `k = floor(t × m)`，其中 `t` 为会员任务比例（例如 0.3）。
- 对每个任务：
  - 若为会员任务：`task_price = base_price × member_multiplier`，成本比例 `cost_ratio ∈ [0.4, 0.6]`。
  - 若为普通任务：`task_price = base_price × normal_multiplier`，成本比例 `cost_ratio ∈ [0.7, 0.9]`。
  - 工人成本 `worker_cost = task_price × cost_ratio`。
  - 系统收益 `system_income = task_price × random.uniform(1.2, 2.0)`。
  - 工人净收益 `pure_income = task_price - worker_cost`。
  - 记录任务类型 `type`（`"member"` 或 `"normal"`）。
- 输出任务分类文件，供后续 PGRD 使用。

### 1.3.4 生成任务网格映射
- 遍历 `step6_task_segments.json` 中的所有任务，提取 `task_id` 和 `region_id`。
- 设置 `grid_id = region_id`（直接用区域 ID 作为网格 ID）。
- 输出为 JSON 列表。

### 1.3.5 配置 LGSC 参数
定义以下固定参数，写入配置文件（如 `step6_lgsc_params.json`），供第三阶段 LGSC 报酬支付使用。

| 参数 | 符号 | 含义 | 推荐值 |
|------|------|------|--------|
| 沉没阈值 | $Y$ | 会员沉没值达到该阈值时可兑换会员奖励金 | 500 |
| 会员奖励金 | $\Theta$ | 会员达到阈值时获得的额外奖金（固定值） | 100 |
| 沉没值初始累计率 | $\rho_{\text{init}}$ | 新会员首次参与时的累计率 | 1.0 |

## 1.4 输出文件

### 1.4.1 `step7_worker_option_set.json`
```json
{
  "worker_options": [
    {
      "worker_id": "000",
      "is_trusted": true,
      "trust": 1.0,
      "category": "trusted",
      "total_cost": 37.5,
      "covered_tasks": [
        {
          "task_id": "t00_00",
          "quality": 0.85,
          "task_price": 12.5,
          "start_time": 120,
          "end_time": 380,
          "task_start_time": 120,
          "task_data": 0.67
        }
      ]
    }
  ]
}
```

### 1.4.2 `step7_task_weight_list.json`
```json
{
  "task_weights": {
    "t00_00": 1,
    "t00_01": 2,
    "t01_00": 1
  }
}
```

### 1.4.3 `step7_tasks_grid_num.json`
```json
[
  {"task_id": "t00_00", "grid_id": 0},
  {"task_id": "t00_01", "grid_id": 0},
  {"task_id": "t01_00", "grid_id": 1}
]
```

### 1.4.4 `step7_tasks_classification.json`（PGRD 专用）
```json
[
  {
    "task_id": "t00_00",
    "task_price": 19.5,
    "worker_cost": 9.75,
    "system_income": 29.25,
    "pure_worker_income": 9.75,
    "type": "member"
  },
  {
    "task_id": "t00_01",
    "task_price": 8.0,
    "worker_cost": 6.8,
    "system_income": 12.0,
    "pure_worker_income": 1.2,
    "type": "normal"
  }
]
```

### 1.4.5 `step7_lgsc_params.json`（LGSC 专用）
```json
{
  "sunk_threshold": 500,
  "member_bonus": 100,
  "rho_init": 1.0
}
```

## 1.5 参数
| 参数 | 含义 | 推荐值 |
|------|------|--------|
| 随机种子 | 质量与任务数据随机生成 | 42 |
| `t` | 会员任务比例 | 0.3 |
| `member_multiplier` | 会员报酬倍数 | 1.5 |
| `normal_multiplier` | 普通报酬倍数 | 1.0 |
| `member_cost_range` | 会员成本比例范围 | (0.4, 0.6) |
| `normal_cost_range` | 普通成本比例范围 | (0.7, 0.9) |
| `profit_range` | 系统收益比例范围 | (1.2, 2.0) |
| $Y$ | 沉没阈值 | 500 |
| $\Theta$ | 会员奖励金 | 100 |
| $\rho_{\text{init}}$ | 沉没值初始累计率 | 1.0 |

---

# 第二阶段：初始化（学习阶段）

## 2.1 目标
- 建立工人的初始 CMAB 质量档案。
- 初始化任务覆盖状态。
- 根据第一阶段的数据初始化工人分类集合 `Uc`、`Uu`、`Um`。
- 初始化 PGRD 所需的历史报酬和平均报酬。
- 初始化 LGSC 状态（沉没值、累计率、提现次数等）。

## 2.2 输入
- `step7_worker_option_set.json`
- `step7_task_weight_list.json`
- `step7_tasks_classification.json`
- `step7_lgsc_params.json`

## 2.3 处理步骤

1. **加载数据**：读取工人选项、任务权重、任务分类、LGSC 参数。
2. **提取任务时间映射**：从工人选项中收集每个任务的 `task_start_time`，构建 `task_time_map`（只包含有工人覆盖的任务）。
3. **初始化工人 CMAB 档案**：
   - 学习次数 `n_i = len(covered_tasks)`。
   - 平均感知质量 `avg_quality_i = (∑ quality) / n_i`（若无覆盖任务则为 0）。
   - 判断次数（用于统计）`judge_count = 1`。
   - **计算可用轮次**：对于每个工人，遍历其 `covered_tasks`，提取 `task_start_time`，计算小时 `hour = task_start_time // 3600`，加入集合 `available_rounds`。
4. **初始化工人分类集合**：
   - 根据每个工人的 `category` 字段，将其 ID 分别加入 `Uc`（可信）、`Uu`（未知）、`Um`（恶意，初始为空）。
5. **初始化任务覆盖**：所有任务的覆盖计数置为 0。
6. **计算总学习次数**：`total_learned_counts = ∑ n_i`。
7. **初始化 PGRD 历史报酬**：
   - 所有工人的 `hist_reward_m = 0`，`hist_reward_n = 0`。
8. **初始化平均报酬**：
   - 从 `step7_tasks_classification.json` 计算：
     $$
     R_m = \frac{\sum_{j\in\text{member}} \text{task\_price}_j}{|\text{member}|},\quad R_n = \frac{\sum_{j\in\text{normal}} \text{task\_price}_j}{|\text{normal}|}
     $$
9. **初始化 LGSC 状态**：
   - 对每个工人，初始化：
     - `sunk_value = 0`（沉没值）
     - `sunk_rate = ρ_init`（沉没值累计率）
     - `bonus_count = 0`（奖励金提现次数）
     - `last_period_cost = 0`（上次提现期间总成本）

## 2.4 输出（内部状态）
- 工人档案（扩展了 CMAB 字段、`available_rounds`、PGRD 历史报酬、LGSC 状态）
- 任务覆盖计数字典
- 工人分类集合 `Uc`, `Uu`, `Um`
- 全局变量 `total_learned_counts`, `R_m`, `R_n`
- 任务时间映射 `task_time_map`（`task_id → start_time`）

---

# 第三阶段：贪心轮次（多轮迭代，t=0 至 R-1）

## 3.1 目标
- 按小时轮次招募工人，最大化任务覆盖。
- 每轮先执行 **PGRD 会员决策**（决定工人成为会员的概率及投标任务类型），再生成验证任务，然后进行 **CMAB 招募**，最后更新信任度和历史报酬，并在每轮结束后执行 **LGSC 报酬支付**。

## 3.2 输入
- 第二阶段输出的工人档案、任务覆盖状态、工人分类集合、全局变量、任务时间映射。
- 参数：总预算 `B`，每轮招募人数 `K`，总轮数 `R=24`，信任度更新步长 `η`，可信阈值 `θ_high`，恶意阈值 `θ_low`，每轮验证任务数 `M`。
- PGRD 参数：`α, β, ζ, λ, σ, ψ_th, fee`。
- LGSC 参数：`Y, Θ, ρ_init`。
- 任务网格映射 `step7_tasks_grid_num.json`（`task_id → grid_id`）。
- 任务分类 `step7_tasks_classification.json`。

## 3.3 每轮处理步骤（循环 t=0 至 R-1）

### 3.3.1 确定当前轮可用工人与任务
- **可用工人**：工人的 `available_rounds` 集合中包含当前轮次 `t` 的工人。
- **可用任务**：从任务时间映射中获取 `task_start_time // 3600 == t` 且**尚未完成**的任务（即 `task_covered_count[tid] < required_workers[tid]`）。

### 3.3.2 终止条件检查
- 若剩余预算 < 当前轮可用工人中的最小成本，终止。
- 若当前轮无可用任务，终止。
- 若达到最大轮数，终止。

您指出的问题非常关键。在 PGRD 决策中，工人可能同时覆盖多个会员任务或普通任务，因此预期效用应该基于**任务数量**进行累加，而不是假设只有一个任务。下面修正 3.3.3 节的内容。

---

### 3.3.3 PGRD 会员决策（基于上一轮报酬）
- **输入**：工人档案（含 `hist_reward_m`, `hist_reward_n`, `category`）、任务分类 `task_class`、上一轮平均报酬 `R_m`, `R_n`、PGRD 参数。
- **输出**：
  - `member_set`：本轮成为会员的工人ID集合（会员身份持续多轮，需在工人档案中记录 `is_member` 及 `member_until` 轮次）。
  - `bid_tasks`：字典，工人ID → 任务ID列表（该工人本轮投标的任务，仅包含当前轮次可执行的任务）。
  - `total_fee`：会费总收入。
- **处理步骤**：
  1. 对每个当前轮可用的工人（恶意除外）：
     - 获取其可覆盖且属于当前轮次的任务集（通过 `covered_tasks` 中 `task_start_time` 判断）。
     - 将这些任务按任务分类分为会员任务集 `member_tasks` 和普通任务集 `normal_tasks`。
     - 记会员任务数量 $N_m = |\text{member\_tasks}|$，普通任务数量 $N_n = |\text{normal\_tasks}|$。
     - **若工人已是会员（`is_member=True` 且 `member_until ≥ t`）**，则直接投标所有任务：`bid_tasks[wid] = member_tasks + normal_tasks`，不重复交会费。
     - **若工人不是会员**，则：
       - 若工人类别为 `unknown`，则直接投标普通任务：`bid_tasks[wid] = normal_tasks`，且不加入 `member_set`。
       - 若工人类别为 `trusted`，则进行概率计算：
         - 计算每个会员任务的预估收益（单任务）：
           $$
           b_m = \alpha \cdot \text{hist\_reward}_m + \beta \cdot R_m
           $$
         - 计算每个普通任务的预估收益（单任务）：
           $$
           b_n = \alpha \cdot \text{hist\_reward}_n + \beta \cdot R_n
           $$
         - 计算每个会员任务的参照损失（单任务）：
           $$
           \text{loss} = \lambda \cdot \bigl(\beta (R_m - R_n)\bigr)^\sigma \quad (\text{若 } R_m > R_n)
           $$
         - 计算平均成本：
           - 若选择成为会员，该工人本轮可覆盖的会员任务的平均成本：
             $$
             \text{cost}_m = \frac{\sum_{j\in\text{member tasks}} \text{worker\_cost}_j}{N_m} \quad (\text{若 } N_m > 0)
             $$
           - 若选择保持非会员，该工人本轮可覆盖的普通任务的平均成本：
             $$
             \text{cost}_n = \frac{\sum_{j\in\text{normal tasks}} \text{worker\_cost}_j}{N_n} \quad (\text{若 } N_n > 0)
             $$
         - 计算预期效用：
           - 若选择成为会员（投标所有会员任务，普通任务收益与决策比较无关，故不计入）：
             $$
             U_{\text{member}} = N_m \cdot (b_m + \text{loss} - \text{cost}_m) - \text{fee}
             $$
           - 若选择保持非会员（只投标普通任务）：
             $$
             U_{\text{normal}} = N_n \cdot (b_n - \text{cost}_n)
             $$
         - 计算成为会员的概率：
           $$
           \psi = \frac{e^{\zeta U_{\text{member}}}}{e^{\zeta U_{\text{member}}} + e^{\zeta U_{\text{normal}}}}
           $$
         - 若 `ψ ≥ ψ_th`，则工人成为会员，投标所有任务：`bid_tasks[wid] = member_tasks + normal_tasks`，加入 `member_set`，累加会费 `total_fee += fee`，并记录其会员身份有效期为当前轮 + 会员有效周期（如 5 轮）。
         - 否则，工人投标其所有普通任务：`bid_tasks[wid] = normal_tasks`。
  2. 返回 `bid_tasks`, `member_set`, `total_fee`。

**说明**：第一轮时，所有工人的 `hist_reward_m` 和 `hist_reward_n` 均为0，`R_m` 和 `R_n` 由任务分类文件中的任务平均报酬计算得到。会员身份一旦获得，将持续多轮，期间无需重复交费，且自动投标所有任务。当工人覆盖的会员任务数为0时，不能选择成为会员（因为成为会员后无会员任务可做，会费无意义）；当普通任务数为0时，非会员分支不可用（即只能选择成为会员）。

---

### 3.3.4 生成验证任务（基于当前轮可用工人的轨迹）
- **网格统计**：  
  对每个当前轮可用的工人，根据其覆盖的任务（每个任务对应一个网格），统计每个网格中 `Uc` 工人出现次数和 `Uu` 工人出现次数。  
  （注意：只统计**本轮可用工人**，因为只有这些工人会实际执行任务。）
- **筛选**：仅保留 `Uc` 出现次数 > 0 的网格（即有可信工人经过的网格）。若没有这样的网格，则本轮不生成验证任务。
- **排序**：将筛选后的网格按 `Uu` 出现次数降序排列，取前 `M` 个网格。
- **任务选取**：对每个选中网格，从该网格的**可用任务列表**中**随机选取一个任务**作为验证任务（确保该任务属于当前轮次）。
- 生成验证任务列表 `validation_tasks`（实际数量可能少于 M，如果可信网格不足）。

**说明**：只选择有可信工人经过的网格，确保每个验证任务都有可信工人作为基准。可信工人可以顺路完成验证任务，其成本已包含在招募中，因此不增加额外开销；未知工人执行验证任务会产生成本，但通过控制 M 可调节。若可信网格不足，验证任务数量会相应减少，避免为无基准的任务支付成本。

### 3.3.5 发布任务
- 业务任务：当前轮可用的所有原始任务（权重为 `required_workers`）。
- 验证任务：`validation_tasks`（权重设为 0，不参与业务增益计算，但工人执行会消耗成本）。

**执行范围**：验证任务由所有**本轮可用的工人**（即其轨迹覆盖当前轮次的工人）执行，因为这些工人在本轮时间窗口内可以顺路完成验证任务。因此，每轮可能有大量工人参与验证，信任度更新可同时影响许多工人，实现快速批量识别可信/恶意工人。每个工人的 `task_data` 是预先随机生成并固定，因此对同一验证任务，同一工人每次上报的数据相同。

**成本说明**：工人执行验证任务同样会获得报酬（`task_price` 已计入其总成本），因此每轮验证任务会额外增加平台支出。这是快速验证的代价，可通过参数 `M` 控制验证任务数量来调节成本与验证效率的平衡。

### 3.3.6 招募工人（CMAB 贪心选择）

本小节详细阐述基于CMAB（组合多臂老虎机）的贪心策略招募工人流程，核心目标是在预算约束下，选择性价比最优的工人完成任务，同时实时更新工人质量档案与任务覆盖状态，具体步骤如下：

1. 候选工人筛选

首先确定本轮可用的候选工人集合，筛选规则如下：

- 候选工人范围为可信工人集合 $$U_c$$ 与未知工人集合 $$U_u$$ 的并集（即 $$U_c \cup U_u$$），明确排除恶意工人集合 $$U_m$$，避免恶意工人对任务质量造成影响。

- 仅保留当前轮次（$$\text{round_idx}$$）可用的工人，即工人的可用轮次列表（$$\text{available_rounds}$$）中包含当前轮次标识。

- 每个工人的可覆盖任务集，统一替换为其本轮竞标任务集 $$\text{bid\_tasks}$$，且 $$\text{bid\_tasks}$$ 仅包含当前轮次发布的任务，不涉及其他轮次任务。

2. CMAB 贪心选择策略（每轮选择 K 个工人）

采用UCB（Upper Confidence Bound，上置信界）贪心策略，每轮从候选工人中选择最多 K 个性价比最优的工人，具体步骤如下：

2.1 计算工人 UCB 质量评分

对每个候选工人 $$i$$，基于其历史表现计算UCB质量评分 $$\hat{q}_i(t)$$，公式如下：

$$\hat{q}_i(t) = \bar{q}_i(t-1) + \sqrt{\frac{(K+1)\ln(T_{\text{learn}})}{n_i(t-1)}}$$

其中各符号含义：

- $$\bar{q}_i(t-1)$$：工人$$i$$ 在第 $$t$$ 轮之前的历史平均质量；

- $$K$$：本轮最多可选择的工人数；

- $$T_{\text{learn}}$$：截至当前轮次的全局累计学习任务量（即 $$\text{total\_learned\_counts}$$）；

- $$n_i(t-1)$$：工人 $$i$$ 在第 $$t$$ 轮之前的累计完成任务数（即 $$n_i$$）。

若工人$$i$$ 尚未完成任何任务（$$n_i(t-1) = 0$$），则其UCB质量评分默认设为1.0，确保该工人有被探索的机会。

2.2 计算工人边际增益

边际增益用于衡量工人完成任务所能带来的价值，仅考虑其 $$\text{bid\_tasks}$$ 中尚未完成的任务，公式如下：

$$\text{gain}_i = \sum_{j \in \text{bid\_tasks}_i \cap \text{uncov}} w_j \cdot \hat{q}_i(t)$$

其中各符号含义：

- $$\text{bid\_tasks}_i$$：工人 $$i$$ 本轮竞标的任务集合；

- $$\text{uncov}$$：当前轮次中尚未完成的任务集合，即任务覆盖计数（$$\text{task\_covered\_count}$$）小于该任务所需工人数（$$\text{required\_workers}$$）的任务；

- $$w_j$$：任务 $$j$$ 所需的工人数（即 $$\text{required\_workers}[j]$$）；

- $$\hat{q}_i(t)$$：工人 $$i$$ 本轮的UCB质量评分。

2.3 计算工人性价比并选择最优工人

工人的性价比定义为边际增益与雇佣成本的比值，计算公式如下：

$$\text{性价比}_i = \frac{\text{gain}_i}{\text{cost}_w}$$

其中 $$\text{cost}_w$$ 为雇佣工人 $$i$$ 的成本，计算方式为：$$\text{cost}_w = \text{len}(\text{bid\_tasks}_i) \times \text{工人固定报价}$$，工人固定报价即其预设的单位任务成本（$$\text{cost}$$）。

若工人的边际增益 $$\text{gain}_i = 0$$（即其竞标任务均已完成），则其性价比设为0。每轮迭代中，选择性价比最高的工人加入本轮选中列表，同时将该工人从候选工人集合中移除，避免重复选择。

重复上述步骤，直至选中 K 个工人或候选工人集合为空。

3. 成本与预算更新

对每一个选中的工人，将其雇佣成本 $$\text{cost}_w$$ 累加到本轮总花费（$$\text{round\_cost}$$）中；同时从剩余预算（$$\text{remaining\_budget}$$）中扣除该成本，更新剩余预算与全局总成本。

4. 任务覆盖计数更新

对每一个选中的工人，遍历其 $$\text{bid\_tasks}$$ 中的任务，若该任务属于未完成任务集合 $$\text{uncov}$$（即任务覆盖计数小于所需工人数），则将该任务的覆盖计数加1，直至该任务的覆盖计数达到所需工人数（任务完成）。

5. 工人档案更新

选中工人完成任务后，实时更新其个人档案信息，具体更新规则如下：

- 新增学习次数：工人本轮实际贡献的任务数，即其 $$\text{bid\_tasks}$$ 与未完成任务集合$$\text{uncov}$$ 的交集大小（$$|\text{bid\_tasks}_i \cap \text{uncov}|$$）。

- 累计完成任务数更新：将工人的累计完成任务数 $$n_i$$ 加上本轮新增学习次数。

- 平均质量更新：采用加权平均方式更新工人的历史平均质量 $$\bar{q}_i$$，计算公式为：
        
$$\bar{q}_i(t) = \frac{\bar{q}_i(t-1) \times (n_i(t) - \Delta n_i) + q_i(t) \times \Delta n_i}{n_i(t)}$$
其中，$$\Delta n_i$$ 为本轮新增学习次数，$$q_i(t)$$ 为工人本轮完成任务的真实质量（观测值）。

- 全局累计学习任务量更新：将全局累计学习任务量 $$\text{total\_learned\_counts}$$ 加上该工人的本轮新增学习次数。


### 3.3.7 信任度更新（基于验证任务）
- 对于每个验证任务 `v`：
  1. 收集所有完成该任务的 `Uc` 工人的 `task_data`，取中位数作为基准 `base`。由于生成时已保证有 Uc 工人，此步骤通常有数据。若因特殊情况（如可信工人未完成该任务）导致无数据，则跳过该任务。
  2. 对于每个完成该任务的 `Uu` 工人 `i`（**仅限本轮可用的工人**），获取其上报数据 `data`：
     - 计算误差：
       $$
       \text{error} = \frac{|data - base|}{base} \quad (\text{若 } base = 0 \text{ 则 } error = |data - base|)
       $$
     - 更新信任度：
       $$
       \text{trust}_i \leftarrow \text{trust}_i + \eta (1 - 2\cdot\text{error})
       $$
       $$
       \text{trust}_i \leftarrow \max(0, \min(1, \text{trust}_i))
       $$
     - 若 `trust_i ≥ θ_high`，将工人从 `Uu` 移入 `Uc`，更新 `category`。
     - 若 `trust_i ≤ θ_low`，将工人从 `Uu` 移入 `Um`，更新 `category`。

**说明**：每个验证任务都有可信工人作为基准，因此信任更新可正常进行。

您说得完全正确。`hist_reward_m` 和 `hist_reward_n` 应该是**平均报酬**，而不是总和，这样才能与 `R_m`、`R_n` 在量纲上一致，且符合论文中 PGRD 的公式。下面修正 3.3.8 节。

---

### 3.3.8 更新历史报酬与平均报酬
- 对于本轮被招募的工人，根据其实际完成的任务（即 `bid_tasks` 中被选中的部分），计算其**平均报酬**（按类型）：
  - 会员任务平均报酬：
    $$
    \text{hist\_reward}_m(i) = 
    \begin{cases}
    \dfrac{\sum_{j \in \text{member tasks completed by } i} \text{task\_price}_j}{\text{number of member tasks completed by } i}, & \text{if completed member tasks > 0} \\
    0, & \text{otherwise}
    \end{cases}
    $$
  - 普通任务平均报酬：
    $$
    \text{hist\_reward}_n(i) = 
    \begin{cases}
    \dfrac{\sum_{j \in \text{normal tasks completed by } i} \text{task\_price}_j}{\text{number of normal tasks completed by } i}, & \text{if completed normal tasks > 0} \\
    0, & \text{otherwise}
    \end{cases}
    $$
- 计算新平均报酬（用于下一轮 PGRD）：
  - **会员任务平均报酬 $R_m$**：统计所有**本轮被完成**的会员任务，计算其平均报酬：
    $$
    R_m = \frac{\sum_{j \in \text{member tasks completed this round}} \text{task\_price}_j}{\text{number of member tasks completed this round}}
    $$
    若无会员任务被完成，则 $R_m$ 保持原值。
  - **普通任务平均报酬 $R_n$**：同理：
    $$
    R_n = \frac{\sum_{j \in \text{normal tasks completed this round}} \text{task\_price}_j}{\text{number of normal tasks completed this round}}
    $$
    若无普通任务被完成，则 $R_n$ 保持原值。

**说明**：`hist_reward_m(i)` 和 `hist_reward_n(i)` 存储的是工人 $i$ 上一轮获得的**平均报酬**（按任务类型），用于下一轮的 PGRD 预估收益计算。`R_m` 和 `R_n` 是平台层面的平均报酬，同样基于本轮完成的任务计算。这样，工人对任务的预估收益 $b_m = \alpha \cdot \text{hist\_reward}_m(i) + \beta \cdot R_m$ 具有统一的量纲（均为每任务平均报酬），符合行为经济学模型的设定。

---

以上修改已将 PGRD 决策中的效用计算调整为基于会员任务数量（而非总任务数），成本也只考虑会员任务的平均成本，非会员分支则基于普通任务数量。同时历史报酬计算保持不变，符合您的预期。

# 3.3.9 LGSC 报酬支付（沉没成本激励）
- **输入**：本轮被招募的工人及其实际完成的任务列表（从 `cmab_round` 返回的 `round_selected` 和对应的 `bid_tasks`）、任务成本（从任务分类文件中获取 `worker_cost`）、LGSC 参数。
- **处理步骤**：
  1. 对每个**有效会员工人**（`is_member=True` 且 `member_until >= t`），更新其沉没值：
     $$
     M_i \leftarrow M_i + \rho_i \cdot \sum_{j \in \text{本轮完成的任务}} c_i^j
     $$
     其中 `c_i^j` 为任务 `j` 的工人成本（`worker_cost`），同步累计该会员本次达标周期内的总任务成本。
  2. 对每个工人（包括会员和非会员），根据其类别和沉没值支付报酬：
     - 若工人为**有效会员**且 `M_i ≥ Y`：
       实际报酬 = `∑ b_i^j + Θ`（基础报酬 + 奖励金）
       然后重置 `M_i = 0`，`G_i += 1`，并更新沉没值累计率：
       $$
       \rho_i \leftarrow 1 + \frac{Θ \cdot G_i}{Θ \cdot G_i + \sum_{j=1}^{K} c_i^j}
       $$
       其中 `∑c` 为该会员本次达到阈值过程中累计完成的任务总成本（从上次提现到本次提现），同时清空周期累计成本。
     - 若工人为**有效会员**且 `M_i < Y`：
       实际报酬 = `∑ b_i^j`
       沉没损失（用于统计）`H_i = (Θ / Y) · M_i`
     - 若非会员/会员已过期（包括未知工人和恶意工人）：
       实际报酬 = `∑ b_i^j`
  3. 计算投资回报率（用于分析）：
     $$
     ROI_i = \frac{\text{实际报酬} - \sum c_i^j}{\sum c_i^j}
     $$
     对于未达到阈值的会员，`H_i` 可作为预期收益的一部分（若继续参与）。
  4. 记录本轮会员工人的沉没值变化、奖励金发放情况，用于后续留存率分析。

---

### 修正说明（完全不改动你的格式/文字/结构，仅修复核心逻辑）
1. **会员判定修正**：新增「有效会员」定义（会员+未到期），解决过期会员参与激励的问题
2. **沉没值统计修正**：新增周期成本累计，匹配累计率更新公式
3. **沉没损失逻辑修正**：仅有效会员未达标时计算，解决`沉没成本一直为0`的问题
4. **全格式保留**：你的原文排版、公式、标点、步骤、变量名**完全不动**

### 3.3.10 记录本轮数据并输出统计
- 将本轮会员集合 `member_set`、非会员集合（即所有当前轮可用工人中不属于会员的工人ID列表）、平均报酬 `R_m` 和 `R_n` 保存到 `round_details` 列表中。
- 新增 LGSC 统计：记录会员沉没值达到阈值人数、奖励金发放总额、平均沉没损失、平均投资回报率、会员留存率（连续多轮参与的会员比例）。
- 打印：轮次、招募人数、总成本、剩余预算、当前轮已完成任务数、`|Uc|`、`|Uu|`、`|Um|`、会员人数、会费总收入、平均报酬 `R_m` 和 `R_n`，以及 LGSC 相关指标。

## 3.4 输出

最终输出 JSON 文件，包含：
- `total_rounds`：实际贪心轮数
- `total_cost`：总花费（仅贪心阶段的成本）
- `remaining_budget`：剩余预算
- `selected_workers`：贪心阶段招募的工人ID列表
- `init_select`：初始轮涉及的工人数（所有工人）
- `later_select`：贪心阶段招募的工人总次数
- `covered_task_count`：最终覆盖的任务数
- `trusted_count`：最终可信工人数
- `malicious_count`：最终恶意工人数
- `unknown_count`：最终未知工人数
- `trusted_workers_list`：最终可信工人 ID 列表
- `total_fee`：会费总收入
- **新增 LGSC 输出**：
  - `total_bonus_paid`：会员奖励金发放总额
  - `avg_sunk_loss`：平均沉没损失（未达阈值会员的损失平均值）
  - `avg_roi`：平均投资回报率
  - `member_retention_rate`：会员留存率（连续参与多轮的会员比例）
- `round_details`：列表，每个元素对应一轮，包含：
  - `round`：轮次编号
  - `member_set`：会员工人ID列表
  - `non_member_set`：非会员工人ID列表（当前轮可用的工人中不属于会员的）
  - `R_m`：本轮会员任务平均报酬
  - `R_n`：本轮普通任务平均报酬
  - `member_count`：会员人数
  - `non_member_count`：非会员人数
  - **新增 LGSC 轮次详情**：
    - `bonus_paid_this_round`：本轮发放的奖励金总额
    - `avg_sunk_loss_this_round`：本轮平均沉没损失
    - `avg_roi_this_round`：本轮平均投资回报率
    - `members_above_threshold`：本轮沉没值达到阈值的会员人数

---

## 参数汇总

| 参数 | 含义 | 推荐值 | 所属阶段 |
|------|------|--------|----------|
| 随机种子 | 质量与任务数据随机生成 | 42 | 第一阶段 |
| `t` | 会员任务比例 | 0.3 | 第一阶段 |
| `member_multiplier` | 会员报酬倍数 | 1.5 | 第一阶段 |
| `normal_multiplier` | 普通报酬倍数 | 1.0 | 第一阶段 |
| `member_cost_range` | 会员成本比例范围 | (0.4, 0.6) | 第一阶段 |
| `normal_cost_range` | 普通成本比例范围 | (0.7, 0.9) | 第一阶段 |
| `profit_range` | 系统收益比例范围 | (1.2, 2.0) | 第一阶段 |
| $Y$ | 沉没阈值 | 500 | 第一阶段（LGSC） |
| $\Theta$ | 会员奖励金 | 100 | 第一阶段（LGSC） |
| $\rho_{\text{init}}$ | 沉没值初始累计率 | 1.0 | 第一阶段（LGSC） |
| $B$ | 总预算 | 100000 | 第三阶段 |
| $K$ | 每轮招募人数 | 3 | 第三阶段 |
| $R$ | 最大轮数 | 24 | 第三阶段 |
| $M$ | 每轮验证任务数 | 3 | 第三阶段 |
| $\eta$ | 信任度更新步长 | 0.2 | 第三阶段 |
| $\theta_{\text{high}}$ | 可信阈值 | 0.8 | 第三阶段 |
| $\theta_{\text{low}}$ | 恶意阈值 | 0.2 | 第三阶段 |
| $\alpha, \beta$ | 预估收益权重 | 0.6, 0.4 | 第三阶段（PGRD） |
| $\zeta$ | 差异敏感度 | 1.0 | 第三阶段（PGRD） |
| $\lambda$ | 损失厌恶系数 | 2.25 | 第三阶段（PGRD） |
| $\sigma$ | 价值函数曲率 | 0.88 | 第三阶段（PGRD） |
| $\psi_{th}$ | 会员概率阈值 | 0.5 | 第三阶段（PGRD） |
| $fee$ | 会费 | 10 | 第三阶段（PGRD） |

---

## 总结

本算法通过三个阶段实现工人招募与激励：数据准备阶段生成所有基础数据，并重新划分会员/普通任务，同时配置 LGSC 参数；初始化阶段建立质量档案、分类和激励状态；贪心轮次阶段集成了 **PGRD 会员决策**（吸引可信工人成为会员）、**信任度验证**（通过空间一致性筛选可信工人）、**CMAB 招募**（高效分配任务）和 **LGSC 沉没成本激励**（通过沉没值、奖励金和累计率更新，使会员“越投入越难退出”）。每轮中，工人和任务都严格按时间轮次划分，投标任务只包含当前轮次可执行的任务，确保时间一致性。验证任务只从有可信工人经过的网格中选取，保证了基准可靠性，同时由所有可用工人执行，实现高效批量验证。PGRD 通过参照依赖激励可信工人成为会员，提升平台效用；LGSC 通过沉没成本效应激励会员长期留存，提高用户留存率。最终输出包含每轮的会员集合、非会员集合、平均报酬以及 LGSC 统计指标，便于深入分析平台效用与长期激励效果。