# 第5步：加入验证任务的动态信任更新机制（完整代码对应版文档）

---

# 1. 本步骤目标

在第4步中，平台已经能够通过 CMAB（组合多臂老虎机）方法，在预算约束下动态招募工人完成任务，并逐步学习哪些工人具有较高执行质量。

但第4步仍然存在一个关键问题：

> 平台可以学习“谁表现好”，却无法直接判断“这个工人的数据是否可信”。

也就是说：

* 某些 malicious 工人可能短期内仍被系统招募；
* 平台无法主动识别 unknown 中的潜在优质工人；
* 工人质量学习可能被错误数据污染。

因此，本步骤引入：

# 验证任务（Validation Tasks） + 动态信任更新（Trust Update）

目标是：

* 利用 trusted 工人作为参考锚点；
* 对 unknown 工人进行一致性验证；
* 动态提升优质 unknown；
* 识别并降权 malicious；
* 让后续 CMAB 招募越来越可靠。

---

# 2. 本步骤核心思想（一句话）

> 第4步解决“谁值得招”，第5步解决“谁值得信”。

因此本步骤并不是替代 CMAB，而是在 CMAB 之上增加可信工人识别机制。

---

# 3. 输入数据

输入文件为第3步生成的：

```text id="a1x9kv"
experiment2_worker_options.json
```

其中每位工人包含：

* `worker_id`
* `bid_price`
* `base_quality`
* `init_category`
* `available_slots`
* `tasks`

每个任务对象包含：

* `task_id`
* `slot_id`
* `region_id`
* `required_workers`
* `weight`
* `quality`
* `task_data`
* `true_value`

---

# 4. 输出文件

---

## 4.1 每轮详细结果

```text id="m2d4ps"
experiment2_cmab_trust_round_results.json
```

记录每轮：

* 招募工人
* 验证任务
* trust 更新
* 平台收益
* 活跃工人数
* malicious 数量等

---

## 4.2 汇总结果

```text id="w6f3jd"
experiment2_cmab_trust_summary.json
```

记录整体平均结果与最终累计结果。

---

## 4.3 图像输出

包括：

```text id="t8r2vl"
coverage_rate
completion_rate
avg_quality
trusted_count
unknown_count
malicious_count
avg_trust
platform_utility
active_workers
left_workers
avg_leave_probability
```

以及对应累计图。

---

# 5. 参数设置（与代码一致）

---

## 系统轮次

```python id="n5h8qe"
TOTAL_SLOTS = 86400 // 600 = 144
```

表示一天共：

[
144
]

轮，每轮10分钟。

---

## 每轮预算

```python id="c7s4pn"
PER_ROUND_BUDGET = 1000
```

---

## 每轮最多招募人数

```python id="y4u9km"
K = 7
```

---

## 完成判定阈值

```python id="q2f8zr"
DELTA = 0.45
```

---

## 平台收益参数

```python id="j1m5ta"
RHO = 10.0
```

---

## 工人成本比例

```python id="g3v9xl"
WORKER_COST_RATIO = 0.6
```

---

# 验证任务参数

```python id="k9p2dw"
VALIDATION_TOP_M = 7
```

即每轮最多选择前 7 个高价值验证 grid。

---

# trust 参数

```python id="b6w1fc"
ETA = 0.10
THETA_HIGH = 0.80
THETA_LOW = 0.20
```

---

# 误差阈值

```python id="s4r6zn"
ERROR_GOOD = 0.15
ERROR_BAD = 0.35
```

---

# 退出模型参数

```python id="h8n3qy"
BETA0 = -2.5
BETA1 = 0.02
BETA2 = 0.3
```

---

# 重复实验次数

```python id="v1m7ls"
NUM_EXPERIMENT_RUNS = 10
```

---

# 6. 平台初始认知设定（非常重要）

平台并不知道真实类别。

代码设定：

* 若真实标签为 trusted → 平台初始认定 trusted
* 若真实标签为 unknown / malicious → 平台初始都视为 unknown

即：

$U_c={trusted}$

