# Step7 最终实现文档（与当前代码一致版）

## 题目

**基于空间一致性验证、会员激励与沉没成本留存机制的双阶段工人招募与长期参与模型**

---

# 1. 总体目标

在 Step6（CMAB + Trust + PGRD）基础上，进一步解决：

> 即使已经识别可信工人并给予会员激励，高质量工人仍可能因长期成本压力而退出平台。

因此 Step7 新增：

## LGSC（Loss-Gain with Sunk Cost）沉没成本留存机制

核心目标：

* 提高会员工人长期留存率；
* 稳定可信工人供给；
* 提升平台长期收益；
* 控制激励成本。

---

# 2. 系统整体结构（当前代码真实流程）

每轮执行顺序如下：

$$
\text{Task Arrival}
\rightarrow
\text{PGRD Membership}
\rightarrow
\text{CMAB Recruitment}
\rightarrow
\text{Task Evaluation}
\rightarrow
\text{Trust Validation}
\rightarrow
\text{LGSC Update}
\rightarrow
\text{Leave Decision}
$$

即：

1. 本轮任务到达
2. trusted 工人先进行会员决策（PGRD）
3. 在会员输出的任务集合上执行 CMAB 招募
4. 评价任务完成情况
5. 执行验证任务并更新 trust
6. 对会员执行沉没成本累计与奖励金发放
7. 更新退出概率与活跃状态

---

# 3. 保留机制（不变部分）

---

## 3.1 Step4：CMAB 招募机制

仍使用边际增益选择工人：

$$
\Delta_i(t)=
\sum_{j\in S_i(t)}
w_j
\max(0,\hat q_i(t)-Q_j^{cur}(t))
$$

得分：

$$
score_i(t)=\frac{\Delta_i(t)}{c_i}
$$

其中：

* $w_j$：任务权重
* $\hat q_i(t)$：工人质量估计（UCB）
* $c_i$：报价

平台贪心选择 Top-K 工人。

---

## 3.2 Step5：验证任务与可信度更新

通过 trusted 工人数据作为参考值：

$$
v_j^{ref} = median(data_j^{trusted})
$$

unknown 工人与参考值比较误差：

$$
error_i=
\frac{|x_i-v_j^{ref}|}{|v_j^{ref}|}
$$

再更新 trust：

* 高可信 → trusted
* 中间 → unknown
* 低可信 → malicious

---

# 4. Step6：会员激励机制（保留）

---

## 4.1 仅 trusted 工人可成为会员

若工人类别：

* trusted → 可申请会员
* unknown → 不可加入
* malicious → 排除

---

## 4.2 会员任务划分

按任务权重排序，前比例任务划为会员任务：

$$
|\Gamma_t^{me}|=
round(|\Gamma_t|\cdot \theta)
$$

其中：

* $\theta = MEMBER_TASK_RATIO$

其余任务为普通任务。

---

## 4.3 PGRD 收益比较

会员方案：

$$
R_i^A=
n_i^M \bar r_i^M - f
$$

普通方案：

$$
R_i^B=
n_i^N \bar r_i^N
$$

参照损失：

$$
L_i=\max(0,R_i^A-R_i^B)
$$

会员概率：

$$
\psi_i=
\sigma\left(
\xi(R_i^A-R_i^B+\lambda L_i)
\right)
$$

若：

$$
\psi_i \ge \tau
$$

则成为会员。

---

# 5. Step7：LGSC 沉没成本留存机制（新增核心）

---

# 5.1 新增工人状态变量

每个工人新增：

```python
is_member
sunk_value
sunk_rate
bonus_count
period_cost_sum
cumulative_bonus
current_sunk_loss
```

---

# 5.2 核心思想

会员工人在持续参与任务过程中，会不断累积：

$$
S_i(t)
$$

若中途退出，则失去当前累计沉没值。

若达到阈值：

$$
S_i(t)\ge Y
$$

则获得奖励金：

$$
\Theta
$$

因此工人更倾向继续留在平台。

---

# 6. 沉没值累计（代码一致）

仅对：

* 本轮被选中；
* 且当前是会员

的工人更新。

设本轮执行任务成本：

$$
C_i^{round}(t)
$$

则：

$$
S_i(t+1)
========

S_i(t)+\rho_i(t)\cdot C_i^{round}(t)
$$

其中：

* $\rho_i(t)$ 为累计率（初始1）

---

# 7. 奖励金触发机制

若：

