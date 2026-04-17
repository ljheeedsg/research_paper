很好，现在给你一版**完整、详细、和你当前系统完全对齐的 Step5 文档（最终版）**。
这版是：

* ✅ 保留你老师“验证任务”思路
* ✅ 和你 Step3（stability + true_value）完全一致
* ✅ 和 Step4（CMAB）无冲突
* ✅ 结构完整，可以直接写论文/报告

你可以保存为：

# 📄 `experiment2_step5_dynamic_trust_with_validation.md`

---

# 1. 概述（Overview）

在 Step4 中，系统已通过 CMAB 实现基于工人质量的动态招募优化，但该方法仍存在关键问题：

```text
无法区分“能力低”与“数据不可信”
```

即：

* 有些工人质量不高（能力问题）
* 有些工人数据不稳定甚至异常（可信问题）

👉 CMAB 只能学习“质量”，无法识别“是否可信”

---

# 🎯 本步骤目标

引入：

> ✅ **基于验证任务的动态信任机制（Validation-based Trust Mechanism）**

实现：

```text
✔ 利用可信工人作为参考
✔ 对未知工人进行一致性验证
✔ 动态更新工人信任度
✔ 识别并剔除不可信工人
```

---

# 2. 工人集合定义

---

## 2.1 三类工人

定义：

$$
U_c,\quad U_u,\quad U_m
$$

---

| 集合    | 含义                  |
| ----- | ------------------- |
| $U_c$ | 可信工人（trusted）       |
| $U_u$ | 未知工人（unknown）       |
| $U_m$ | 不可信/恶意工人（malicious） |

---

## 2.2 初始化

来自 Step3：

```text
init_category == trusted → Uc
init_category == unknown → Uu
Um = ∅
```

---

## 2.3 信任度定义

每个工人：

$$
trust_i \in [0,1]
$$

初始化：

```text
trusted → 1.0
unknown → 0.5
```

---

# 3. 核心思想

---

## 🎯 本机制不是判断“谁最准”

而是判断：

```text
谁的数据是否与稳定参考一致
```

---

## 🔥 关键：

* trusted 工人 → 数据更稳定（来自 Step3）
* unknown 工人 → 数据波动较大

---

👉 因此可以：

```text
用 trusted 作为“参考锚点”
```

---

# 4. 每轮整体流程

---

对于每一轮 $t = 1,2,...,R$：

---

## Step 1：确定当前轮可用数据

---

### 可用工人

```text
worker.available_slots 包含 t
```

---

### 可用任务

```text
task.slot_id == t
```

---

## Step 2：CMAB 招募（不变）

---

候选：

```text
Uc ∪ Uu
```

排除：

```text
Um
```

---

选择：

```text
selected_workers（K个）
```

---

## Step 3：生成验证任务（核心新增）

---

# 5. 验证任务生成机制

---

## 5.1 目标

选择任务，使：

```text
✔ 有 trusted 工人执行
✔ 有 unknown 工人执行
```

👉 才能做比较

---

## 5.2 定义

对于任务 $j$：

* $W_c(j)$：能执行该任务的 trusted 工人（且在 selected_workers 中）
* $W_u(j)$：能执行该任务的 unknown 工人（且在 selected_workers 中）

---

## 5.3 筛选条件

$$
|W_c(j)| > 0 \quad \text{且} \quad |W_u(j)| > 0
$$

---

## 5.4 排序策略

按：

$$
|W_u(j)| \downarrow
$$

👉 优先验证更多 unknown 工人

---

## 5.5 选择验证任务

$$validation\_tasks = \text{top } M \text{ tasks}$$

---

# 6. 任务执行

---

## 6.1 发布任务

每轮任务集合：

```text
业务任务 + 验证任务
```

---

## 6.2 执行者

```text
仅 selected_workers 执行
```

---

## ❗说明

避免：

```text
所有经过的人执行 ❌
```

因为：

* 会破坏成本模型
* 与 CMAB 冲突

---

# 7. 信任更新机制（核心）

---

## 7.1 基准值（Reference）

对于每个验证任务 $v$：

$$
base_v = \text{median} \{ data_i \mid i \in W_c(v) \}
$$

---

## ⚠️ 重要说明

```text
base_v ≠ true_value
```

而是：

```text
trusted 工人一致性估计
```

---

## 7.2 误差计算

对于 unknown 工人 $i$：

$$
error_{iv} =
\begin{cases}
|data_i - base_v|, & base_v = 0 \\
\frac{|data_i - base_v|}{base_v}, & \text{otherwise}
\end{cases}
$$

---

## 7.3 信任更新公式

$$
trust_i \leftarrow trust_i + \eta (1 - 2 \cdot error_{iv})
$$

---

## 7.4 边界处理

$$
trust_i = \max(0, \min(1, trust_i))
$$

---

## 🎯 含义

| 情况    | trust变化 |
| ----- | ------- |
| 数据接近  | 上升      |
| 数据偏差大 | 下降      |

---

# 8. 工人分类更新

---

## 阈值

$$
\theta_{high},\quad \theta_{low}
$$

---

## 更新规则

---

### unknown → trusted

$$
trust_i \geq \theta_{high}
$$

---

### unknown → malicious

$$
trust_i \leq \theta_{low}
$$

---

### 其他

保持在 $U_u$

---

# 9. 与 CMAB 的融合

---

下一轮：

```text
候选 = Uc ∪ Uu
排除 Um
```

---

👉 malicious 工人：

```text
不会再被选中
```

---

# 10. 参数设置

---

| 参数         | 含义     | 推荐值 |
| ---------- | ------ | --- |
| $M$        | 验证任务数  | 3~5 |
| $\eta$     | 信任更新步长 | 0.2 |
| $\theta_{high}$ | 可信阈值   | 0.8 |
| $\theta_{low}$  | 恶意阈值   | 0.2 |

---

# 11. 预期效果

---

| 指标              | 变化 |
| --------------- | -- |
| completion_rate | ↑  |
| avg_quality     | ↑↑ |
| reward          | ↑  |
| 稳定性             | ↑  |

---

# 12. 机制合理性说明（关键）

---

## 12.1 trusted 为什么能作为参考？

来自 Step3：

```text
trusted → 更低噪声（更稳定）
```

---

因此：

$$
Var(data_{trusted}) < Var(data_{unknown})
$$

---

## 12.2 本方法本质

---

不是：

```text
估计真实值 ❌
```

而是：

```text
一致性验证 ✔
```

---

## 12.3 方法类型

```text
✔ relative consistency checking
✔ semi-supervised trust estimation
```

---

# 13. 总体流程总结

---

```text
CMAB → 选人（能力）
Validation → 验证（可信）
Trust → 过滤（不可信）
```

---

# 🎯 最终一句话总结

> 本步骤通过引入基于验证任务的一致性评估机制，利用可信工人的稳定性作为参考，对未知工人进行动态信任度更新，从而识别并剔除不可信工人，进一步提升系统数据质量与任务完成性能。

---

# 🚀 你现在的状态

你现在已经：

```text
✔ CMAB（能跑）
✔ 数据模型（合理）
✔ Trust机制（完整）
```

---

👉 下一步：

# 👉 可以开始写 Step5代码 + 跑 B2 vs B3

---

如果你愿意，我下一步可以帮你：

👉 **把这个 Step5 文档 → 直接转成可运行代码（在你现有Step4上改）**
