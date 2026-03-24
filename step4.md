输入 step2_worker_option_set.json

先提取每个任务的task_price 作为reward   代表工人做完任务的报酬
生成worker_cost 代表工人做任务的成本
然后按你说的方法生成system_income  代表完成这个任务系统的净收益 

所以后续如果要比较工人收益 应该用reward-worker_cost   然后系统除了会费只在任务的收益为system_income - reward 


然后根据工人收益再排序 t作为比例 实现算法3.1

最终输出： 会员任务集合和普通任务集合    生成step4_tasks_classification.json
json内每个人物可以写成
{
    "task_id": "t03_00",
    "task_price": 49.68570051909786,
    "worker_cost"
    "system_income"
    "pure_worker_income"
    "type": "member"
  },   

# 一、任务利润生成与会员任务划分（增强净收益差异版）

## 1. 概述
在群智感知系统中，平台需要将任务划分为两类：
- **会员任务**：高工人净收益，仅限会员用户参与。
- **普通任务**：低工人净收益，所有用户均可参与。

通过工人净收益的差异，利用参照依赖效应激励普通用户加入会员，从而提高平台效用。本步骤从工人覆盖数据中提取每个任务的原始报价平均值，按报价高低确定任务类型，然后使用**固定倍数**调整会员任务和普通任务的报酬，并针对不同任务类型设置**不同的成本比例范围**，从而显著拉大会员任务与普通任务的工人净收益差距，增强参照依赖效应。

---

## 2. 输入
- **`step2_worker_option_set.json`**：每个工人覆盖的任务列表，每个任务包含 `task_id`、`quality`、`task_price`（工人对该任务的报价）。
- **参数**：
  - `t`：会员任务比例（0 < t ≤ 1），例如 0.3 表示 30% 的任务为会员任务。
  - `member_multiplier`：会员任务报酬倍数（>1），例如 1.5。
  - `normal_multiplier`：普通任务报酬倍数（≤1），例如 1.0。
  - `member_cost_range`：会员任务成本占报酬的比例范围，例如 (0.4, 0.6)。
  - `normal_cost_range`：普通任务成本占报酬的比例范围，例如 (0.7, 0.9)。
  - `profit_range`：系统收益占报酬的比例范围，例如 (1.2, 2.0)。
  - 随机种子（可选）：用于生成随机数，保证结果可复现。

---

## 3. 输出
- **`step4_tasks_classification.json`**：每个任务包含以下字段：
  - `task_id`：任务ID
  - `task_price`：平台支付给工人的报酬（经倍数调整后）
  - `worker_cost`：工人完成该任务的平均成本（随机生成，小于 `task_price`）
  - `system_income`：平台从该任务中获得的收益（随机生成，大于 `task_price`）
  - `pure_worker_income`：工人净收益 = `task_price - worker_cost`
  - `type`：`"member"` 或 `"normal"`

---

## 4. 处理步骤

### 4.1 提取每个任务的原始报价平均值
- 遍历所有工人的 `covered_tasks`，对每个任务收集其所有出现时的 `task_price`。
- 对每个任务，计算 `task_price` 的平均值作为该任务的原始报价 `base_price`。

### 4.2 确定任务类型
- 将所有任务按 `base_price` 降序排序（报价高的任务更有价值，应优先成为会员任务）。
- 设任务总数为 `m`，计算 `k = floor(t × m)`。
- 前 `k` 个任务标记为 `"member"`，其余标记为 `"normal"`。

### 4.3 调整报酬（固定倍数）
- **会员任务**：`task_price = base_price × member_multiplier`
- **普通任务**：`task_price = base_price × normal_multiplier`

### 4.4 生成工人成本和系统收益
对每个任务，根据其类型选择不同的成本比例范围，并随机生成：
- **工人成本**：
  ```
  if task_type == 'member':
      cost_ratio = random.uniform(member_cost_range[0], member_cost_range[1])
  else:
      cost_ratio = random.uniform(normal_cost_range[0], normal_cost_range[1])
  worker_cost = task_price × cost_ratio
  ```
  保证 `worker_cost < task_price`，且会员任务的成本比例更低，从而获得更高的净收益。
- **系统收益**：
  ```
  system_income = task_price × random.uniform(profit_range[0], profit_range[1])
  ```
  保证 `system_income > task_price`，平台获得正利润。

### 4.5 计算工人净收益
```
pure_worker_income = task_price - worker_cost
```

### 4.6 保存结果
将每个任务的完整信息保存到 `step4_tasks_classification.json`。

---

## 5. 参数说明与调试建议

