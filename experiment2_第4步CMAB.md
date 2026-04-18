# 第4步：论文对齐版 CMAB 招募

## 1. 目标

本步骤对齐论文《Combinatorial Multi-Armed Bandit Based Unknown Worker Recruitment in Heterogeneous Crowdsensing》的核心思想，在每个轮次中：

- 工人报告自己的任务选项集与报价；
- 平台只掌握工人的历史质量估计，不知道真实 `base_quality`；
- 在预算约束下，逐步选择能带来最大边际完成质量增益的工人。

本步骤不再把“覆盖”直接当“完成”。  
覆盖率只是补充统计指标，论文版主目标是加权完成质量。

## 2. 输入

输入文件为 [experiment2_worker_options.json](C:\Users\ASUS\Desktop\research_paper\experiment2_worker_options.json)。

对每个工人 `i`，平台可见：

- 报价 `c_i`（代码中为 `bid_price`）
- 当前轮可做任务集合 `S_i(t)`
- 历史观测次数 `n_i`
- 历史平均质量 `\bar{q}_i`

平台不可见：

- `base_quality_i`

## 3. 任务完成质量

设本轮被选中的工人集合为 $A_t$。  
对于任务 $j$，其实际完成质量定义为：

$$Q_j(t) = \max_{i \in A_t, j \in S_i(t)} q_{ij}$$

也就是说：

- 同一任务可被多个工人覆盖；
- 任务质量取这些工人中的最大质量；
- 因而“任务覆盖”与“任务完成质量”是两个不同层次的概念。

## 4. 论文版目标函数

设任务 $j$ 的权重为 $w_j$，则本轮总的加权完成质量为：

$$WCQ_t = \sum_j w_j \cdot Q_j(t)$$

这是本步骤的核心目标函数。  
平台在招募时，目标就是尽量让 `WCQ_t` 变大。

## 5. UCB 质量估计

对于工人 $i$，平台维护历史平均质量 $\bar{q}_i(t-1)$ 和累计观测次数 $n_i(t-1)$。  
其本轮估计质量采用 UCB：

$$\hat{q}_i(t) = \bar{q}_i(t-1) + \sqrt{\alpha \cdot \ln(T_{obs} + 1) / n_i(t-1)}$$

其中：

- $T_{obs}$ 是全局累计学习次数；
- $\alpha$ 是探索系数。

对未被观测过的工人，当前实现使用统一的乐观初值：

$$\hat{q}_i(t) = 1.0$$

这样在第一轮会自然退化成“任务数 / 报价”式的排序，和论文文字描述是一致的。

## 6. 公式 12 对齐实现

在轮内贪心过程中，平台维护当前任务的“已达到估计质量”：

$$Q_j^{cur}(t)$$

初始时所有任务都为 $0$。  
若把工人 $i$ 加入当前已选集合，则他对任务 $j$ 的边际贡献为：

$$\max(0, \hat{q}_i(t) - Q_j^{cur}(t))$$

因此，工人 $i$ 的边际增益定义为：

$$\Delta_i(t) = \sum_{j \in S_i(t)} w_j \cdot \max(0, \hat{q}_i(t) - Q_j^{cur}(t))$$

工人的性价比评分为：

$$score_i(t) = \frac{\Delta_i(t)}{c_i}$$

轮内每一步都选择 `score_i(t)` 最大的工人，直到：

- 预算不足，或
- 没有工人还能带来正的边际增益。

这就是当前代码中对论文公式 12 的实现口径。

## 7. 轮次流程

每一轮按以下顺序执行：

1. 提取本轮任务集合 $T_t$。
2. 提取本轮可用工人集合 $W_t$。
3. 计算每个候选工人的 $\hat{q}_i(t)$。
4. 基于当前 $Q_j^{cur}(t)$ 计算每个工人的边际增益 $\Delta_i(t)$。
5. 选择 $\Delta_i(t) / c_i$ 最大的工人加入本轮集合。
6. 更新 $Q_j^{cur}(t)$。
7. 预算耗尽或无正增益后停止。
8. 用真实 $q_{ij}$ 计算本轮实际任务质量 $Q_j(t)$。
9. 更新工人的历史观测次数与平均质量。

### 轮次流程图

```mermaid
flowchart TD
    A[开始轮次] --> B[提取本轮任务集合 T_t]
    B --> C[提取本轮可用工人集合 W_t]
    C --> D[计算每个候选工人的 q_hat_i(t)]
    D --> E[初始化 Q_j^cur(t) = 0 for all j]
    E --> F{预算充足且有正增益工人?}
    F -->|是| G[选择 score_i(t) 最大的工人]
    G --> H[加入工人到 A_t]
    H --> I[更新 Q_j^cur(t) for j in S_i(t)]
    I --> F
    F -->|否| J[用真实 q_ij 计算 Q_j(t)]
    J --> K[更新工人历史]
    K --> L[计算指标: coverage_rate, completion_rate, avg_quality]
    L --> M[结束轮次]
```