$$
S_i(t)\ge Y
$$

则：

* 发放奖励金 $\Theta$
* 清空当前沉没值

即：

$$
bonus_i=\Theta
$$

并执行：

$$
S_i(t)=0
$$

记录：

* `bonus_count +=1`
* `cumulative_bonus += Θ`

---

# 8. 累计率更新机制

奖励领取后：

$$
\rho_i(t+1)
===========

1+
\frac{\Theta G_i}
{\Theta G_i + C_i^{last}}
$$

其中：

* $G_i$：历史奖励次数
* $C_i^{last}$：本周期累计投入成本

含义：

> 长期坚持的会员，后续沉没值积累更快，更容易再次获得奖励。

---

# 9. 当前沉没损失值（代码一致）

若工人当前退出，将损失：

$$
H_i(t)=\frac{\Theta}{Y}S_i(t)
$$

代码记录为：

```python
current_sunk_loss
```

用于解释留存行为。

---

# 10. Step7 扩展退出概率模型（最关键）

原 Step6：

$$
p_i^{leave}
===========

\sigma(
\beta_0+\beta_1C_i-\beta_2R_i
)
$$

Step7 扩展为：

$$
p_i^{leave}
===========

\sigma\left(
\beta_0
+\beta_1 C_i
-\beta_2 \bar R_i
-\beta_3 m_i
-\beta_4 \frac{S_i}{Y}
\right)
$$

其中：

* $m_i=1$：会员
* $S_i/Y$：沉没进度

表示：

### 会员更不容易退出

$$
-\beta_3 m_i
$$

### 沉没值越高越不愿退出

$$
-\beta_4 S_i/Y
$$

---

# 11. 平台收益模型（代码一致）

每轮平台净收益：

$$
U_t=
V_t
+
F_t
---

## P_t

B_t
$$

其中：

* $V_t$：任务价值收益
* $F_t$：会员费收入
* $P_t$：支付给工人报酬
* $B_t$：奖励金支出

---

# 12. 每轮完整代码流程（真实执行顺序）

---

## Step A：读取任务与可用工人

得到：

* `round_tasks`
* `available_workers`

---

## Step B：执行会员决策（PGRD）

输出：

* member_count
* membership_fee_income
* bid_tasks_map

---

## Step C：CMAB 招募

在 `bid_tasks_map` 上执行：

* selected_worker_ids

---

## Step D：任务评价

统计：

* coverage_rate
* completion_rate
* avg_quality

---

## Step E：验证任务与 trust 更新

更新：

* trusted
* unknown
* malicious

---

## Step F：LGSC 更新

对会员工人：

* 累计 sunk_value
* 发放 bonus
* 更新 sunk_rate

---

## Step G：退出判定

根据新退出概率：

* worker leave / stay

---

## Step H：累计指标更新

输出 round_result。

---

# 13. round_result 新增字段（建议保留）

```python
member_count
trusted_member_count
membership_fee_income

bonus_payment
bonus_trigger_count

avg_sunk_value
avg_sunk_rate

num_active_workers
left_workers

avg_leave_probability

platform_utility
cumulative_platform_utility
```

---

# 14. 实验目标（Step7）

比较：

## B4 vs B5

其中：

* B4 = CMAB + Trust + PGRD
* B5 = CMAB + Trust + PGRD + LGSC

观察：

1. 留存率是否提升
2. active workers 是否更稳定
3. 平台收益是否继续增长
4. bonus 支出是否合理
5. 数据质量是否保持稳定

---

# 15. 理论预期结果

加入 LGSC 后：

### 留存率提高

$$
Retention_{B5}>Retention_{B4}
$$

### 活跃工人增加

$$
ActiveWorkers_{B5}>B4
$$

### 平台收益长期增长

短期可能因奖励金下降，长期回升：

$$
Utility_{longrun}(B5)>B4
$$

---

# 16. 最终论文创新点表达

本文提出一种面向群智感知平台的双阶段工人管理机制：

第一阶段通过 CMAB 与空间一致性验证筛选高可信工人；

第二阶段通过会员激励与沉没成本机制提高高质量工人的长期参与意愿，实现平台收益与工人稳定性的协同优化。

---

# 17. 当前代码评价（与你代码一致）

## 可以直接跑实验。

## 主线成立。

## 后续只需调参数与画图即可。

---

# 18. 你现在下一步该做什么

直接跑：

## B4 vs B5

然后把图发我，我帮你分析是否论文级结果。