| 参数 | 含义 | 推荐范围 | 调试方向 |
|------|------|----------|----------|
| `t` | 会员任务比例 | 0.2 ~ 0.5 | 比例越大，会员任务越多，参照损失可能更明显。 |
| `member_multiplier` | 会员任务报酬倍数 | 1.2 ~ 2.0 | 越大，会员任务报酬越高，吸引力越强。 |
| `normal_multiplier` | 普通任务报酬倍数 | 0.8 ~ 1.0 | 越小，普通任务报酬越低，会员相对优势更大。 |
| `member_cost_range` | 会员任务成本比例 | (0.4, 0.6) | 值越小，会员净收益越高。 |
| `normal_cost_range` | 普通任务成本比例 | (0.7, 0.9) | 值越大，普通净收益越低。 |
| `profit_range` | 系统收益比例 | (1.2, 2.0) | 确保平台盈利。 |
| 随机种子 | 控制随机性 | 任意整数 | 固定后结果可复现。 |

**调试步骤**：
1. 先固定 `t=0.3`，设置 `member_multiplier=1.5`，`normal_multiplier=1.0`，`member_cost_range=(0.4,0.6)`，`normal_cost_range=(0.7,0.9)`。
2. 运行脚本，查看输出统计信息，确认会员任务平均净收益显著高于普通任务（例如会员净收益是普通的 2~3 倍）。
3. 如果差异不够，可调整 `member_cost_range` 下限（如 (0.3,0.5)）或 `normal_cost_range` 上限（如 (0.8,1.0)），也可增大 `member_multiplier`。
4. 得到满意的数据后，此文件作为固定输入，后续在算法3-2中调整会费 `fee` 观察会员人数变化。

---

## 6. 示例
假设从 `step2_worker_option_set.json` 中提取到 3 个任务，其 `task_price` 出现情况如下：
- `t00_00`：被 2 个工人覆盖，报价分别为 12 和 14 → `base_price = 13`
- `t00_01`：被 1 个工人覆盖，报价 8 → `base_price = 8`
- `t00_02`：被 3 个工人覆盖，报价分别为 10, 11, 9 → `base_price = 10`

取 `t = 0.5`，则 `k = floor(3×0.5)=1`。按 `base_price` 降序排序：t00_00 (13) > t00_02 (10) > t00_01 (8)，前 1 个为会员任务，即 t00_00。

设置参数：
- `member_multiplier = 1.5`，`normal_multiplier = 1.0`
- `member_cost_range = (0.4, 0.6)`，`normal_cost_range = (0.7, 0.9)`
- `profit_range = (1.2, 2.0)`

生成数据：
- 会员任务 t00_00：`task_price = 13 × 1.5 = 19.5`，`cost_ratio = 0.5`（假设）→ `worker_cost = 9.75`，`pure_income = 9.75`，`system_income = 19.5 × 1.5 = 29.25`。
- 普通任务 t00_02：`task_price = 10 × 1.0 = 10.0`，`cost_ratio = 0.8`（假设）→ `worker_cost = 8.0`，`pure_income = 2.0`，`system_income = 10 × 1.5 = 15.0`。
- 普通任务 t00_01：`task_price = 8 × 1.0 = 8.0`，`cost_ratio = 0.85`（假设）→ `worker_cost = 6.8`，`pure_income = 1.2`，`system_income = 8 × 1.5 = 12.0`。

输出 `step4_tasks_classification.json`：
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
    "task_id": "t00_02",
    "task_price": 10.0,
    "worker_cost": 8.0,
    "system_income": 15.0,
    "pure_worker_income": 2.0,
    "type": "normal"
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

---

## 7. 注意事项
- 同一任务可能被不同工人覆盖，其报价可能不同，因此使用平均值作为原始报价。
- 工人成本 `worker_cost` 和系统收益 `system_income` 在任务层面生成，不随工人变化。这简化了模型，但后续算法3-2中工人实际净收益可能因个体报酬不同而异，但任务类型是基于平均值的，仍可作为参照。
- 参数 `t` 的选择会影响会员任务数量，从而影响参照依赖的强度。建议通过实验确定最优值。
- 通过分别设置会员和普通任务的成本比例范围，可以直观控制两类任务的净收益差距。固定倍数法使报酬差异直观可控，便于调试。随机生成的值可通过设置随机种子保证结果可复现。

3.2 算法  输入 step4_tasks_classification.json文件的分类集合 和step2_worker_option_set.json
先算出 任务区的平均报酬公式3.1   step4_tasks_classification.json文件的分类集合  

先置被选中的任务集合为空   设一个参加会员任务概率阈值  合理设置会费
对于每一个工人循环遍历：
      先算会员与非会员任务预估收益 
      再通过这个算参照依赖损失
      最后得出该工人参与会员任务的概率 
      与阈值比较
      如果大于则让该工人加入会员集合
      并且统计会费累加
      小于就是加入普通集合

      并且统计被选中的任务集合 以便系统生成给出下一轮的会员与非会员任务平均报酬