## 8. 输出指标

### 8.1 主看指标

- `coverage_rate`

表示本轮至少被一个工人覆盖的任务比例：

$$coverage\_rate = \frac{covered\_tasks}{total\_tasks}$$

- `completion_rate`

当前代码中把它作为“系统判断后的完成率”来展示：

$$completion\_rate = \frac{|\{j : Q_j(t) \geq \delta\}|}{|\mathcal{T}_t|}$$

也就是说：

- 先看任务是否被覆盖；
- 工人提交数据后，系统再根据当前质量条件判断任务是否完成；
- 这里不再单独把“达标率”拆成另一套主图，而是直接把它并入 `completion_rate` 的口径。

- `avg_quality`

表示本轮被覆盖任务的平均实际质量。

这三个指标分别回答：

- `coverage_rate`
  - 表示任务有没有被至少一个被招募工人覆盖
  - 它只回答“有没有人做”，不回答“做得好不好”

- `completion_rate`
  - 表示系统判断后，有多少任务最终可以算完成
  - 它回答“任务最后成没成”

- `avg_quality`
  - 表示本轮所有被覆盖任务的平均最终质量
  - 只对已经被覆盖的任务求平均

### 8.2 内部保留指标

为了保留与论文原目标函数的一致性，代码内部仍然保留：

- `weighted_completion_quality`
  - 表示本轮总加权完成质量
  - 即：

$$\sum_j w_j \cdot Q_j(t)$$

- `normalized_completion_quality`
  - 表示归一化后的加权完成质量
  - 即：

$$\frac{\sum_j w_j \cdot Q_j(t)}{\sum_j w_j}$$

它们仍会写入结果 JSON，便于以后需要时做附录分析，但不再作为当前这版实验的主展示图。

### 8.3 输出文件怎么看

第 4 步现在会同时生成两套图：

- `experiment2_cmab_*`
  - 论文版 CMAB 招募结果
- `experiment2_random_*`
  - 随机招募基线结果

两套图的指标含义完全相同，唯一差别只是招募策略不同。

#### 1. 单轮指标图

- `experiment2_cmab_coverage_rate.png`
- `experiment2_random_coverage_rate.png`
  - 每一轮的覆盖率

- `experiment2_cmab_completion_rate.png`
- `experiment2_random_completion_rate.png`
  - 每一轮的完成率

- `experiment2_cmab_avg_quality.png`
- `experiment2_random_avg_quality.png`
  - 每一轮被覆盖任务的平均质量

#### 2. 累计指标图

- `experiment2_cmab_cumulative_coverage_rate.png`
- `experiment2_random_cumulative_coverage_rate.png`
  - 从第 1 轮累计到当前轮的覆盖率

- `experiment2_cmab_cumulative_completion_rate.png`
- `experiment2_random_cumulative_completion_rate.png`
  - 从第 1 轮累计到当前轮的完成率

- `experiment2_cmab_cumulative_avg_quality.png`
- `experiment2_random_cumulative_avg_quality.png`
  - 从第 1 轮累计到当前轮的整体平均数据质量

#### 3. 结果文件

- [experiment2_cmab_round_results.json](C:\Users\ASUS\Desktop\research_paper\experiment2_cmab_round_results.json)
  - 记录每一轮的详细结果

- [experiment2_cmab_summary.json](C:\Users\ASUS\Desktop\research_paper\experiment2_cmab_summary.json)
  - 记录整体汇总指标

- [experiment2_random_round_results.json](C:\Users\ASUS\Desktop\research_paper\experiment2_random_round_results.json)
  - 记录随机招募基线每一轮的详细结果

- [experiment2_random_summary.json](C:\Users\ASUS\Desktop\research_paper\experiment2_random_summary.json)
  - 记录随机招募基线的整体汇总指标

### 8.4 看图时的建议

如果你后面要做论文分析，建议优先这样看：

- 比“任务覆盖能力”时看 `coverage_rate`
- 比“系统最终完成效果”时看 `completion_rate`
- 比“数据本身质量”时看 `avg_quality`

也就是说：

- `coverage_rate` 不是 `completion_rate`
- `completion_rate` 表示系统判断后的完成情况
- `avg_quality` 表示整体数据质量
- 当前主展示里只保留“覆盖率、完成率、整体数据质量”三类指标

## 9. 本步骤和后续步骤的边界

第 4 步只负责：

- 预算约束下的招募；
- 最大化任务加权完成质量；
- 主展示中输出覆盖率、完成率和整体数据质量。

第 5 步以后再处理：

- `task_data` 驱动的信任验证；
- 不可信工人筛除；
- 可信工人长期激励。

因此，当前这版实验展示里，最推荐直接看三件事：

- 覆盖率有没有提高
- 系统判断后的完成率有没有提高
- 整体数据质量有没有提高
