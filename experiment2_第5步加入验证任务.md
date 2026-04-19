我先说判断：

## 这版 Step5 代码整体是对的，主线已经成型了

你现在这版代码已经把这几层接上了：

* Step4 的 CMAB 招募
* 验证任务生成
* trust 更新
* 恶意工人排除
* 长期退出模型
* 平台效用统计

整体结构是顺的。

但我建议你注意 **两个“逻辑口径”问题**，不一定非要改代码，但文档里必须写清楚，不然以后你会再混。

---

# 我先帮你看代码：哪里对，哪里要注意

## 这几部分是对的

### 1. 工人初始化逻辑是对的

你现在让平台初始只知道 trusted，其余 unknown 和 malicious 都先当 unknown，这很合理。

### 2. 第5步仍沿用 Step4 的 CMAB 招募

你没有改掉第4步主体，而是在其上叠加 trust，这个方向是对的。

### 3. malicious 被排除出后续招募

这正是第5步的核心作用之一。

### 4. 先按 grid 选验证任务，再固定到具体 task

这个比直接乱选任务更稳定，也更符合你最开始“空间一致性验证”的思路。

### 5. trust 更新后再重建 Uc/Uu/Um

这一步是对的，说明你的分类是动态变化的，不是死的。

---

## 这两个点你要特别注意

### 问题1：你现在的验证任务，是按 `available_workers` 做的，不是按 `selected_workers` 做的

你在这两处都用了 `available_workers`：

* `generate_validation_tasks_by_grid(...)`
* `update_trust_by_validation(...)`

也就是说：

> 只要这个工人在该 slot 可用，即使这一轮没有被 CMAB 选中，它也可能被拿来参与验证任务统计。

这会带来一个口径问题：

#### 你现在代码的真实含义是

“验证任务”不是只给本轮被招募工人，而是对本轮可用工人做验证。

#### 如果这是你想要的

可以不改，但文档必须写成：

> 验证阶段面向本轮可用工人，而非仅限于本轮被招募工人。

#### 如果你原本想要的是

> 只有被 CMAB 选中的工人才执行验证任务

那这里就要改成 `selected_worker_ids` 口径。

---

### 问题2：退出判定仍然对所有 active workers 生效

你现在 `update_worker_leave_state()` 是对所有 `is_active=True` 的工人做退出判定，不区分本轮是否被选中。

#### 这代表什么？

表示：

> 工人即使本轮没被平台选中，也可能因为长期收益差或平台吸引力不够而离开。

#### 这个逻辑并不是错

但它对应的是“平台级流失”，不是“执行任务后的疲劳流失”。

所以文档里也要写清楚。

---

# 总体判断

## 这版代码可以继续往下用

不需要推翻。

## 但你必须在文档里把下面两件事讲清楚

1. 验证任务到底面向谁
2. 退出机制到底是“平台级退出”还是“任务执行后退出”

只要这两点写清楚，这版代码是能成立的。

---

# 下面我直接给你一版完整文档

我按你**现在这版代码真实逻辑**来写，不强行改成别的版本。

---

# 第5步：基于验证任务的动态信任更新机制（完整文档）

## 1. 本步骤目标

在 Step4 中，平台已经能够通过 CMAB 在预算约束下动态招募工人，但该方法仍存在一个关键问题：

> 平台只能根据历史质量表现学习“谁看起来表现好”，却无法判断“这个工人的数据是否可信”。

因此，第5步引入验证任务与动态信任更新机制，目标是：

* 利用 trusted 工人作为参考锚点；
* 对 unknown 工人进行一致性验证；
* 动态更新工人 trust；
* 识别并剔除 malicious 工人；
* 防止后续 CMAB 持续招募不可信工人。

---

## 2. 输入与输出

### 2.1 输入

本步骤输入文件为：

* `experiment2_worker_options.json`

文件中每个工人包含：

* `worker_id`
* `bid_price`
* `base_quality`
* `init_category`
* `available_slots`
* `tasks`

  * `task_id`
  * `slot_id`
  * `region_id`
  * `required_workers`
  * `weight`
  * `quality`
  * `task_data`
  * `true_value`

其中：

* `quality`：工人执行任务的实际完成质量
* `task_data`：工人实际上报的数据值
* `true_value`：任务的真实参考值（由 Step3 生成）

---

### 2.2 输出

本步骤输出：

#### 结果文件