输出被选中的任务集合 会员和普通工人集合  以及平台效用 （告诉我怎么看）  用户效用  你不应该这样写文档吗

# 算法3-2：单轮用户任务选择机制

## 1. 目的
在给定当前轮次的任务分类（会员任务/普通任务）和工人历史报酬（上一轮数据）的情况下，计算每个普通工人成为会员的概率，并决定其任务选择。本算法仅处理单轮决策，为后续多轮迭代提供基础。

---

## 2. 输入

| 输入项 | 说明 | 来源 |
|--------|------|------|
| `worker_options` | 每个工人覆盖的任务列表，每个任务包含 `task_id`, `quality`, `task_price` | `step2_worker_option_set.json` |
| `task_classification` | 每个任务的任务ID、报酬、成本、系统收益、类型（`member`/`normal`） | `step4_tasks_classification.json` |
| `R_m` | 上一轮会员任务的平均报酬（第一轮用任务平均报酬初始化） | 计算获得 |
| `R_n` | 上一轮普通任务的平均报酬（第一轮用任务平均报酬初始化） | 计算获得 |
| `hist_reward_m_i` | 工人i上一轮在会员任务上的平均报酬（第一轮设为0或任务平均报酬） | 上一轮记录 |
| `hist_reward_n_i` | 工人i上一轮在普通任务上的平均报酬（第一轮设为0或任务平均报酬） | 上一轮记录 |
| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `alpha` | 历史报酬权重 | 0.6 |
| `beta` | 平均报酬权重（`alpha+beta=1`） | 0.4 |
| `fee` | 会员费（固定值） | 根据数据计算（见第6节） |
| `zeta` | 差异敏感度 | 1 |
| `lambda` | 损失厌恶系数（λ>1） | 2.25 |
| `sigma` | 价值函数曲率（0<σ<1） | 0.88 |
| `psi_th` | 成为会员的概率阈值 | 0.5 |

---

## 3. 输出

- **会员集合** `members`：本轮选择成为会员的工人ID列表。
- **普通集合** `normals`：本轮选择普通任务的工人ID列表。
- **被选中的任务集合** `selected_tasks`：所有工人选择的任务ID列表（去重）。
- **平台效用** `platform_utility` = 所有选中任务的 `system_income` 之和 + 会费总收入 - 支付给工人的报酬之和。
- **用户效用** `user_utility` = 所有工人获得的报酬之和 - 所有工人的成本之和 - 会费总收入（即工人总净收益）。

---

## 4. 处理步骤

### 4.1 初始化（第一轮特有）
- 从 `task_classification` 中提取：
  - 会员任务的平均报酬 `R_m` = 所有会员任务的 `task_price` 的平均值。
  - 普通任务的平均报酬 `R_n` = 所有普通任务的 `task_price` 的平均值。
- 对每个工人，若其可覆盖任何会员任务，则 `hist_reward_m_i = R_m`，否则 0；若可覆盖任何普通任务，则 `hist_reward_n_i = R_n`，否则 0。（第一轮无历史数据，用平均值近似）

### 4.2 对每个工人（非会员）循环

1. **计算预估收益**（公式3-2）：
   ```
   b_m = alpha * hist_reward_m_i + beta * R_m
   b_n = alpha * hist_reward_n_i + beta * R_n
   ```

2. **计算参照损失**（公式3-5）：
   ```
   loss = lambda * (beta * (R_m - R_n))^sigma
   ```
   其中 `lambda` 为损失厌恶系数（>1），`sigma` 为曲率（0<σ<1）。该公式将实际差值放大，体现损失厌恶。

3. **计算预期效用**（公式3-7、3-8）：
   - 工人成本 `cost_m_i` = 该工人覆盖的会员任务的平均 `worker_cost`（若无会员任务则为0）。
   - 工人成本 `cost_n_i` = 该工人覆盖的普通任务的平均 `worker_cost`（若无普通任务则为0）。
   ```
   U_member = b_m + loss - cost_m_i - fee
   U_normal = b_n - cost_n_i
   ```

4. **计算成为会员的概率**（公式3-6）：
   ```
   psi = exp(zeta * U_member) / (exp(zeta * U_member) + exp(zeta * U_normal))
   ```

5. **决策**：
   - 若 `psi >= psi_th`：
     - 工人加入 `members` 集合。
     - 选择该工人可覆盖的所有会员任务，加入 `selected_tasks`。
     - 会费总收入 `total_fee += fee`。
   - 否则：
     - 工人加入 `normals` 集合。
     - 选择该工人可覆盖的所有普通任务，加入 `selected_tasks`。

### 4.3 统计结果
- 支付给工人的报酬总和 = 所有选中任务的 `task_price` 之和（每个任务只计一次）。
- 系统收益总和 = 所有选中任务的 `system_income` 之和。
- 平台效用 = 系统收益总和 + 会费总收入 - 报酬总和。
- 用户效用 = 所有工人获得的总报酬 - 所有工人完成任务的成本总和 - 会费总收入。