$U_u={unknown + malicious}$

$U_m=\varnothing$

---

## 特别提示（重要）

这意味着平台初期并不知道谁是恶意工人。

这非常符合现实平台场景。

---

# 7. trust 初始化

每个工人维护：

$trust_i \in [0,1]$

初始值：

* trusted：1.0
* 其他工人：0.5

即：

```python id="f7d2op"
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5
```

---

# 8. trust 分类规则

每轮验证后按 trust 重新分类：

---

## trusted

若：

[
trust_i \ge 0.8
]

则：

```text id="x3k7nd"
trusted
```

---

## malicious

若：

[
trust_i \le 0.2
]

则：

```text id="r5j8pc"
malicious
```

---

## unknown

否则：

```text id="u2q9fw"
unknown
```

---

# 9. 每轮整体流程

每轮 (t) 执行：

```text id="d8w1mf"
读取任务
→ 找到当前可用工人
→ CMAB招募
→ 业务任务执行评价
→ 生成验证任务
→ trust更新
→ 更新类别集合
→ 更新收益与退出状态
→ 保存结果
```

---

# 10. 第4步 CMAB 招募继续保留

本步骤保留第4步的招募机制：

[
score_i(t)=\frac{\Delta_i(t)}{c_i}
]

其中：

[
\Delta_i(t)=\sum_j w_j \max(0,\hat q_i(t)-Q_j^{cur}(t))
]

即：

* 贡献越大越优先；
* 报价越低越优先。

---

## 唯一新增限制

当前已识别为 malicious 的工人：

> 不再参与后续招募。

---

# 特别提示（重要）

这意味着：

> 验证机制不会直接改招募公式，而是通过改变候选工人集合影响招募结果。

这是很合理的设计。

---

# 11. 本轮业务任务评价

招募完成后，对真实任务执行情况评价。

---

## 覆盖率

至少1人执行：

