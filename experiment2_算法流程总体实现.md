下面给你一版**最终可落地的“代码实现文档”**。
我按我们前面已经定下来的原则来写：

* **Step4 保持原 CMAB 主公式不变**
* **Step5 保持验证任务 + trust 更新不变**
* **Step6 引入 PGRD + LGSC**
* **会员只对 trusted 开放**
* **不让激励机制直接改坏覆盖逻辑**
* **PGRD 主要提升平台效益**
* **LGSC 主要提高会员留存率**

这版是“**代码设计文档**”，不是只讲理论，也不是直接贴完整代码，而是告诉你：

1. 应该新增哪些状态变量
2. 每轮流程怎么接
3. 公式如何落地
4. 输出哪些指标
5. 每张图记录什么、怎么记录

我会尽量和你当前 Step5 代码口径对齐。你现在的 Step5 已经具备：

* CMAB 招募
* 验证任务生成
* trust 更新
* malicious 排除
* 平台效用
* active workers / leave probability 统计。

---

# Step6：代码实现文档（最终版）

## CMAB + Trust + PGRD + LGSC

---

# 1. 总体目标

在你当前 Step5 系统基础上，继续解决：

> trusted workers 数量不足、trusted workers 长期参与不足、平台需要低成本长期留住可信工人。

因此 Step6 继续保留：

* Step4：CMAB 招募
* Step5：验证任务与 trust 更新

并新增：

* **PGRD：基于参照依赖的会员决策**
* **LGSC：基于沉没成本的长期留存机制**

---

# 2. 当前系统保留不动的部分

这些部分**不要改主逻辑**：

## 2.1 CMAB 招募

继续使用：

$$
\Delta_i(t)=\sum_{j\in S_i(t)} w_j \max\left(0,\hat q_i(t)-Q_j^{cur}(t)\right)
$$

$$
score_i(t)=\frac{\Delta_i(t)}{c_i}
$$

只排除 malicious 工人。
这部分你当前 Step5 已经写好了，不需要重构。

---

## 2.2 验证任务生成

继续保留：

* 先按 grid 聚合 trusted/unknown 重叠
* 再选 top-M grid
* 再映射到具体 task。

---

## 2.3 trust 更新

继续保留：

* 用 trusted 工人的 `task_data` 中位数作为参考
* unknown 和参考比较
* 分段更新 trust
* 重新划分 trusted / unknown / malicious。

---

## 2.4 平台效用与长期退出框架

继续保留：

* `platform_task_value`
* `platform_payment`
* `platform_utility`
* `leave_probability`
* `is_active`
* `active_workers`
* `left_workers`。

---

# 3. Step6 新增的核心思想

新增两部分：

## 3.1 PGRD

只对 trusted 工人开放会员资格。
trusted 工人比较：

* 成为会员后的预期净收益
* 不成为会员时的普通收益

如果会员方案更有吸引力，则更可能成为会员。
平台则通过收取会员费提高平台效益。

---

## 3.2 LGSC

会员用户在执行任务过程中不断累积“沉没值”。

* 达到阈值后得到奖励金
* 若中途退出，沉没值清零
* 提现后更新累计率，使下一轮更容易再得到奖励

从而提高会员留存率。

---

# 4. 新增状态变量设计

在你当前 `workers[worker_id]` 结构上新增以下字段。

---

## 4.1 会员状态

```python
"is_member": False
```

表示当前是否为会员。

---

## 4.2 会员概率

```python
"membership_probability": 0.0
```

表示本轮 PGRD 计算得到的会员参与概率。

---

## 4.3 会费累计

```python
"cumulative_membership_fee": 0.0
```

表示该工人累计缴纳的会员费。

---

## 4.4 沉没值

```python
"sunk_value": 0.0
```

表示当前周期的累计沉没值。

---

## 4.5 沉没累计率

```python
"sunk_rate": 1.0
```

初始累计率。

---

## 4.6 历史奖励提取次数

```python
"bonus_count": 0
```

表示已经领取过多少次会员奖励。

---

