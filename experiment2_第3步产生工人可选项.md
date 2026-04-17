很好，这次我帮你做的是：

> ✅ **在你原文档基础上完整重写（不是简化版）**
> ✅ 保留你原有结构、详细程度
> ✅ 只在关键地方加入“稳定性 + 验证机制支撑”

我会直接给你一版**可以完全替换的 Step3 文档**（保持你现在这种详细风格）。

---

# 📄 修改完整版（Step3）

（已在你原文基础上修改）👇

---

# 📄 `experiment2_第3步产生工人可选项.md（修正版）`

---

# 1. 概述（Overview）

本步骤的目标是：

> 将 Step 1 的车辆轨迹数据与 Step 2 的任务数据进行匹配，生成**工人可选项（Worker Options）**

具体构建：

* 每个工人能执行哪些任务（可覆盖关系）
* 工人执行每个任务时的**实际质量 $q_{ij}$**
* 工人提交的任务数据（task_data）
* 工人的可用轮次（available_slots）

⚠️ **新增关键建模：**

本步骤同时引入：

* 任务真实值（ground truth）
* 工人稳定性（stability）

用于后续**验证任务信任机制**

---

# 2. 本步骤的核心作用

---

| 上游            | 本步骤 | 下游    |
| ------------- | --- | ----- |
| 轨迹数据          | ➜   | CMAB  |
| 任务数据          | ➜   | 覆盖/完成 |
| base_quality  | ➜   | 质量学习  |
| stability（新增） | ➜   | 信任验证  |

---

# 3. 输入数据

---

## 3.1 工人数据（Step 1）

`experiment2_vehicle.csv`

字段：

* `vehicle_id`
* `region_id`
* `start_time`
* `end_time`
* `cost`
* `init_category`
* `base_quality`

---

## 3.2 任务数据（Step 2）

`experiment2_tasks.csv`

字段：

* `task_id`
* `region_id`
* `slot_id`
* `start_time`
* `end_time`
* `required_workers`
* `weight`

---

# 4. 输出数据

---

## 输出文件

`experiment2_worker_options.json`

---

## 数据结构

```json
{
  "worker_001": {
    "cost": 12.5,
    "base_quality": 0.72,
    "stability": 0.3,
    "init_category": "trusted",
    "available_slots": [3,4,5],
    "tasks": [
      {
        "task_id": "t03_02",
        "task_start_time": 1800,
        "task_end_time": 2399,
        "quality": 0.68,
        "task_data": 23.5,
        "true_value": 22.8
      }
    ]
  }
}
```

---

# 5. 核心建模思想

---

# 5.1 覆盖条件（不变）

---

## 空间

$$region_i = region_j$$

---

## 时间

$$[start_i, end_i] \cap [start_j, end_j] \neq \emptyset$$

---

# 5.2 质量建模（CMAB使用）

---

$$q_{ij} = base_quality_i + \epsilon_{ij}$$

---

$$\epsilon_{ij} \sim \mathcal{N}(0, 0.05)$$

---

👉 限制：

$$q_{ij} \in [0,1]$$

---

# 5.3 新增：任务真实值（关键）

---

对每个任务：

$$x_j^{true} \sim U(0,1)$$

---

👉 含义：

```text
真实环境值（仅用于模拟，不被算法直接使用）
```

---

# 5.4 新增：稳定性建模（核心改动）

---

根据初始类别：

```python
if init_category == "trusted":
    stability = 0.3
else:
    stability = 1.0
```

---

## 🎯 含义

| 类型      | 含义    |
| ------- | ----- |
| trusted | 数据稳定  |
| unknown | 数据波动大 |

---

# 5.5 任务数据生成（核心）

---

$$x_{ij} = x_j^{true} + noise_{ij}$$

---

## 噪声：

$$noise_{ij} \sim \mathcal{N}(0, \sigma_i)$$

---

$$\sigma_i = (1 - base_quality_i) \cdot stability_i$$

---

# 🔥 关键解释

---

## trusted 工人：

```text
✔ 噪声小
✔ 数据集中
✔ 更一致
```

---

## unknown 工人：

```text
✔ 噪声大
✔ 数据分散
✔ 不稳定
```

---

# 🎯 最重要一句话（新增）

> trusted 工人不一定更准确，但更稳定，因此可以作为验证任务的参考基准。

---

# 5.6 时间片（轮次）

---

$$slot = \left\lfloor \frac{start_time}{SLOT_SEC} \right\rfloor$$

---

# 6. 参数

---

| 参数            | 默认值        |
| ------------- | ---------- |
| SLOT_SEC      | 600        |
| SIGMA_QUALITY | 0.05       |
| DATA_SCALE    | 不再使用（已改模型） |
| RANDOM_SEED   | 1          |

---

# 7. 处理流程（Step-by-Step）

---

## Step 1：加载数据

---

## Step 2：按 region 分组任务

---

## Step 3：生成任务真实值

```python
true_value = np.random.uniform(0,1)
```

---

## Step 4：遍历工人

---

## Step 5：判断覆盖

---

## Step 6：生成 q_ij

---

## Step 7：生成 task_data（修改版）

```python
sigma = (1 - base_quality) * stability
task_data = true_value + np.random.normal(0, sigma)
```

---

## Step 8：记录 slot

---

## Step 9：保存 JSON

---

# 8. 输出数据性质

---

现在数据具备：

```text
✔ 能力（q_ij）
✔ 稳定性（stability）
✔ 数据一致性（task_data）
✔ ground truth（隐藏）
```

---

# 9. 与后续步骤关系

---

## Step4（CMAB）

使用：

* q_ij
* cost

---

## Step5（Trust）

使用：

* task_data
* true_value（不直接用）
* trusted 稳定性

---

# 10. 本步骤的关键升级（新增）

---

本版本相比原始版本：

---

## ✔ 新增：

```text
✔ 稳定性（trust基础）
✔ ground truth（验证基础）
✔ 数据一致性建模
```

---

## ✔ 解决：

```text
✔ trusted 为什么能作为参考
✔ 验证机制为何成立
```

---

# 11. 伪代码（更新版）

```text
load workers
load tasks

generate true_value for tasks

for worker:
    assign stability based on category

    for each segment:
        if match task:
            generate q_ij
            generate task_data (new model)

save JSON
```

---

# 12. 总结（升级版）

---

> 本步骤在传统质量建模基础上引入稳定性与真实值建模，使得可信工人具有更高一致性，为后续验证任务中的信任度更新提供可靠依据。

---

# ✅ 说明

你刚才那份原文档我已经完整对齐改造了（不是删减版）：

👉 保留了你所有结构
👉 只改了三处关键地方：

1. **task_data模型（核心）**
2. **加入stability**
3. **加入true_value**

---

# 🚀 下一步

如果你确认这版 Step3 OK，我可以帮你做：

👉 **Step5 同样“完整版重写（不缩水版）”**

会完全对齐你老师的验证任务逻辑 👍
