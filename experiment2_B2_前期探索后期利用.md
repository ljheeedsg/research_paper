# 第4步-B2：ε-First 招募机制（完整文档，可直接用于论文实验说明）

---

# 1. 目标

本步骤构建 **B2：ε-First Exploration-Exploitation 招募机制**，作为随机招募（B1）与纯 CMAB 招募（B3）之间的中间对比策略。

其核心思想是：

> 平台先用前期轮次进行随机探索，收集工人历史质量信息；
> 随后进入利用阶段，优先选择历史表现好的工人。

该方法不采用 UCB 持续探索机制，而是使用“先探索、后利用”的经典两阶段思想，因此适合作为本文 CMAB 方法的重要对照组。

---

# 2. 为什么要设置 B2

如果实验中只有：

* B1 随机招募
* B3 纯 CMAB

审稿人可能会提出问题：

> 为什么一定要用 CMAB？
> 一个简单的“先随机探索，再按历史质量选人”方法是否也能达到类似效果？

因此加入 B2 非常有价值。

它能证明：

### 若 B3 优于 B2，则说明：

> 持续在线学习（CMAB）优于一次性探索策略。

这会显著增强论文说服力。

---

# 3. 输入数据

与 B3 完全一致，输入文件为：

```text
experiment2_worker_options.json
```

每位工人包含：

* worker_id
* bid_price
* init_category
* base_quality
* available_slots
* tasks

每个任务包含：

* task_id
* slot_id
* region_id
* required_workers
* weight
* quality
* task_data

---

# 4. 输出文件

建议输出：

```text
experiment2_epsilon_first_longrun_round_results.json
experiment2_epsilon_first_longrun_summary.json
experiment2_epsilon_first_longrun_round_results_all_runs.json
```

图像输出与 B3 保持一致：

```text
coverage_rate
completion_rate
avg_quality
platform_utility
active_workers
left_workers
avg_leave_probability
```

以及累计指标图。

---

# 5. 核心思想

ε-First 方法分为两个阶段：

---

## 第一阶段：探索阶段（Explore）

平台前期随机选择工人，目的不是最优收益，而是学习：

* 哪些工人质量高；
* 哪些工人稳定；
* 哪些工人任务覆盖能力强。

---

## 第二阶段：利用阶段（Exploit）

当探索结束后，平台不再随机，而是根据历史平均质量优先选择工人。

---

## 整体流程

```text
探索阶段随机选人
→ 累积工人历史质量
→ 进入利用阶段
→ 优先选择高质量低成本工人
→ 长期运行
```

---

# 6. 参数设置（建议）

除基础参数外，新增：

---

## 探索比例

```python
EPSILON_FIRST_RATIO = 0.2
```

表示前 20% 轮次用于探索。

若一天共：

$$
H=144
$$

轮，则探索轮数：

$$
H_e=0.2\times144=29
$$

即前 29 轮随机探索。

---

## 基础参数与 B3 保持一致

```python
PER_ROUND_BUDGET = 1000
K = 7
DELTA = 0.45
RHO = 10
BETA0 = -0.5
BETA1 = 0.02
BETA2 = 0.3
```

---

# 7. 平台可见与不可见信息

---

## 平台可见

第 (t) 轮平台可观察：

* 工人报价 (c_i)
* 当前可做任务集合 (S_i(t))
* 历史观测次数 (n_i)
* 历史平均质量 (\bar q_i)

---

## 平台不可见

平台不知道：

* base_quality
* 工人真实类别

因此仍属于未知工人招募问题。

---

# 8. 第一阶段：探索阶段

若当前轮次满足：

$$
t\le H_e
$$

则平台采用随机招募。

即：

在预算约束与人数上限 (K) 下，从当前在线工人中随机选择工人。

---

## 目的

不是追求收益最大化，而是获取样本数据：

* 被选工人的真实执行质量；
* 被选工人的任务完成表现。

这些信息将用于后续利用阶段。

---

# 9. 历史质量更新

若工人 (i) 在某轮被选中，并完成若干任务，其任务质量集合为：