## 4.7 当前周期累计成本

```python
"period_cost_sum": 0.0
```

表示自上次领取奖励以来，本周期累计投入的任务成本。

---

## 4.8 累计会员奖励

```python
"cumulative_bonus": 0.0
```

表示历史领取奖励总额。

---

## 4.9 会员留存状态统计

```python
"member_rounds": 0
```

表示成为会员的累计轮数。

---

# 5. Step6 新增全局参数

建议新增以下配置参数：

```python
# ===== Step6: PGRD =====
MEMBERSHIP_FEE = 10.0
MEMBER_TASK_RATIO = 0.5
MEMBER_REWARD_MULTIPLIER = 1.25
NORMAL_REWARD_MULTIPLIER = 1.0
PGRD_LAMBDA = 1.5
PGRD_XI = 4.0
MEMBERSHIP_THRESHOLD = 0.55

# ===== Step6: LGSC =====
SUNK_THRESHOLD = 100.0
MEMBER_BONUS = 30.0
RHO_INIT = 1.0

# leave model extension
BETA3 = 0.5
BETA4 = 1.0
```

---

# 6. PGRD 代码实现逻辑

---

# 6.1 只对 trusted 开放会员决策

在每轮中，先从当前 active workers 中筛出：

```python
trusted_candidates = [
    worker for worker in available_workers
    if worker["category"] == "trusted"
]
```

unknown 和 malicious 不参与会员决策。

---

# 6.2 会员任务与普通任务划分

为了保留论文口径，可以仍然定义：

* member tasks
* normal tasks

但**建议这只用于收益计算，不直接用于改变任务可做权限**。

也就是说：

* 任务仍照常由 Step4/5 的招募逻辑选择
* 会员任务只在“收益估计”里使用

建议按权重或利润从高到低排序后，取前 `MEMBER_TASK_RATIO` 作为会员任务。

---

# 6.3 计算 (R_i^A(t)) 和 (R_i^B(t))

对于 trusted worker (i)：

设：

* (n_i^M(t))：本轮其能接触到的会员任务数
* (n_i^N(t))：本轮其能接触到的普通任务数
* (p_M(t))：会员任务平均报酬
* (p_N(t))：普通任务平均报酬
* (c_i^M(t))：会员任务平均成本
* (c_i^N(t))：普通任务平均成本

---

## 会员方案效用

$$
R_i^A(t)=n_i^M(t)\left(p_M(t)-c_i^M(t)\right)-f_i
$$

其中：

* $f_i = \mathrm{MEMBERSHIP\_FEE}$

---

## 普通方案效用

$$
R_i^B(t)=n_i^N(t)\left(p_N(t)-c_i^N(t)\right)
$$

---

# 6.4 参照损失

$$
L_i(t)=\max\left(0,\; R_i^A(t)-R_i^B(t)\right)
$$

---

# 6.5 会员概率

$$
\psi_i(t)=\frac{1}{1+\exp\left(-\xi\left(R_i^A(t)-R_i^B(t)+\lambda L_i(t)\right)\right)}
$$

代码里可写为：

```python
diff = R_A - R_B + PGRD_LAMBDA * loss
psi = 1.0 / (1.0 + math.exp(-PGRD_XI * diff))
```

---

# 6.6 会员决策

```python
is_member = psi >= MEMBERSHIP_THRESHOLD
```

若成为会员：

* `worker["is_member"] = True`
* `worker["membership_probability"] = psi`
* `worker["cumulative_membership_fee"] += MEMBERSHIP_FEE`

否则：

* `worker["is_member"] = False`

---

# 6.7 平台会费收益

每轮新增：

```python
membership_fee_income_t
```

计算为：

```python
membership_fee_income_t = sum(
    MEMBERSHIP_FEE for worker in trusted_candidates if worker["is_member"]
)
```

平台总收益改为：

$$
platform\_utility_t = platform\_task\_value_t + membership\_fee\_income_t - payment_t - bonus\_payment_t
$$

注意：