* `experiment2_cmab_trust_round_results.json`
* `experiment2_cmab_trust_summary.json`

#### 图像文件

* `experiment2_cmab_trust_coverage_rate.png`
* `experiment2_cmab_trust_completion_rate.png`
* `experiment2_cmab_trust_avg_quality.png`
* `experiment2_cmab_trust_cumulative_coverage_rate.png`
* `experiment2_cmab_trust_cumulative_completion_rate.png`
* `experiment2_cmab_trust_cumulative_avg_quality.png`
* `experiment2_cmab_trust_trusted_count.png`
* `experiment2_cmab_trust_unknown_count.png`
* `experiment2_cmab_trust_malicious_count.png`
* `experiment2_cmab_trust_validation_count.png`
* `experiment2_cmab_trust_avg_trust.png`
* `experiment2_cmab_trust_platform_utility.png`
* `experiment2_cmab_trust_cumulative_platform_utility.png`
* `experiment2_cmab_trust_active_workers.png`
* `experiment2_cmab_trust_left_workers.png`
* `experiment2_cmab_trust_avg_leave_probability.png`

---

## 3. 工人集合定义

平台动态维护三类工人集合：

* (U_c)：trusted 工人
* (U_u)：unknown 工人
* (U_m)：malicious 工人

初始化时：

* 若 `init_category == trusted`，则平台初始将其记为 trusted
* 其余工人（包括真实 unknown 和真实 malicious）初始都视为 unknown

也就是说，平台最开始并不知道谁是恶意工人。

---

## 4. trust 定义与初始化

每个工人维护一个动态信任度：

[
trust_i \in [0,1]
]

初始值为：

* trusted：`1.0`
* unknown：`0.5`

并根据阈值更新工人类别：

* 若 (trust_i \ge \theta_{high})，则归为 trusted
* 若 (trust_i \le \theta_{low})，则归为 malicious
* 否则保持 unknown

代码中参数为：

* `THETA_HIGH = 0.8`
* `THETA_LOW = 0.2` 

---

## 5. 与 Step4 的关系

第5步并没有推翻 Step4，而是在 Step4 的 CMAB 招募基础上叠加 trust 机制。

### Step4 负责

* 在预算约束下招募高边际收益工人

### Step5 负责

* 检查这些工人（以及当前可用工人）是否可信
* 更新 trust
* 将恶意工人排除出后续 CMAB 候选池

因此：

> Step4 解决“谁值得招”，Step5 解决“谁值得信”。

---

## 6. 每轮整体流程

每轮 (t) 的流程如下：

### Step A：读取本轮任务与可用工人

* 当前 slot 的任务集合 `round_tasks`
* 当前 slot 中 `available_slots` 包含该 slot 且 `is_active=True` 的工人

### Step B：CMAB 招募

使用 Step4 的论文风格 CMAB 继续招募，但排除已经被识别为 malicious 的工人。

### Step C：评价业务任务结果

统计：

* coverage_rate
* completion_rate
* avg_quality
* weighted_completion_quality
* platform_utility

### Step D：生成验证任务

在本轮可用工人中，先按 grid 统计 trusted 与 unknown 的空间重叠，再从 top-M grid 中选出验证任务。

### Step E：执行验证并更新 trust

对验证任务中同时覆盖 trusted 与 unknown 的工人，比较 unknown 的 `task_data` 与 trusted 参考值之间的误差，并更新 trust。

### Step F：更新工人类别

根据 trust 阈值，将工人重新归类为 trusted、unknown 或 malicious。

### Step G：更新长期运行状态

更新：

* 累计收益
* 累计成本
* 退出概率
* active_workers
* left_workers

---

## 7. CMAB 招募逻辑

本步骤仍使用 Step4 的招募评分：

[
\Delta_i(t)=\sum_{j\in S_i(t)} w_j \cdot \max(0,\hat q_i(t)-Q_j^{cur}(t))
]

[
score_i(t)=\frac{\Delta_i(t)}{c_i}
]

其中：

* (\hat q_i(t))：工人的 UCB 预测质量
* (Q_j^{cur}(t))：当前任务 j 已达到的预测质量
* (w_j)：任务权重
* (c_i)：工人报价

与 Step4 唯一不同的是：

> 当前类别为 malicious 的工人不再参与招募。

---

## 8. 验证任务生成机制

### 8.1 核心思想

只有同时存在：

* trusted 工人
* unknown 工人

的 grid，才有验证价值。

