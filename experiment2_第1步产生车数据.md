# 📄 `experiment2_step1_generate_vehicles.md`（最终完整版）

---

# 1. 概述（Overview）

本步骤的目标是：

> 从原始出租车轨迹数据中构建群智感知实验的**工人基础数据集（Worker Dataset）**

该数据集包含：

* 工人的时空轨迹（trajectory segments）
* 工人的基础属性（成本、初始类别）
* 工人的真实能力（base_quality）

该数据将作为后续任务生成、质量建模、工人招募、信任验证与激励机制的统一输入。

---

# 2. 核心建模思想（必须理解）

本步骤遵循两个关键建模原则：

---

## 2.1 质量与信任解耦（核心）

### 质量（Quality）

$$base\_quality_i$$

表示：

> 工人的真实感知能力（设备、技术、稳定性）

---

### 信任（Trust）

表示：

> 工人是否诚实、数据是否可靠（后续学习得到）

---

## ❗关键关系

$$\text{quality} \neq \text{trust}$$

* 高质量 ≠ 高可信
* 低质量 ≠ 恶意

---

## 2.2 本步骤只生成"真实世界"，不做"算法判断"

| 内容            | 是否在本步骤 |
| ------------- | ------ |
| base_quality  | ✅      |
| init_category | ✅      |
| trust_i       | ❌      |
| malicious     | ❌      |

---

# 3. 本步骤职责（Scope）

---

## 3.1 本步骤负责

1. 数据清洗与解析
2. 高密区域提取
3. 空间网格划分
4. 构建轨迹段
5. 合并同区域段
6. 按固定时间片切分
7. 工人重编号
8. 生成工人属性：

   * cost
   * init_category
   * base_quality ⭐

---

## 3.2 本步骤不负责

* 不生成任务
* 不计算任务质量
* 不更新信任度
* 不识别恶意工人
* 不执行招募

---

# 4. 输入数据

## 文件

`dataset/beijing_300_cars_2008-02-03.csv`

---

## 字段（自动识别）

| 逻辑字段 | 可接受名称            |
| ---- | ---------------- |
| ID   | taxi_id / id     |
| 时间   | time / timestamp |
| 纬度   | lat              |
| 经度   | lon              |

---

# 5. 输出数据

## 文件

`experiment2_vehicle.csv`

---

## 字段定义

| 字段            | 含义     |
| ------------- | ------ |
| vehicle_id    | 工人ID   |
| region_id     | 网格编号   |
| start_time    | 开始时间   |
| end_time      | 结束时间   |
| cost          | 成本     |
| init_category | 初始类别   |
| base_quality  | 真实能力 ⭐ |

---

# 6. 参数设置

| 参数            | 默认值 |
| ------------- | --- |
| GRID_X_NUM    | 10  |
| GRID_Y_NUM    | 10  |
| SLOT_SEC      | 600 |
| COST_MIN      | 5   |
| COST_MAX      | 20  |
| TRUSTED_RATIO | 0.3 |
| RANDOM_SEED   | 1   |

---

# 7. 质量建模（重点）

---

## 7.1 base_quality 定义

每个工人有：

$$base\_quality_i \in [0,1]$$

---

## 7.2 生成方式（独立于信任）

采用混合分布：

```python
z = random choice

if z == high:
    base_quality ~ U(0.75, 0.95)
elif z == medium:
    base_quality ~ U(0.45, 0.75)
else:
    base_quality ~ U(0.1, 0.45)
```

---

## 7.3 含义解释

| 类型  | 含义     |
| --- | ------ |
| 高质量 | 好设备+稳定 |
| 中质量 | 一般水平   |
| 低质量 | 噪声大    |

---

## ❗注意

* 与 `init_category` 无关
* 平台不可见

---

# 8. 初始工人类别

---

## 定义

| 类别      | 含义       |
| ------- | -------- |
| trusted | 已知可信（种子） |
| unknown | 未知       |

---

## 生成方式

```python
if rand < TRUSTED_RATIO:
    trusted
else:
    unknown
```

---

## 重要说明

* 这里只是"已知可信"，不是"高质量"
* malicious 不在本步骤出现

---

# 9. 处理流程（核心）

---

## Step 1：读取数据

* 解析字段
* 转换时间为秒

---

## Step 2：高密区域提取

* 使用分位数
* 平移区域

---

## Step 3：网格划分

$$region = g_y \cdot GRID\_X + g_x$$

---

## Step 4：构建轨迹段

* 同车排序
* 相邻点构成段

---

## Step 5：合并同区域段

---

## Step 6：时间片切分（关键）

$$slot = \left\lfloor \frac{time}{SLOT\_SEC} \right\rfloor$$

---

## Step 7：重编号

```text
vehicle_id = 1,2,3...
```

---

## Step 8：生成属性 ⭐

---

### cost

```python
cost ~ U(5,20)
```

---

### init_category

```python
trusted / unknown
```

---

### base_quality

独立生成（见第7节）

---

## Step 9：输出

CSV 文件

---

# 10. 输出数据性质

生成数据具有：

* 时间离散（slot）
* 空间离散（grid）
* 工人能力差异（base_quality）
* 信任未知（init_category）

---

# 11. 与下一步接口

Step 2 使用：

| 字段            | 用途      |
| ------------- | ------- |
| region_id     | 任务空间    |
| time          | 任务时间    |
| base_quality  | 生成 q_ij |
| cost          | 招募      |
| init_category | 初始信任    |

---

# 12. 关键逻辑总结

---

## 现实世界

$$base\_quality \rightarrow q_{ij}$$

---

## 平台学习

$$q_{ij} \rightarrow \hat{q}_i$$

---

## 招募优化

$$\hat{q}_i \rightarrow selection$$

---

# 13. 伪代码

```text
load data
clean data

extract region
grid partition

group by taxi
build segments
merge segments

split by SLOT

reindex vehicles

for each vehicle:
    assign cost
    assign init_category
    assign base_quality

save CSV
```
