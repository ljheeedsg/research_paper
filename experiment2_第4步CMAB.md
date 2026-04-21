# 第4步：长期运行版 CMAB 招募机制（完整代码对应版文档）

---

# 1. 目标

本步骤在论文《Combinatorial Multi-Armed Bandit Based Unknown Worker Recruitment in Heterogeneous Crowdsensing》的基础上，结合本研究场景，构建 **长期运行版（Long-run）CMAB 工人招募机制**。

平台在每一轮任务到来时，需要解决如下问题：

* 当前有哪些任务需要完成；
* 当前有哪些工人在线且可参与本轮任务；
* 平台不知道工人的真实能力，只能依据历史表现估计；
* 在预算约束下，如何选择工人；
* 如何在长期运行中兼顾平台收益与工人留存。

因此，本步骤不仅关注单轮任务分配，还考虑：

* 工人长期参与意愿；
* 平台累计收益；
* 工人退出系统后的动态影响。

本步骤是整个系统中的核心决策模块。

---

# 2. 输入数据

输入文件为第三步生成的：

```text id="x2w8nk"
experiment2_worker_options.json
```

其中每位工人包含：

* 工人编号 `worker_id`
* 报价 `bid_price`
* 初始类别 `init_category`
* 基础质量 `base_quality`
* 可用轮次 `available_slots`
* 可选任务集合 `tasks`

其中每个任务对象包含：

* `task_id`
* `slot_id`
* `region_id`
* `required_workers`
* `weight`
* `quality`
* `task_data`
* `true_value`

---

# 3. 输出文件

本步骤输出长期运行实验结果。

---

## 3.1 每轮详细结果

```text id="o4yq5w"
experiment2_cmab_longrun_round_results.json
```

记录每轮：

* 被选工人
* 覆盖率
* 完成率
* 平均质量
* 平台收益
* 活跃工人数
* 退出人数

---

## 3.2 汇总结果

```text id="k8uj6q"
experiment2_cmab_longrun_summary.json
```

记录整体平均表现与累计指标。

---

## 3.3 多次实验原始结果

```text id="mw1t5r"
experiment2_cmab_longrun_round_results_all_runs.json
```

保存 10 次不同随机种子的实验结果。

---

## 3.4 输出图像

包括：

```text id="x6sj9f"
coverage_rate
completion_rate
avg_quality
platform_utility
active_workers
left_workers
avg_leave_probability
```

以及对应累计图。

---

# 4. 核心思想

本步骤采用：

> **学习 + 招募 + 收益 + 留存**

四位一体机制。

即每轮平台执行：

```text id="n8d5vx"
估计工人质量
→ 招募工人
→ 完成任务
→ 更新历史
→ 判断工人是否离开
→ 进入下一轮
```

这比传统单轮 CMAB 更贴近真实众包平台。

---

# 5. 参数设置（与代码一致）

---

## 时间参数

```python id="r9g4ek"
TOTAL_SLOTS = 86400 // 600 = 144
```

表示一天共：

$144$

轮（每轮10分钟）。

---

## 每轮预算

```python id="u3e2np"
PER_ROUND_BUDGET = 1000
```

---

## 每轮最多招募人数

```python id="s0j7wy"
K = 7
```

即：

> 每轮最多选择 7 名工人。

---

## 完成判定阈值

```python id="f4x1ha"
DELTA = 0.45
```

用于任务是否算完成。

---

## 新工人初始乐观估计

```python id="d7m6vo"
DEFAULT_INIT_UCB = 1.0
```

---

## 平台收益参数

```python id="v5t8qc"
RHO = 10.0
```

任务价值货币化系数。

---

## 工人真实成本比例

```python id="z2n4lg"
WORKER_COST_RATIO = 0.6
```

表示：

$真实成本 = 0.6 \times 报酬$

---

## 退出模型参数

```python id="j1r6kw"
BETA0 = -2.5
BETA1 = 0.02
BETA2 = 0.3
```

---

## 重复实验次数

```python id="p8h3sm"
NUM_EXPERIMENT_RUNS = 10
```

---

# 6. 平台可见信息与不可见信息

---

## 平台可见

平台在第 (t) 轮可观察：

* 工人报价 (c_i)
* 当前可做任务集合 (S_i(t))
* 历史观测次数 (n_i)
* 历史平均质量 (\bar q_i)

---

## 平台不可见

平台无法直接知道：

* `base_quality`
* 工人真实类别（trusted / unknown / malicious）

这符合现实众包平台设定。

---

# 7. 工人质量估计（UCB 学习）

平台对工人 (i) 的估计质量为：

$\hat q_i(t)=\bar q_i(t-1)+\sqrt{\frac{(K+1)\ln(T)}{n_i}}$

其中：

* (T)：累计学习次数；
* (n_i)：工人被观察次数。

---

## 未被观察工人

若：

$n_i=0$

则：

$\hat q_i(t)=1.0$

即乐观初始化。

---

## 特别注意（重要）

这意味着第一轮系统自然退化为：

> **任务数 / 报价 优先**

因为所有人估计质量相同。

这与你论文原文逻辑一致。

---

# 8. 单轮招募目标（公式12 对齐）

设当前轮任务集合为：

$T_t$

任务 (j) 当前已达到估计质量：

$Q_j^{cur}(t)$

初始均为 0。

