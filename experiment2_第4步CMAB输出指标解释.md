# 实验结果指标解释文档（Markdown 数学公式版）

## 一、文档目的

本文档用于解释当前代码运行后生成的各项实验结果指标，包括：

1. 任务效果类指标
2. 数据质量类指标
3. 平台效益类指标
4. 工人留存类指标
5. 招募规模类指标

所有解释均基于当前代码真实实现逻辑。

---

# 二、任务效果类指标

---

## 1. Coverage Rate（任务覆盖率）

### 定义

表示当前轮中，有多少任务至少被 1 名工人执行。

### 计算方式

设：

* 总任务数为 $M_t$
* 被覆盖任务数为 $M_t^{cov}$

则：

$$
CoverageRate(t)=\frac{M_t^{cov}}{M_t}
$$

### 判定标准

只要某任务有至少一个被选中工人执行，即视为被覆盖。

### 指标意义

衡量平台是否成功将任务分配出去。

---

## 2. Completion Rate（任务完成率）

### 定义

表示当前轮中，真正达到人数要求且质量达标的任务比例。

### 计算方式

设完成任务数为 $M_t^{comp}$，则：

$$
CompletionRate(t)=\frac{M_t^{comp}}{M_t}
$$

### 任务完成条件

任务 $j$ 完成需同时满足：

$$
num_workers_j \ge required_workers_j
$$

且

$$
avg_quality_j \ge DELTA
$$

其中：

* `required_workers`：任务所需工人数
* `DELTA`：最低质量阈值

---

# 三、数据质量类指标

---

## 3. Round Data Quality（每轮数据质量）

### 定义

表示当前轮所有被覆盖任务产生的数据平均质量。

### 计算方式

设被覆盖任务集合为 $T_t^{cov}$，任务最终质量为 $Q_j(t)$，则：

$$
RDQ(t)=\frac{\sum_{j\in T_t^{cov}}Q_j(t)}{|T_t^{cov}|}
$$

### 单任务质量计算

若多人执行任务：

$$
Q_j(t)=\frac{1}{m}\sum_{k=1}^{m}q_{jk}
$$

其中：

* $m$：参与该任务工人数
* $q_{jk}$：第 $k$ 位工人的真实质量

### 指标意义

衡量当前轮招募工人的整体数据可靠性。

---

## 4. Cumulative Data Quality（累计数据质量）

### 定义

表示从第1轮到当前轮所有被覆盖任务的数据质量总体平均值。

### 计算方式

$$
CDQ(t)=
\frac{
\sum_{\tau=1}^{t}\sum_{j\in T_\tau^{cov}}Q_j(\tau)
}{
\sum_{\tau=1}^{t}|T_\tau^{cov}|
}
$$

### 指标意义

衡量平台长期运行中的平均数据质量水平。

---

# 四、平台效益类指标

---

## 5. Platform Payment（平台支付成本）

### 定义

当前轮支付给被招募工人的总报酬。

### 计算方式

设被选工人集合为 $S_t$，工人报价为 $bid_i$，则：

$$
PlatformPayment(t)=\sum_{i\in S_t}bid_i
$$

### 说明

只要工人被招募，即支付报价，不依赖任务是否完成。

---

## 6. Platform Task Value（平台任务价值）

### 定义

当前轮任务产生的总数据价值。

### 单任务价值计算

设任务权重为 $w_j$，最高真实质量为 $best_quality_j$，则：

$$
Value_j=\rho \cdot w_j \cdot best_quality_j
$$

其中：

* $\rho$：收益缩放系数（代码中常数）

### 总价值

$$
PlatformTaskValue(t)=\sum_j Value_j
$$

### 说明

只要任务被执行并产生数据，即可产生价值，不要求任务必须 completed。

---

## 7. Platform Utility（平台效益）

### 定义

平台当前轮净收益。

### 计算方式

$$
PlatformUtility(t)=PlatformTaskValue(t)-PlatformPayment(t)
$$

### 指标意义

衡量平台该轮运行是否盈利。

---

# 五、工人留存类指标

---

## 8. Num Active Workers（活跃工人数）

### 定义

当前轮结束后，仍未退出平台的工人数。

### 计算方式

$$
ActiveWorkers(t)=#{i:is_active_i=True}
$$

### 指标意义

衡量平台当前劳动力池规模。

---

## 9. Num Left Workers This Round（本轮退出人数）

### 定义

当前轮结束时，新退出平台的工人数。

### 指标意义

衡量该轮工人流失情况。

---

## 10. Cumulative Left Workers（累计退出人数）

### 定义

从第1轮到当前轮，总退出工人数。

$$
CumulativeLeft(t)=#{i:is_active_i=False}
$$

### 指标意义

衡量长期工人流失规模。

---

## 11. Avg Leave Probability（平均退出概率）

### 定义

本轮被选中工人的平均退出风险。

### 单工人退出概率计算

$$
p_i^{leave}=
\sigma(\beta_0+\beta_1C_i-\beta_2R_i)
$$

其中：

* $C_i$：累计成本
* $R_i$：平均收益

Sigmoid 函数：

$$
\sigma(x)=\frac{1}{1+e^{-x}}
$$

### 平均退出概率

$$
AvgLeaveProb(t)=\frac{1}{|S_t|}\sum_{i\in S_t}p_i^{leave}
$$

### 指标意义

衡量本轮工人整体离开平台的风险水平。

---

# 六、招募规模类指标

---

## 12. Selected Workers Number（招募人数）

### 定义

当前轮被平台选中的工人数。

$$
SelectedNum(t)=|S_t|
$$

### 指标意义

衡量平台当前轮招募规模。

---

## 13. Available Workers Number（可用工人数）

### 定义

当前时间片中满足：

1. 工人轨迹可出现
2. 尚未退出平台

的工人数。

### 指标意义

衡量当前轮真实候选工人池大小。

---

# 七、指标关系总结

## 高 Coverage + 高 Completion

说明招募效果好。

## 高 Data Quality

说明选中的工人质量高。

## 高 Platform Utility

说明平台收益好。

## 高 Active Workers + 低 Leave Probability

说明留存机制有效，平台长期稳定。

---

# 八、一句话总结

本代码实现同时衡量：

* 任务是否被完成
* 数据质量是否可靠
* 平台是否盈利
* 工人是否持续留存
* 系统是否长期稳定运行