* `bonus_payment_t` 是 LGSC 奖励支出
* 会费是平台收益
* 奖励金是平台额外成本

---

# 7. LGSC 代码实现逻辑

---

# 7.1 只有会员会累积沉没值

对每个：

```python
worker["is_member"] == True
```

的工人，在其本轮执行了任务时，累积沉没值。

---

# 7.2 沉没值更新

设该工人本轮完成任务集合为 $\mathcal{K}_i(t)$，任务成本为 $c_{ij}(t)$，则：

$$
S_i(t+1)=S_i(t)+\rho_i(t)\sum_{j\in \mathcal{K}_i(t)} c_{ij}(t)
$$

代码中：

```python
round_cost_sum = sum(task_costs_of_this_worker)
worker["sunk_value"] += worker["sunk_rate"] * round_cost_sum
worker["period_cost_sum"] += round_cost_sum
```

---

# 7.3 奖励触发

若：

```python
worker["sunk_value"] >= SUNK_THRESHOLD
```

则：

* `bonus = MEMBER_BONUS`
* `worker["cumulative_bonus"] += bonus`
* `worker["bonus_count"] += 1`
* `worker["sunk_value"] = 0.0`

并记录：

```python
bonus_payment_t += MEMBER_BONUS
```

---

# 7.4 累计率更新

领取奖励后，更新：

$$
\rho_i(t+1)=1+\frac{\Theta_i\cdot G_i(t)}{\Theta_i\cdot G_i(t)+C_i^{last}}
$$

代码里可写为：

```python
bonus = MEMBER_BONUS
G_i = worker["bonus_count"]
C_last = max(worker["period_cost_sum"], 1e-8)

worker["sunk_rate"] = 1.0 + (bonus * G_i) / (bonus * G_i + C_last)
worker["period_cost_sum"] = 0.0
```

---

# 7.5 未达阈值时的沉没损失

$$
H_i(t)=\frac{\Theta_i}{Y}S_i(t)
$$

这个值主要用于解释留存逻辑，可不必单独进入收益发放，但建议记录：

```python
worker["current_sunk_loss"] = MEMBER_BONUS / SUNK_THRESHOLD * worker["sunk_value"]
```

便于后续分析。

---

# 8. 退出概率如何扩展

你当前 Step5 已有：

$$
P_i^{leave}(t)=\sigma\left(\beta_0+\beta_1 C_i(t)-\beta_2 R_i(t)\right)
$$

现在扩展为：

$$
P_i^{leave}(t)=\sigma\left(\beta_0+\beta_1 C_i(t)-\beta_2 R_i(t)-\beta_3 m_i(t)-\beta_4 \frac{S_i(t)}{Y}\right)
$$

其中：

* (m_i(t))：会员状态
* (S_i(t)/Y)：沉没进度

代码里：

```python
leave_probability = sigmoid(
    BETA0
    + BETA1 * cumulative_cost
    - BETA2 * avg_reward
    - BETA3 * int(worker["is_member"])
    - BETA4 * (worker["sunk_value"] / SUNK_THRESHOLD)
)
```

这意味着：

* 会员更不容易走
* 沉没值越高越不容易走

这正对应：

> **LGSC 提高会员留存率**

---

# 9. 每轮完整流程（最终代码流程）

建议你最终每轮顺序为：

---

## Step A：读取本轮任务与可用工人

* `round_tasks`
* `available_workers`

---

## Step B：执行 Step4 的 CMAB 招募

得到：

* `selected_worker_ids`
* `selection_details`

---

## Step C：评价业务任务结果

得到：

* `coverage_rate`
* `completion_rate`
* `avg_quality`
* `weighted_completion_quality`
* `platform_task_value`

---

## Step D：执行 Step5 验证任务

* `validation_tasks`
* `trust_update_records`
* 重建 `Uc/Uu/Um`

---

## Step E：执行 Step6 的 PGRD 会员决策

对 trusted workers 计算：

* `R_A`
* `R_B`
* `loss`
* `membership_probability`
* `is_member`

并计算：

* `membership_fee_income_t`