### 8.2 grid 统计

对于本轮每个 grid，统计：

* `trusted_count`
* `unknown_count`

若该 grid 满足：

* trusted_count > 0
* unknown_count > 0

则作为候选验证 grid。

### 8.3 排序与选择

候选 grid 按以下顺序排序：

1. unknown_count 降序
2. trusted_count 降序
3. grid_id 升序

然后取前 `VALIDATION_TOP_M` 个 grid。代码里：

* `VALIDATION_TOP_M = 5` 

### 8.4 具体验证任务

在每个被选中的 grid 中，固定取 task_id 最小的任务作为验证任务。

---

## 9. trust 更新机制

### 9.1 trusted 参考值

对于某个验证任务 (v)，先取该任务上所有 trusted 工人的 `task_data`，并计算其中位数作为参考值：

[
base_v = median(data_i, i\in trusted)
]

### 9.2 unknown 工人误差

对于执行该验证任务的 unknown 工人 (i)，其误差为：

若 (base_v\approx 0)：

[
error_{iv}=|data_i-base_v|
]

否则：

[
error_{iv}=\frac{|data_i-base_v|}{|base_v|}
]

### 9.3 分段更新

代码中采用分段规则：

* 若 `error <= ERROR_GOOD`，trust 增加 `ETA`
* 若 `ERROR_GOOD < error <= ERROR_BAD`，trust 不变
* 若 `error > ERROR_BAD`，trust 减少 `ETA`

参数为：

* `ETA = 0.10`
* `ERROR_GOOD = 0.15`
* `ERROR_BAD = 0.35` 

### 9.4 trust 截断

更新后将 trust 截断到 ([0,1])。

---

## 10. 平台效用与长期退出机制

本步骤仍保留长期运行模型。

### 10.1 平台单轮收益

平台收益定义为：

[
platform_task_value_t = \sum_j \rho \cdot w_j \cdot best_quality_j
]

[
platform_payment_t = \sum_i bid_i
]

[
platform_utility_t = platform_task_value_t - platform_payment_t
]

代码中：

* `RHO = 10.0` 

---

### 10.2 工人累计收益与成本

对被选中工人：

* 本轮报酬 = `bid_price`
* 本轮真实成本 = `WORKER_COST_RATIO * bid_price`

其中：

* `WORKER_COST_RATIO = 0.6` 

---

### 10.3 退出概率

每轮对所有当前活跃工人计算：

[
P_i^{leave} = \sigma(\beta_0 + \beta_1 \cdot cumulative_cost_i - \beta_2 \cdot avg_reward_i)
]

其中：

* `BETA0 = -2.5`
* `BETA1 = 0.02`
* `BETA2 = 0.3` 

然后对每个 active worker 做 Bernoulli 退出判定。

---

## 11. 输出统计量说明

下面把你代码里记录和画图的量全部写清楚。

---

# 11.1 `coverage_rate`

### 含义

本轮至少被 1 个工人执行的任务比例。

### 计算方式

对本轮每个任务，若 `num_workers > 0`，则记为 covered。

[
coverage_rate_t = \frac{num_covered_t}{num_tasks_t}
]

### 图

* `experiment2_cmab_trust_coverage_rate.png`

### 记录逻辑

它记录的是本轮“有没有人做”，不要求完成，也不要求 trust 达标。

---

# 11.2 `completion_rate`

### 含义

本轮满足完成条件的任务比例。

### 完成条件

* 执行人数达到 `required_workers`
* 平均质量 `avg_quality >= DELTA`

[
completion_rate_t = \frac{num_completed_t}{num_tasks_t}
]

### 图

* `experiment2_cmab_trust_completion_rate.png`

### 记录逻辑

它记录的是“最终算不算完成”，比 coverage 更严格。

---

# 11.3 `avg_quality`

### 含义

本轮所有被覆盖任务的平均最终质量。

### 计算方式

先对每个被覆盖任务取：

[
best_quality_j = \max(q_{ij})
]

再在所有 covered tasks 上求平均。

### 图

* `experiment2_cmab_trust_avg_quality.png`

### 记录逻辑

它衡量的是本轮任务结果整体质量水平。

---

# 11.4 `cumulative_coverage_rate`

### 含义

从第1轮到当前轮累计的覆盖率。

### 计算方式

[
cumulative_coverage_rate_t=
\frac{\sum_{\tau=1}^{t} num_covered_{\tau}}
{\sum_{\tau=1}^{t} num_tasks_{\tau}}
]

