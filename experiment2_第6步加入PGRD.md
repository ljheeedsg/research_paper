# Step6：加入 PGRD 会员决策机制

## 1. 概述

在 Step5 中，平台已经具备：

* 基于 CMAB 的质量学习与工人招募
* 基于验证任务的动态信任更新

本步骤在此基础上进一步引入 PGRD（Policy Gradient Reward Decision）风格的会员决策机制，用于刻画：

* 可信工人是否愿意支付会费成为会员
* 成为会员后可竞标哪些任务
* 会员身份如何持续影响后续轮次收益与招募结果

这里的核心不是替代 CMAB，而是让 PGRD 先改变工人的可投标任务集合，再由 CMAB 在该集合上做质量驱动的选择。

---

## 2. 任务分类

平台先将全部任务划分为两类：

* `member`：会员任务
* `normal`：普通任务

在当前实现中，不再只按任务权重 `weight` 划分，而是先为每个任务计算“质量敏感度”：

$$
priority_j
=
\omega_w \cdot \frac{w_j}{\max_k w_k}
+
\omega_r \cdot \frac{req_j}{\max_k req_k}
$$

其中：

* $w_j$：任务权重
* $req_j$：任务所需工人数 `required_workers`
* $\omega_w$：质量敏感度中任务权重占比，对应 `QUALITY_TASK_WEIGHT`
* $\omega_r$：质量敏感度中人数需求占比，对应 `QUALITY_TASK_REQ`

然后再按 `priority_j` 从高到低排序，取前 `MEMBER_RATIO` 比例作为会员任务，其余作为普通任务。

设任务集合为：

$$
\Gamma = \Gamma_{me} \cup \Gamma_{no}
$$

其中：

* $\Gamma_{me}$：会员任务集合
* $\Gamma_{no}$：普通任务集合

---

## 3. 任务收益与任务级成本

对每个任务 $j$，定义其 PGRD 使用的收益为：

$$
r_j =
\begin{cases}
w_j \cdot \mu_{me}, & j \in \Gamma_{me} \\
w_j \cdot \mu_{no}, & j \in \Gamma_{no}
\end{cases}
$$

其中：

* $w_j$：任务权重
* $\mu_{me}$：会员任务收益倍率，对应代码中的 `MEMBER_MULTIPLIER`
* $\mu_{no}$：普通任务收益倍率，对应代码中的 `NORMAL_MULTIPLIER`

为避免 PGRD 的效用被工人总成本直接淹没，本步骤同时定义任务级执行成本：

$$
c_j =
\begin{cases}
r_j \cdot \rho_{me}, & j \in \Gamma_{me} \\
r_j \cdot \rho_{no}, & j \in \Gamma_{no}
\end{cases}
$$

其中：

* $\rho_{me}$：会员任务成本比例，对应 `MEMBER_COST_RATIO`
* $\rho_{no}$：普通任务成本比例，对应 `NORMAL_COST_RATIO`

说明：

* 这里的 $r_j$ 和 $c_j$ 仅用于 PGRD 会员决策与收益更新；
* 业务任务的 `reward` 定义保持不变；
* 但当前代码中的 `avg_quality` 已统一为“按被执行任务统计”，并额外记录累计完成率与累计平均质量。

---

## 4. 工人状态

对每个工人 $i$，平台维护以下与 PGRD 相关的状态：

* `is_member`：当前是否为会员
* `member_until`：会员资格截止轮次
* `hist_reward_m`：上一轮会员任务平均收益
* `hist_reward_n`：上一轮普通任务平均收益

同时，工人仍保留：

* `category ∈ {trusted, unknown, malicious}`
* `trust`
* `n_obs`
* `avg_quality`

其中只有 `trusted` 工人允许成为会员；`unknown` 和 `malicious` 工人不能主动购买会员资格。

---

## 5. PGRD 决策对象

对当前轮可用工人 $i$，首先收集其当前轮可执行任务，并拆分为：

$$
T_i^{me}, \quad T_i^{no}
$$

其中：

* $T_i^{me}$：工人 $i$ 当前轮可执行的会员任务
* $T_i^{no}$：工人 $i$ 当前轮可执行的普通任务

若工人当前轮没有会员任务，则其没有购买会员的必要，默认只竞标普通任务。

---

## 6. 预期收益

设：

* $R_m^{(t-1)}$：截至上一轮会员工人的平均收益
* $R_n^{(t-1)}$：截至上一轮非会员工人的平均收益

则工人 $i$ 在第 $t$ 轮的会员与普通预期收益分别定义为：

$$
b_m = \alpha \cdot hist\_reward_{m,i}^{(t-1)} + \beta \cdot R_m^{(t-1)}
$$

$$
b_n = \alpha \cdot hist\_reward_{n,i}^{(t-1)} + \beta \cdot R_n^{(t-1)}
$$

其中：