---

## Step F：执行 Step6 的 LGSC 沉没值更新与奖励发放

对会员工人：

* 累积 `sunk_value`
* 若达阈值则发 `MEMBER_BONUS`
* 更新 `sunk_rate`

并统计：

* `bonus_payment_t`

---

## Step G：更新收益/成本/退出状态

* `update_worker_reward_cost(...)`
* 更新 leave probability
* 更新 active_workers / left_workers

---

## Step H：更新累计指标并写 round_result

---

# 10. round_result 需要新增的字段

在你现在 Step5 的 `round_result` 基础上，新增这些字段。

---

## 10.1 PGRD 相关字段

```python
"membership_fee_income": ...
"member_count": ...
"trusted_member_count": ...
"member_worker_ids": [...]
"membership_records": [...]
```

其中 `membership_records` 每个工人建议记录：

```python
{
    "worker_id": ...,
    "R_A": ...,
    "R_B": ...,
    "reference_loss": ...,
    "membership_probability": ...,
    "is_member": ...
}
```

---

## 10.2 LGSC 相关字段

```python
"bonus_payment": ...
"bonus_trigger_count": ...
"avg_sunk_value": ...
"avg_sunk_rate": ...
"member_retention_proxy": ...
```

---

## 10.3 扩展平台效用字段

```python
"platform_task_value": ...
"platform_payment": ...
"membership_fee_income": ...
"bonus_payment": ...
"platform_utility": ...
```

其中：

$$
platform\_utility_t = platform\_task\_value_t + membership\_fee\_income_t - platform\_payment_t - bonus\_payment_t
$$

---

# 11. summary 需要新增的字段

在 `summary.json` 中新增：

```python
"avg_membership_fee_income_all_non_empty"
"avg_bonus_payment_all_non_empty"
"avg_member_count_all_non_empty"
"avg_trusted_member_count_all_non_empty"
"avg_avg_sunk_value_all_non_empty"
"avg_avg_sunk_rate_all_non_empty"

"final_cumulative_membership_fee_income"
"final_cumulative_bonus_payment"
"final_cumulative_platform_utility"
"final_member_count"
"final_trusted_member_count"
```

---

# 12. 建议输出的图（以及每张图记录什么）

下面是你要求的“每张图记录什么、怎么记录”。

---

## 12.1 `coverage_rate`

### 文件

`experiment2_cmab_trust_pgrd_lgsc_coverage_rate.png`

### 含义

本轮被至少一名工人执行的任务比例。

### 记录逻辑

从 `task_results` 中统计 `covered=True` 的任务数，再除以 `num_tasks`。

---

## 12.2 `completion_rate`

### 文件

`..._completion_rate.png`

### 含义

本轮满足：

* 人数达到 `required_workers`
* 平均质量达到 `DELTA`

的任务比例。

### 记录逻辑

从 `task_results` 中统计 `completed=True` 的任务数，再除以 `num_tasks`。

---

## 12.3 `avg_quality`

### 文件

`..._avg_quality.png`

### 含义

本轮所有被覆盖任务的平均最终质量。

### 记录逻辑

对 `covered=True` 的任务，取 `best_quality` 后求平均。

---

## 12.4 `cumulative_coverage_rate`

### 文件

`..._cumulative_coverage_rate.png`

### 含义

截至当前轮，累计覆盖率。

### 记录逻辑

累计 `num_covered / num_tasks`。

---

## 12.5 `cumulative_completion_rate`

### 文件

`..._cumulative_completion_rate.png`

### 含义

截至当前轮，累计完成率。

### 记录逻辑

累计 `num_completed / num_tasks`。

---

## 12.6 `cumulative_avg_quality`

### 文件

`..._cumulative_avg_quality.png`

### 含义

截至当前轮，所有被覆盖任务的累计平均质量。

### 记录逻辑

累计 covered task 的 `best_quality` 后求平均。

---

## 12.7 `platform_utility`

### 文件

`..._platform_utility.png`

### 含义

平台本轮净收益。