---

## 5. 参数说明
- `alpha`, `beta`：控制工人对历史报酬和平均报酬的依赖程度，推荐 `alpha=0.6, beta=0.4`。
- `fee`：固定会费，根据数据集预先确定（参考第6节）。
- `zeta`：差异敏感度，影响概率曲线的陡峭程度，推荐 `1`。
- `lambda`：损失厌恶系数，推荐 2.25（论文常用值）。
- `sigma`：价值函数曲率，推荐 0.88（论文常用值）。
- `psi_th`：概率阈值，默认 `0.5`，可根据需求调整。

---

## 6. 会费确定方法（基于定理3-4）
根据论文定理3-4，会费应满足：
\[
\overline{r - v} < \zeta^R < \overline{b - c}
\]
其中：
- \(\overline{r - v}\) = 所有任务的平均 `(task_price - system_income)`（下界）
- \(\overline{b - c}\) = 所有任务的平均 `(task_price - worker_cost)`（上界）

实际操作：
```python
# 从 task_classification 计算
lower = sum(t['task_price'] - t['system_income'] for t in task_class) / len(task_class)
upper = sum(t['task_price'] - t['worker_cost'] for t in task_class) / len(task_class)
fee = (lower + upper) / 2
```
若 `fee` 超出合理范围（如负数），可适当调整。

---

## 7. 示例（简化）
假设只有3个任务，分类为 `member`、`member`、`normal`，数据如下：
| task_id | task_price | worker_cost | system_income | type   |
|---------|------------|-------------|---------------|--------|
| t1      | 12         | 6           | 20            | member |
| t2      | 12         | 7           | 18            | member |
| t3      | 10         | 5           | 15            | normal |

参数：`alpha=0.6, beta=0.4, fee=10, zeta=1, lambda=2.25, sigma=0.88, psi_th=0.5`

初始化：
- `R_m = (12+12)/2 = 12`
- `R_n = 10`
- 工人A可覆盖 t1,t2，无普通任务 → `hist_reward_m=12, hist_reward_n=0`
- 工人B可覆盖 t3，无会员任务 → `hist_reward_m=0, hist_reward_n=10`

计算工人A：
- `b_m = 0.6*12+0.4*12=12`, `b_n = 0.6*0+0.4*10=4`
- 差值 `delta = beta*(R_m - R_n) = 0.4*(12-10)=0.8`
- 参照损失 `loss = lambda * delta^sigma = 2.25 * 0.8^0.88 ≈ 2.25 * 0.83 ≈ 1.8675`
- `cost_m = (6+7)/2=6.5`, `cost_n=0`
- `U_member = 12 + 1.8675 - 6.5 - 10 = -2.6325`
- `U_normal = 4 - 0 = 4`
- `psi = exp(-2.6325)/(exp(-2.6325)+exp(4)) ≈ 0.072 / (0.072+54.6) ≈ 0.00132 < 0.5` → 普通
- 选择普通任务：无 → 不添加任务。

工人B：
- `b_m = 0.6*0+0.4*12=4.8`, `b_n = 0.6*10+0.4*10=10`
- `delta = 0.8`, `loss ≈ 1.8675`
- `cost_m=0`, `cost_n=5`
- `U_member = 4.8 + 1.8675 - 0 - 10 = -3.3325`
- `U_normal = 10 - 5 = 5`
- `psi = exp(-3.3325)/(exp(-3.3325)+exp(5)) ≈ 0.0357/(0.0357+148.4) ≈ 0.00024 < 0.5` → 普通
- 选择普通任务：t3 → `selected_tasks` 加入 t3。

最终：
- `members = []`, `normals = [A,B]`
- `selected_tasks = [t3]`
- 会费收入 = 0
- 报酬总和 = 10
- 系统收益总和 = 15
- 平台效用 = 15 - 10 = 5
- 用户效用 = 10 - 5 = 5

---

## 8. 输出格式（JSON）
```json
{
  "members": [],
  "normals": ["A", "B"],
  "selected_tasks": ["t3"],
  "platform_utility": 5.0,
  "user_utility": 5.0
}
```

---

## 9. 后续集成
本算法作为单轮模块，可在UWR的每轮循环中调用。每轮结束后，需根据实际报酬更新工人的 `hist_reward_m`、`hist_reward_n` 以及全局 `R_m`、`R_n`，供下一轮使用。

---

## 10. 注意事项
- 若工人可覆盖的任务集为空，直接跳过该工人。
- 同一任务可能被多个工人选择，但为简化，每个任务只计入一次（去重）。实际中可根据需要调整（如允许多个工人完成同一任务，但会影响成本计算）。
- 会费 `fee` 在算法运行前确定，后续轮次保持不变。