* $\alpha$：历史收益权重，对应 `PGRD_ALPHA`
* $\beta$：全局平均收益权重，对应 `PGRD_BETA`

---

## 7. 参照损失

为了体现“若不成为会员，将错失高价值任务收益”的感知损失，引入参照损失项：

$$
\Delta^{(t-1)} = \beta \cdot \left(R_m^{(t-1)} - R_n^{(t-1)}\right)
$$

$$
V_{loss}^{(t)} =
\begin{cases}
\lambda \cdot (\Delta^{(t-1)})^\sigma, & \Delta^{(t-1)} > 0 \\
0, & \text{otherwise}
\end{cases}
$$

其中：

* $\lambda$：损失厌恶系数，对应 `PGRD_LAMBDA`
* $\sigma$：损失曲率，对应 `PGRD_SIGMA`

---

## 8. 效用函数

### 8.1 会员效用

对可信工人，成为会员的效用定义为：

$$
U_{me}^{(t)} = b_m + V_{loss}^{(t)} - \bar{c}_{me}^{(t)} - \zeta_R
$$

其中：

* $\bar{c}_{me}^{(t)}$：当前轮该工人可执行会员任务的平均任务级成本
* $\zeta_R$：会费，对应 `PGRD_FEE`

### 8.2 普通效用

不成为会员的效用定义为：

$$
U_{no}^{(t)} = b_n - \bar{c}_{no}^{(t)}
$$

其中 $\bar{c}_{no}^{(t)}$ 为当前轮普通任务的平均任务级成本。

说明：

* 本实现采用“平均成本”而不是“总成本”，是为了避免任务数量的量级直接淹没 PGRD 的效用比较；
* 会员资格一旦成立，工人可在本轮同时竞标会员任务和普通任务。

---

## 9. 会员概率与决策规则

根据 softmax 形式计算会员选择概率：

$$
\psi_i^{(t)} =
\frac{e^{\zeta U_{me}^{(t)}}}
{e^{\zeta U_{me}^{(t)}} + e^{\zeta U_{no}^{(t)}}}
$$

其中 $\zeta$ 为决策敏感度，对应 `PGRD_ZETA`。

为了让参数变化对结果产生稳定、可解释的影响，本实现不再采用随机采样：

$$
\psi_i^{(t)} \ge \psi_{th} \Rightarrow \text{工人成为会员}
$$

其中：

* $\psi_{th}$：成为会员的概率阈值，对应 `PGRD_PSI_TH`

即：

* 若 $\psi_i^{(t)} \ge \psi_{th}$，则工人本轮成为会员；
* 否则维持非会员身份。

---

## 10. 会员持续期

与单轮即失效的设计不同，本步骤引入会员有效期机制。

若工人 $i$ 在第 $t$ 轮成为会员，则：

$$
member\_until_i = t + L
$$

其中 $L$ 为会员持续轮数，对应 `MEMBER_VALIDITY`。

在会员有效期内：

* 工人无需重复缴费；
* 默认保持会员身份；
* 本轮可同时竞标会员任务与普通任务；
* 不再重新执行会员选择判定。

这样可以让 PGRD 的影响跨轮传播，而不是每轮重新归零。

---

## 11. 不同类别工人的处理规则

### 11.1 `trusted`

* 可以执行 PGRD 会员决策；
* 若满足阈值条件，可成为会员；
* 会员身份会在后续轮次持续生效。

### 11.2 `unknown`

* 不允许成为会员；
* 只能竞标普通任务；
* 后续仍可通过验证任务更新 trust，并可能升级为 `trusted`。

### 11.3 `malicious`

* 不允许成为会员；
* 不参与招募；
* 投标集合为空。

---

## 12. PGRD 与 CMAB 的耦合方式

PGRD 并不直接决定最终招募谁，而是先生成每个工人的投标任务集合 `bid_tasks`：

* 会员：`member_tasks + normal_tasks`
* 已在有效期内的会员：`member_tasks + normal_tasks`
* 非会员：`normal_tasks`

然后 CMAB 在 `bid_tasks` 上继续计算：

$$
qualitySignal_i^{(t)}
=
(1-\beta_{tr}) \cdot \hat{q}_i^{(t)}
+
\beta_{tr} \cdot \tau_i^{(t)}
$$

$$
score_i^{(t)}
=
\frac{
\sum_{j \in bid\_tasks_i^{(t)}}
w_j \cdot qualitySignal_i^{(t)} \cdot bonus_{ij}^{(t)}
}{cost_i}
$$

其中，若工人当前为会员，则：

$$
bonus_{ij}^{(t)} = 1 + \gamma_{me} \cdot priority_j
$$

否则 $bonus_{ij}^{(t)} = 1$。

因此当前代码里，招募评分不再只依赖 UCB 质量估计，而是同时考虑：