若加入工人 (i)，则其边际增益：

$\Delta_i(t)=\sum_{j\in S_i(t)} w_j \max(0,\hat q_i(t)-Q_j^{cur}(t))$

其中：

* (w_j)：任务权重。

工人评分：

$score_i(t)=\frac{\Delta_i(t)}{c_i}$

平台每步选择：

$score_i(t)$

最大的工人。

---

## 终止条件

直到满足任一条件：

* 达到人数上限 7；
* 预算不足；
* 没有正边际增益工人。

---

# 9. 单轮真实执行评价

招募完成后，用真实质量 (q_{ij}) 计算任务表现。

---

## 任务覆盖率

若至少一名被选工人执行任务：

$covered_j = 1$

则：

$coverage_rate=\frac{\#covered}{\#tasks}$

---

## 任务完成率

任务需满足：

1. 工人数达到需求；
2. 平均质量达到阈值。

即：

$num_workers_j \ge required_j$

且：

$avg_quality_j \ge 0.45$

则任务完成。

因此：

$completion_rate=\frac{\#completed}{\#tasks}$

---

## 特别注意（重要）

### 覆盖率 ≠ 完成率

* 覆盖率表示有没有人做；
* 完成率表示做完且质量达标。

这两个指标必须区分。

---

## 平均质量

仅对被覆盖任务计算：

$avg_quality_t$

---

# 10. 平台收益模型

平台从任务完成中获得收益：

$value_j = RHO \cdot w_j \cdot best_quality_j$

即：

$value_j=10\times w_j\times best_quality_j$

单轮平台总收益：

$TaskValue_t=\sum_j value_j$

平台支付：

$Payment_t=\sum_{i\in A_t} c_i$

平台效用：

$Utility_t=TaskValue_t-Payment_t$

---

## 特别提示（重要）

这使你的算法不再只是“完成任务”，而是：

> **在赚钱前提下完成任务**

这是更真实的平台视角。

---

# 11. 工人长期留存机制（创新点）

本代码加入长期动态退出模型。

仅对本轮被选工人，计算退出概率：

$p_i^{leave}=sigmoid(BETA0+BETA1C_i-BETA2R_i)$

* (C_i)：累计成本；
* (R_i)：平均收益。

具体为：

$sigmoid(x)=\frac{1}{1+e^{-x}}$

---

## 含义解释

### 成本越高 → 更想退出

由：

$+BETA1C_i$

决定。

---

### 收益越高 → 更愿留下

由：

$-BETA2R_i$

决定。

---

## 若随机命中退出

则：

```text id="t2y7hv"
is_active = False
```

工人永久离开系统。

---

# 12. 为什么这一步很强（论文价值）

传统 CMAB 只研究：

* 如何选人

你的版本已经研究：

* 如何选人
* 平台赚不赚钱
* 工人会不会流失
* 长期系统是否稳定

这明显高于普通本科式实验。

---

# 13. 多轮流程

每轮执行：

```text id="v0p5cs"
提取本轮任务
→ 提取在线工人
→ UCB估计
→ 贪心招募
→ 真实执行
→ 更新历史质量
→ 更新收益成本
→ 判断退出
→ 保存指标
→ 下一轮
```

持续 144 轮。

---

# 14. 多次重复实验

代码采用：

```text id="g4m2qx"
10 个随机种子
```

重复实验，再取平均值。

---

## 特别注意（重要）

这说明你的结果不是偶然一次运行，而是：

> 统计稳定结果。

论文里这一点很加分。

---

# 15. 输出指标说明（建议主展示）

---

## 主图建议展示

### 1. coverage_rate

看任务有没有被覆盖。

### 2. completion_rate

看系统最终任务完成效果。

### 3. avg_quality

看整体数据质量。

### 4. platform_utility

看平台赚不赚钱。

### 5. active_workers

看系统是否还能持续运行。

---

# 16. 累计指标

代码还输出：

```text id="q6e9wj"
cumulative_coverage_rate
cumulative_completion_rate
cumulative_avg_quality
cumulative_platform_utility
```

用于长期趋势分析。

---

# 17. 本步骤与后续步骤边界

---

## 第4步负责：

* 招募决策
* 预算控制
* 长期平台收益
* 工人流失

---

## 第5步负责：

* task_data 验证机制
* trusted 扩展
* malicious 识别

---

## 第6步负责：

* 长期激励优化
* 晋升 trusted
* 留存奖励机制

---

# 18. 当前代码最值得强调的结论（建议论文写）

---

## 结论1

CMAB 不仅提高覆盖率，还提高完成率。

---

## 结论2

高质量工人被逐步学习识别并优先选择。

---

## 结论3

若只追求低价工人，长期活跃人数会下降。

---

## 结论4

平台收益最大化与工人留存之间存在权衡。

---

# 19. 特别提醒（你论文很关键）

如果导师问：

> 为什么第4步要加退出机制？

你回答：

> 现实众包平台不是静态工人池。工人若长期低收益或高成本，会流失。因此仅优化单轮收益是不够的，必须研究长期运行稳定性。

这个回答很专业。

---

# 20. 小结（核心一句话）

本步骤本质是：

> 在预算约束下，通过 CMAB 学习高质量工人，并在长期运行中同时优化任务完成、平台收益与工人留存。

这已经不是普通招募算法，而是：

> **动态众包平台运营模型。**