### 记录逻辑

[
platform_task_value

* membership_fee_income

- payment
- bonus_payment
  ]

---

## 12.8 `cumulative_platform_utility`

### 文件

`..._cumulative_platform_utility.png`

### 含义

截至当前轮累计净收益。

### 记录逻辑

逐轮累加 `platform_utility`。

---

## 12.9 `trusted_count`

### 文件

`..._trusted_count.png`

### 含义

本轮结束后 trusted 工人数。

### 记录逻辑

遍历 workers，统计 `category == "trusted"`。

---

## 12.10 `malicious_count`

### 文件

`..._malicious_count.png`

### 含义

本轮结束后 malicious 工人数。

### 记录逻辑

遍历 workers，统计 `category == "malicious"`。

---

## 12.11 `avg_trust`

### 文件

`..._avg_trust.png`

### 含义

所有工人的平均 trust。

### 记录逻辑

对全部 workers 的 `trust` 求平均。

---

## 12.12 `member_count`

### 文件

`..._member_count.png`

### 含义

本轮会员总人数。

### 记录逻辑

统计 `is_member=True` 的工人数。

---

## 12.13 `trusted_member_count`

### 文件

`..._trusted_member_count.png`

### 含义

本轮 trusted 且是会员的人数。

### 记录逻辑

统计：

```python
worker["category"] == "trusted" and worker["is_member"] == True
```

---

## 12.14 `membership_fee_income`

### 文件

`..._membership_fee_income.png`

### 含义

本轮平台从会员费获得的收益。

### 记录逻辑

统计所有本轮新成为会员或本轮被收取会费的 trusted worker 对应的 `MEMBERSHIP_FEE` 总和。

---

## 12.15 `bonus_payment`

### 文件

`..._bonus_payment.png`

### 含义

本轮平台发放给会员的奖励金总额。

### 记录逻辑

统计本轮达到 `SUNK_THRESHOLD` 并成功领取 `MEMBER_BONUS` 的会员总奖励。

---

## 12.16 `avg_sunk_value`

### 文件

`..._avg_sunk_value.png`

### 含义

当前所有会员的平均沉没值。

### 记录逻辑

对 `is_member=True` 的 workers 的 `sunk_value` 求平均。

---

## 12.17 `avg_sunk_rate`

### 文件

`..._avg_sunk_rate.png`

### 含义

当前所有会员的平均沉没累计率。

### 记录逻辑

对 `is_member=True` 的 workers 的 `sunk_rate` 求平均。

---

## 12.18 `num_active_workers`

### 文件

`..._active_workers.png`

### 含义

本轮结束后系统中仍未退出的平台工人数。

### 记录逻辑

统计 `is_active=True` 的工人数。

---

## 12.19 `cumulative_left_workers`

### 文件

`..._left_workers.png`

### 含义

截至当前轮累计退出的工人数。

### 记录逻辑

统计 `is_active=False` 的工人数。

---

## 12.20 `avg_leave_probability`

### 文件

`..._avg_leave_probability.png`

### 含义

本轮所有 active workers 的平均退出概率。

### 记录逻辑

对当前 active workers 的 `leave_probability` 求平均。

---

# 13. 最终判断：方案是否可实现

我帮你按当前代码体系检查后的结论是：

## 可以实现，而且路径很清楚

原因是：

* Step5 已经有 `workers` 全量状态字典。
* 已经有平台收益、工人成本、退出概率框架。
* 只需要新增会员和沉没值状态，不需要重写 Step4/5 主体。
* PGRD 和 LGSC 都可以作为“每轮后处理模块”插进现有主循环。

---

# 14. 最终一句话总结

> 这套最终方案保持 Step4 的 CMAB 招募和 Step5 的 trust 验证不变，在此基础上通过 PGRD 提升平台效益、通过 LGSC 提高 trusted 会员留存率，并通过新增 membership、sunk value、bonus 和扩展 platform utility 等指标完成完整实现。

如果你看这版顺了，下一步我就直接给你写 **Step6 完整 Python 代码**。