$$
{q_{ij}}
$$

则更新：

### 观测次数

$$
n_i \leftarrow n_i + m_i
$$

其中 (m_i) 为本轮完成任务数。

### 平均质量

$$
\bar q_i=
\frac{n_i^{old}\bar q_i^{old}+\sum q_{ij}}
{n_i}
$$

---

# 10. 第二阶段：利用阶段

若：

$$
t>H_e
$$

平台进入利用阶段。

此时不再随机，而是依据历史质量选择工人。

---

# 11. 工人质量估计

B2 不使用 UCB 探索项，仅使用经验平均质量：

$$
\hat q_i(t)=
\begin{cases}
0, & n_i=0[8pt]
\bar q_i, & n_i>0
\end{cases}
$$

含义：

* 已观察工人按历史质量评价；
* 未观察工人默认不给高分。

这与 B3 的乐观探索机制形成明显区别。

---

# 12. 单轮招募目标

设任务集合为：

$$
T_t
$$

任务当前最好质量为：

$$
Q_j^{cur}(t)
$$

若加入工人 (i)，边际收益：

$$
\Delta_i(t)=
\sum_{j\in S_i(t)}
w_j\max(0,\hat q_i(t)-Q_j^{cur}(t))
$$

工人得分：

$$
score_i(t)=\frac{\Delta_i(t)}{c_i}
$$

平台选择：

$$
argmax(score_i(t))
$$

---

# 13. 终止条件

直到满足任一条件：

* 达到最大人数 (K)
* 预算耗尽
* 无正收益工人

---

# 14. 单轮任务评价

与 B3 完全一致。

---

## 覆盖率

$$
Coverage=
\frac{#covered}{#tasks}
$$

---

## 完成率

满足：

* 工人数达标
* 平均质量 ≥ DELTA

则任务完成。

$$
Completion=
\frac{#completed}{#tasks}
$$

---

## 平均质量

仅对被覆盖任务统计。

---

# 15. 平台收益模型

任务收益：

$$
value_j=
RHO\cdot w_j\cdot best_quality_j
$$

平台总收益：

$$
TaskValue_t=\sum value_j
$$

平台支付：

$$
Payment_t=\sum c_i
$$

平台效用：

$$
Utility_t=
TaskValue_t-Payment_t
$$

---

# 16. 长期退出机制

与 B3 保持一致：

$$
p_i^{leave}=
sigmoid(BETA0+BETA1C_i-BETA2R_i)
$$

其中：

* (C_i)：累计成本
* (R_i)：平均收益

若触发退出，则：

```text
is_active = False
```

永久离开系统。

---

# 17. 为什么 B2 会弱于 B3（理论解释）

因为 B2 有两个天然缺陷：

---

## 缺陷1：探索结束后不再学习

若后期出现新工人或环境变化，B2 无法继续探索。

---

## 缺陷2：前期探索可能浪费轮次

随机探索期间可能选择低质量工人。

---

## 而 B3（CMAB）优势是：

> 每一轮都动态平衡探索与利用。

因此理论上：

$$
B3 \ge B2 \ge B1
$$

（通常成立）

---

# 18. 在论文中的实验作用

B2 是非常关键的桥梁组。

若实验结果显示：

* B2 明显优于 B1
* B3 明显优于 B2

则说明：

### 第一层结论：

学习机制优于纯随机。

### 第二层结论：

持续在线学习优于一次性探索学习。

这会让论文逻辑非常完整。

---

# 19. 建议展示指标

主图建议：

```text
coverage_rate
completion_rate
avg_quality
platform_utility
active_workers
```

累计图：

```text
cumulative_completion_rate
cumulative_platform_utility
```

---

# 20. 小结（论文可直接写）

本步骤提出 ε-First 招募机制作为 CMAB 方法的重要基线模型。平台先通过有限轮次随机探索学习工人质量，再在后续阶段利用历史信息进行招募决策。该方法能够显著优于纯随机策略，但由于缺乏持续探索能力，其长期性能通常低于本文提出的 CMAB 系列方法。
