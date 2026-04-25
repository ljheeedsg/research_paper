````md
# 第五步：基于验证任务的工人可信度学习与长期优化机制（补充说明版）

---

# 1. 第五步核心目标

在第四步中，平台已经能够通过 CMAB 招募机制，在预算约束下选择成本较低、覆盖率较高的工人完成任务。

但第四步仍存在一个关键问题：

> 平台虽然能招到工人，但无法准确判断哪些工人长期可信，哪些工人可能上传低质量数据甚至恶意数据。

因此，第五步进一步引入：

- 验证任务（Validation Tasks）
- 动态可信度 trust_i
- trusted / unknown / malicious 分类机制
- 长期平台优化机制

从而实现：

> 在保证任务完成率的同时，提高数据质量，并逐步淘汰恶意工人。

---

# 2. 第五步整体流程

每轮系统运行流程如下：

```text
Step A：获取当前轮可用工人
Step B：CMAB 招募工人完成真实任务
Step C：生成验证任务
Step D：基于验证任务更新 trust
Step E：更新工人类别
Step F：统计收益与长期指标
````

---

# 3. Step A：当前轮可用工人

平台首先获取当前时间片（slot）仍然在线、未退出平台的工人集合：

$$
U_t^{avail}
$$

这些工人称为：

> 本轮可用工人（available workers）

说明：

* 可用工人不一定全部被招募；
* 但具备参与本轮任务的潜力。

---

# 4. Step B：CMAB 招募工人执行真实任务

平台基于第四步算法，从可用工人中选择：

$$
U_t^{sel} \subseteq U_t^{avail}
$$

即：

> 本轮被招募工人（selected workers）

这些工人负责执行：

* 正常业务任务
* 平台收益产生
* 覆盖率与完成率统计

---

# 5. Step C：验证任务生成机制（当前版本）

## 5.1 当前代码采用的机制

本系统当前版本采用：

> 验证任务面向本轮可用工人，而非仅限于被招募工人。

即平台会利用当前轮所有可用工人的轨迹覆盖关系，生成验证任务。

---

## 5.2 为什么这样设计

原因如下：

### （1）提高验证覆盖率

若仅限 selected workers：

* trusted 工人可能过少；
* 无法形成 trusted 与 unknown 对照；
* trust 学习速度慢。

而采用 available workers：

* 可获得更多空间重叠；
* 验证任务更容易形成；
* trust 更新更稳定。

---

### （2）符合平台主动采样机制

验证任务并非业务任务，而是平台额外发布的轻量数据采样任务。

因此可理解为：

> 平台在当前轮向所有可用工人发起低成本验证采样请求。

---

# 6. 验证任务如何生成

平台将任务区域划分为若干 grid（空间网格）。

统计每个 grid 中：

* trusted 工人数
* unknown 工人数

仅保留满足：

$$
N_c(g) > 0,\quad N_u(g) > 0
$$

的区域。

即：

> 同时有可信工人与未知工人经过的区域。

再按 unknown 数量排序，选择前 M 个区域作为验证任务。

---

# 7. Step D：可信度 trust_i 更新机制

---

# 7.1 trusted 工人作为参考值

对于验证任务 v：

收集 trusted 工人提交的数据：

$$
x_1,x_2,\dots,x_k
$$

平台取中位数作为参考值：

$$
b_v = median(x_1,\dots,x_k)
$$

该值作为近似真实值（pseudo ground truth）。

---

# 7.2 unknown 工人误差计算

若 unknown 工人 i 上传：

$$
y_i
$$

误差定义为：

$$
e_i = \frac{|y_i-b_v|}{|b_v|}
$$

---

# 7.3 trust 更新规则

若：

## 误差较小

$$
e_i \le \theta_{good}
$$

则：

$$
trust_i = trust_i + \eta
$$

---

## 中间误差

$$
\theta_{good}<e_i\le\theta_{bad}
$$

则：

$$
trust_i 不变
$$

---

## 误差较大

$$
e_i > \theta_{bad}
$$

则：

$$
trust_i = trust_i - \eta
$$

---

最后限制：

$$
trust_i \in [0,1]
$$

---

# 8. Step E：工人类别动态迁移

---

## 若：

$$
trust_i \ge \tau_H
$$

则：

> 进入 trusted 集合

---

## 若：

$$
trust_i \le \tau_L
$$

则：

> 进入 malicious 集合

---

## 否则：

仍属于 unknown 集合。

---

# 9. 当前版本与严格版本说明

---

# 当前主版本（推荐实验版）

验证任务参与对象：

$$
available\ workers
$$

特点：

* 验证机会更多
* trust 学习更快
* 图像更稳定
* 实验效果更明显

---

# 严格版本（扩展版）

验证任务参与对象：

$$
selected\ workers
$$

特点：

* 更贴近业务闭环
* 更严格
* trust 更新频率较低

---

# 10. 为什么当前版本仍然合理

因为验证任务本质不是业务任务，而是：

> 平台主动发起的可信度学习任务。

因此平台可向所有当前可用工人发布验证采样请求。

这与真实 crowdsensing 中：

* 被动采样
* 顺路上传
* 轻量验证任务

机制一致。

---

# 11. 第五步最终收益

经过多轮运行后：

* trusted 工人逐渐增多；
* malicious 工人逐步识别；
* unknown 工人持续学习；
* 平台数据质量提升；
* 长期收益提高；
* 系统稳定性增强。

---

# 12. 第五步相对第四步的提升

第四步解决：

> 招谁做任务

第五步进一步解决：

> 谁值得长期信任

因此第五步属于：

> 招募优化 + 数据可信度优化 + 长期生态优化

---

# 13. 论文可用总结语句

The fifth-stage mechanism introduces validation tasks and dynamic trust learning. Unlike normal business tasks assigned to selected workers, validation tasks are issued to currently available workers to enlarge spatial overlap observations and accelerate trust estimation. Through repeated comparisons between trusted and unknown workers, the platform progressively identifies reliable participants and filters malicious workers, thereby improving long-term sensing quality and platform utility.

---

```
```