* $\hat{q}_i^{(t)}$：UCB 质量估计
* $\tau_i^{(t)}$：工人 trust
* $priority_j$：任务质量敏感度
* `cost_i`：工人成本，仍沿用 Step4/Step5 中的招募成本定义

因此，PGRD 对结果的影响路径是：

1. 改变工人可竞标的任务集合；
2. 改变工人的得分与被招募概率；
3. 改变完成任务类型与收益；
4. 进一步反馈到下一轮的 $R_m, R_n$。

---

## 13. 收益更新

在每轮结束后，仅根据“本轮被完成的任务”更新收益：

* 若工人完成了会员任务，则更新 `hist_reward_m`
* 若工人完成了普通任务，则更新 `hist_reward_n`

并进一步计算：

$$
R_m^{(t)} = \text{所有当前会员工人的会员历史收益均值}
$$

$$
R_n^{(t)} = \text{所有当前非会员工人的普通历史收益均值}
$$

若某一类本轮没有有效样本，则保持上一轮的均值不变。

这一点非常关键，因为它保证：

* 本轮谁成为会员，会影响下一轮的参考收益；
* PGRD 的选择不是一次性的，而是能通过状态链持续影响后续结果。

---

## 14. 每轮流程

对每个时间轮次 $t$，整体流程如下：

1. 获取当前轮任务集合与可用工人集合。
2. 基于质量敏感度构建 `member/normal` 任务分类。
3. 对可用工人执行 PGRD 会员决策，生成 `bid_tasks_map`。
4. 在 `bid_tasks_map` 基础上执行 CMAB 招募。
5. 统计业务任务完成率、按被执行任务计算的平均质量、累计完成率、累计平均质量、reward、cost、efficiency。
6. 从业务任务中筛选验证任务，并更新 trust/category。
7. 更新 UCB 质量统计量。
8. 根据本轮已完成任务更新 `hist_reward_m`、`hist_reward_n` 以及全局 `R_m`、`R_n`。
9. 记录会员数、会费收入、trusted/unknown/malicious 数量等指标。

---

## 15. 输出指标

除 Step5 中已有指标外，本步骤额外记录：

* `member_count`：本轮会员数量
* `fee_income`：本轮会费收入
* `R_m`：本轮更新后的会员平均收益
* `R_n`：本轮更新后的普通平均收益
* `pgrd_records`：每个工人的 PGRD 决策明细

建议重点观察以下曲线：

* `member_count`
* `fee_income`
* `completion_rate`
* `avg_quality`（按被执行任务统计）
* `cumulative_completion_rate`
* `cumulative_avg_quality`
* `reward`
* `avg_trust`

当前代码还会输出：

* `experiment2_cmab_trust_pgrd_round_results.json`
* `experiment2_cmab_trust_pgrd_summary.json`
* `experiment2_cmab_trust_pgrd_completion_rate.png`
* `experiment2_cmab_trust_pgrd_avg_quality.png`
* `experiment2_cmab_trust_pgrd_cumulative_completion_rate.png`
* `experiment2_cmab_trust_pgrd_cumulative_avg_quality.png`
* `experiment2_cmab_trust_pgrd_reward.png`
* `experiment2_cmab_trust_pgrd_efficiency.png`
* `experiment2_cmab_trust_pgrd_avg_trust.png`
* `experiment2_cmab_trust_pgrd_member_count.png`
* `experiment2_cmab_trust_pgrd_fee_income.png`

---

## 16. 参数说明

| 参数 | 含义 |
| --- | --- |
| `MEMBER_RATIO` | 划为会员任务的任务比例 |
| `MEMBER_MULTIPLIER` | 会员任务收益倍率 |
| `NORMAL_MULTIPLIER` | 普通任务收益倍率 |
| `MEMBER_COST_RATIO` | 会员任务成本比例 |
| `NORMAL_COST_RATIO` | 普通任务成本比例 |
| `PGRD_ALPHA` | 历史收益权重 |
| `PGRD_BETA` | 全局平均收益权重 |
| `PGRD_LAMBDA` | 损失厌恶系数 |
| `PGRD_SIGMA` | 损失曲率 |
| `PGRD_ZETA` | softmax 敏感度 |
| `PGRD_FEE` | 会费 |
| `PGRD_PSI_TH` | 成为会员的概率阈值 |
| `MEMBER_VALIDITY` | 会员持续轮数 |

---

## 17. 与旧版实现的区别

相比旧版文档和旧版代码，本版本有三点关键调整：

1. 不再使用 `random.random() < psi` 的随机采样，而改为阈值判定，使参数变化对结果更稳定、更可解释。
2. 增加会员持续期 `member_until`，使会员身份具备跨轮影响。
3. 使用任务级 `worker_cost` 构造 PGRD 效用，避免工人总成本量级过大导致 PGRD 失效。

这也是本次修复后 PGRD 参数能够真正生效的主要原因。