### 图

* `experiment2_cmab_trust_cumulative_coverage_rate.png`

### 记录逻辑

反映长期平均覆盖能力。

---

# 11.5 `cumulative_completion_rate`

### 含义

从第1轮到当前轮累计的完成率。

### 图

* `experiment2_cmab_trust_cumulative_completion_rate.png`

### 记录逻辑

反映长期平均完成能力。

---

# 11.6 `cumulative_avg_quality`

### 含义

从第1轮到当前轮，所有被覆盖任务的累计平均最终质量。

### 图

* `experiment2_cmab_trust_cumulative_avg_quality.png`

### 记录逻辑

反映系统长期平均质量水平，而不是单轮波动。

---

# 11.7 `trusted_count`

### 含义

本轮结束后，类别为 trusted 的工人数。

### 图

* `experiment2_cmab_trust_trusted_count.png`

### 记录逻辑

反映 trust 机制是否逐渐识别并积累可信工人。

---

# 11.8 `unknown_count`

### 含义

本轮结束后，类别为 unknown 的工人数。

### 图

* `experiment2_cmab_trust_unknown_count.png`

### 记录逻辑

反映尚未被明确识别的中间工人数量。

---

# 11.9 `malicious_count`

### 含义

本轮结束后，类别为 malicious 的工人数。

### 图

* `experiment2_cmab_trust_malicious_count.png`

### 记录逻辑

反映被系统识别并拉黑的恶意工人数量。

---

# 11.10 `num_validation_tasks`

### 含义

本轮生成并执行的验证任务数量。

### 图

* `experiment2_cmab_trust_validation_count.png`

### 记录逻辑

表示本轮 trust 验证强度。

---

# 11.11 `avg_trust`

### 含义

所有工人当前 trust 的平均值。

### 图

* `experiment2_cmab_trust_avg_trust.png`

### 记录逻辑

反映整体工人群体在系统视角下的平均可信水平。

---

# 11.12 `platform_utility`

### 含义

平台本轮净收益。

### 计算方式

[
platform_utility_t = platform_task_value_t - platform_payment_t
]

### 图

* `experiment2_cmab_trust_platform_utility.png`

### 记录逻辑

记录平台当前轮是否盈利，以及盈利幅度。

---

# 11.13 `cumulative_platform_utility`

### 含义

从第1轮到当前轮累计的平台净收益。

### 图

* `experiment2_cmab_trust_cumulative_platform_utility.png`

### 记录逻辑

用于判断平台长期运行是否可持续。

---

# 11.14 `num_active_workers`

### 含义

当前轮结束后，仍未退出平台的 active workers 数量。

### 图

* `experiment2_cmab_trust_active_workers.png`

### 记录逻辑

反映平台劳动力池剩余规模。

---

# 11.15 `cumulative_left_workers`

### 含义

到当前轮为止，累计退出的工人数。

### 图

* `experiment2_cmab_trust_left_workers.png`

### 记录逻辑

反映平台长期流失规模。

---

# 11.16 `avg_leave_probability`

### 含义

本轮所有 active workers 的平均退出概率。

### 图

* `experiment2_cmab_trust_avg_leave_probability.png`

### 记录逻辑

表示当前轮整体流失风险大小。

---

## 12. 结果文件字段说明

### 12.1 `round_results.json`

每轮都会记录：

* 招募结果
* 任务统计
* 验证任务
* trust 更新
* 工人类别分布
* 平台效用
* 退出信息
* 累计指标

### 12.2 `summary.json`

整体汇总：

* 所有单轮指标平均值
* 最终累计指标
* 最终活跃工人数与退出工人数

---

## 13. 本步骤的真实作用

这一阶段最核心的作用不是直接改招募公式，而是：

> 通过验证任务修正工人集合，使 CMAB 后续学习不再持续被恶意工人污染。

因此本步骤的意义在于：

* 提高后续招募质量
* 提高系统整体完成质量
* 提升数据可信性
* 减少恶意工人长期干扰

---

## 14. 一句话总结

> Step5 在 Step4 的 CMAB 招募基础上，通过验证任务与 trust 更新识别并排除恶意工人，从而提高后续任务执行质量、系统完成效果和平台长期可持续性。

---

如果你愿意，我下一步可以继续帮你把这份文档整理成**更像论文格式的最终版**，包括“参数表”和“符号表”。