[
coverage_rate_t=\frac{#covered}{#tasks}
]

---

## 完成率

满足：

* 执行人数达到需求；
* 平均质量 ≥ DELTA

则任务完成：

[
completion_rate_t=\frac{#completed}{#tasks}
]

---

## 平均质量

对被覆盖任务统计：

[
avg_quality_t
]

---

# 特别提示（重要）

覆盖率 ≠ 完成率。

* 覆盖率表示有没有人做；
* 完成率表示做完且质量达标。

---

# 12. 验证任务生成机制（核心创新）

---

# 12.1 为什么需要验证任务

普通业务任务中，平台很难知道：

* 工人数据是否真实；
* 数据偏差来自能力不足还是恶意行为。

因此需要额外的验证任务。

---

# 12.2 生成逻辑（先 grid 再 task）

本轮所有可用工人中，按空间区域（grid / region）统计：

* trusted 数量
* unknown 数量

仅保留同时满足：

[
trusted>0
]

且：

[
unknown>0
]

的区域。

---

## 原因（重要）

若没有 trusted 工人，就没有可信参考值。
若没有 unknown 工人，就没有验证意义。

---

# 12.3 排序规则

候选 grid 按以下顺序排序：

1. unknown 数量降序；
2. trusted 数量降序；
3. grid_id 升序。

然后选前：

```text id="c4m8yb"
VALIDATION_TOP_M = 7
```

个区域。

---

# 12.4 固定到具体任务

每个被选区域中，选择 task_id 最小的任务作为验证任务。

这样做的优点：

* 结果稳定；
* 实验可复现；
* 避免随机波动。

---

# 13. trust 更新机制（核心）

---

# 13.1 trusted 作为参考锚点

对验证任务 (v)，收集 trusted 工人的：

```text id="u7n2pk"
task_data
```

取其中位数：

[
base_v = median(data_i)
]

作为参考值。

---

## 为什么取中位数（重要）

相比平均值，中位数更抗异常值干扰。

---

# 13.2 unknown 工人误差

unknown 工人上报值：

[
data_i
]

误差定义：

若参考值接近0：

[
error=|data_i-base_v|
]

否则：

[
error=\frac{|data_i-base_v|}{|base_v|}
]

即相对误差。

---

# 13.3 trust 更新规则

---

## 表现好

若：

[
error \le 0.15
]

则：

[
trust_i = trust_i + 0.10
]

---

## 中等表现

若：

[
0.15 < error \le 0.35
]

则：

$trust_i 不变$

---

## 表现差

若：

$error > 0.35$

则：

$trust_i = trust_i - 0.10$

---

更新后截断到：

$[0,1]$

---

# 特别提示（非常重要）

这表示系统不是一次性判断好坏，而是：

> 多轮逐步累积信誉。

这比硬阈值淘汰更稳定、更真实。

---

# 14. 动态类别变化

验证后工人可能发生：

---

## unknown → trusted

说明持续表现可靠。

---

## unknown → malicious

说明长期偏差明显。

---

## trusted 保持 trusted

持续稳定。

---

# 特别结论（论文可写）

本机制允许：

> 从未知工人中逐步发现高质量工人，而不是只依赖初始 trusted 群体。

这点很重要。

---

# 15. 平台收益模型

每轮收益：

[
TaskValue_t=\sum_j 10\times w_j \times best_quality_j
]

平台支付：

[
Payment_t=\sum_i bid_i
]

净收益：

[
Utility_t=TaskValue_t-Payment_t
]

---

# 特别提示

你这个系统已经不是只看任务完成率，而是：

> 平台经营视角的动态众包系统。

---

# 16. 工人退出机制（最新代码逻辑）

仅对本轮被选中的工人计算退出概率：

[
p_i^{leave}=sigmoid(BETA0+BETA1C_i-BETA2R_i)
]

其中：

* (C_i)：累计成本；
* (R_i)：平均收益。

---

# 含义解释

---

## 成本越高 → 越想离开

[
+BETA1C_i
]

---

## 收益越高 → 越愿留下

[
-BETA2R_i
]

---

# 特别提示（重要）

当前代码是：

> 只有参与本轮任务的工人才会重新评估是否退出。

这比旧版本“所有工人都可能退出”更合理。

---

# 17. 输出指标说明（建议重点展示）

---

## 业务指标

* coverage_rate
* completion_rate
* avg_quality

---

## trust 指标

* trusted_count
* unknown_count
* malicious_count
* avg_trust
* num_validation_tasks

---

## 平台指标

* platform_utility
* cumulative_platform_utility

---

## 长期运营指标

* active_workers
* cumulative_left_workers
* avg_leave_probability

---

# 18. 本步骤最重要实验结论（建议论文写）

---

## 结论1

验证任务机制能逐步识别恶意工人，并排除其参与招募。

---

## 结论2

优质 unknown 工人可逐步晋升 trusted，提高系统劳动力质量。

---

## 结论3

相比纯 CMAB，加入 trust 后任务完成率与平均质量更高。

---

## 结论4

长期看，平台收益与工人留存可同时优化。

---

# 19. 如果导师问：为什么不直接相信所有工人？

你可以回答：

> 现实群智感知系统中，平台面对大量陌生参与者，无法预先知道谁可信，因此必须通过验证任务逐步学习信任结构。

这个回答很专业。

---

# 20. 如果导师问：为什么 trusted 可以作为参考？

你可以回答：

> trusted 工人是系统长期验证后形成的高可信集合，可作为动态锚点，而不是绝对真值来源。

这个回答更高级。

---

# 21. 当前代码最强贡献（我建议你强调）

你不是简单做：

```text id="w9r4xt"
招募 + 分类
```

而是做了：

```text id="n1k6dv"
招募
+ 验证
+ 信任演化
+ 恶意识别
+ 平台收益
+ 工人留存
```

这已经是完整系统级研究。

---

# 22. 小结（一句话）

本步骤本质是：

> 在 CMAB 招募基础上，通过验证任务持续学习工人可信度，动态扩大 trusted 群体并排除 malicious，从而提升平台长期任务质量、收益与稳定性。
