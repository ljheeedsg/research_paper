# 第一步：产生可用工人数据（完整代码对应版文档）

---

# 1. 实验目标

本步骤的目标是：从原始车辆轨迹点数据中，提取能够用于后续群智感知实验的**可用工人轨迹段数据**，并为每位工人初始化基础属性，用于后续任务生成、工人招募、可信验证、奖励分配等实验模块。

输出结果中的每一条记录表示：

> 某位工人在某个时间段内，位于某个空间区域，可参与群智感知任务。

同时，每位工人具备：

* 工人编号 `vehicle_id`
* 所属区域 `region_id`
* 可用时间段 `start_time, end_time`
* 报价 `cost`
* 初始真实类别 `init_category`
* 基础质量 `base_quality`

---

# 2. 输入数据

输入文件：

```text
dataset/beijing_300_cars_2008-02-03.csv
```

该数据集为北京出租车轨迹数据，每一行表示一个车辆在某一时刻的位置点。

通常包含字段：

* 车辆编号
* 时间戳
* 纬度
* 经度

程序支持自动识别列名：

| 数据字段 | 支持列名                        |
| ---- | --------------------------- |
| 车辆编号 | taxi_id / taxiid / id       |
| 时间戳  | time_sec / time / timestamp |
| 纬度   | lat / latitude              |
| 经度   | lon / longitude             |

若缺少必要列，则程序报错终止。

若某一行格式异常，则自动跳过。

---

# 3. 输出数据

本步骤输出两个文件：

---

## 3.1 工人轨迹段文件

```text
experiment2_vehicle.csv
```

字段如下：

| 字段名           | 含义          |
| ------------- | ----------- |
| vehicle_id    | 工人编号（重新编号后） |
| region_id     | 所属网格区域编号    |
| start_time    | 开始可用时间      |
| end_time      | 结束可用时间      |
| cost          | 工人报价        |
| init_category | 初始真实类别      |
| base_quality  | 基础质量        |

---

## 3.2 网格划分图

```text
experiment2_grid_partition.png
```

图中展示：

* 实验区域位置
* 网格划分情况
* 点密度热力图

---

# 4. 代码参数（与代码完全一致）

## 空间参数

```python
LOW_PERCENTILE = 1
HIGH_PERCENTILE = 99

SHIFT_LON = -0.08
SHIFT_LAT = -0.08

GRID_X_NUM = 10
GRID_Y_NUM = 10
```

表示：

* 取经纬度 1% ~ 99% 分位点作为密集区域
* 向西南方向平移 0.08 度
* 划分为 10 × 10 网格

---

## 成本参数

```python
COST_MIN = 5
COST_MAX = 20
```

即：

$cost_i \sim U(5,20)$


---

## 工人类别比例

```python
TRUSTED_RATIO = 0.2
MALICIOUS_RATIO = 0.4
```

因此：

* trusted：20%
* malicious：40%
* unknown：40%

---

## 时间片参数

```python
SLOT_SEC = 600
```

即：

> 每 600 秒（10 分钟）为一个时间片。

---

## 随机种子

```python
RANDOM_SEED = 100
```

保证实验可复现。

---

## 基础质量参数

### trusted

```python
0.80 ~ 0.90
```

### unknown

```python
0.60 ~ 1.00
```

### malicious

```python
0.10 ~ 0.45
```

---

# 5. 整体流程

代码执行流程如下：

```text
读取轨迹点
→ 选取实验区域
→ 平移区域
→ 网格划分
→ 点映射到区域
→ 生成轨迹段
→ 合并连续区域段
→ 时间片切割
→ 工人编号重映射
→ 分配属性
→ 输出CSV与图像
```

---

# 6. 详细实现逻辑

---

# 6.1 读取原始轨迹点

程序读取 CSV 文件，并提取：

```text
(orig_id, time_sec, lat, lon)
```

其中：

* `orig_id`：原始车辆编号
* `time_sec`：时间戳（秒）
* `lat`：纬度
* `lon`：经度

统计：

* 总轨迹点数量
* 不同车辆数量

---

# 6.2 构建实验区域

提取所有点的经纬度数组。

计算分位点：

$lon_{min}=P_1(lon)$

$lon_{max}=P_{99}(lon)$


$lat_{min}=P_1(lat)$

$lat_{max}=P_{99}(lat)$


得到原始高密度矩形区域。

---

# 6.3 区域平移

代码将矩形中心平移：

$center_lon'=center_lon-0.08$

$center_lat'=center_lat-0.08$


即整体向西南移动。

最终形成新的实验区域：

```text
[lon_min_new, lon_max_new]
[lat_min_new, lat_max_new]
```

---

# 6.4 网格划分

将实验区域划分为：

$10 \times 10 = 100$

个网格。

每个网格步长：

$step_{lon}=\frac{lon_{max}-lon_{min}}{10}$

$step_{lat}=\frac{lat_{max}-lat_{min}}{10}$


---

# 6.5 轨迹点映射到区域

若点在实验区域内，则计算：

$gx=\left\lfloor \frac{lon-lon_{min}}{step_{lon}} \right\rfloor$

$gy=\left\lfloor \frac{lat-lat_{min}}{step_{lat}} \right\rfloor$


区域编号：

$region_id = gy \times 10 + gx$


范围：

```text
0 ~ 99
```

每个点转化为：

```text
(orig_id, time, region_id)
```

---

# 6.6 构建原始轨迹段

对于同一辆车，按时间排序。

若相邻两点为：

```text
(t_k, region_k)
(t_{k+1}, region_{k+1})
```

则生成轨迹段：

* 区域 = `region_k`
* 开始时间：

首段：

```text
t_k
```

其余段：

```text
t_k + 1
```

* 结束时间：

```text
t_{k+1}
```

即：

```text
(orig_id, region_id, start, end)
```

---

# 6.7 合并连续同区域轨迹段

若某车辆连续多个轨迹段属于同一区域：

```text
region_id 相同
```

则合并为更长时间段：

```text
(start_old, end_new)
```

减少数据冗余。

---

# 6.8 时间片切割（600秒）

将长轨迹段切成不跨时间片边界的短段。

代码采用**闭区间整数时间表示**。

例如：

```text
0~600
601~1200
1201~1800
```

若轨迹段跨越多个 slot，则拆分为多个子段。

例如：

原段：

```text
520 ~ 1350
```

切割后：

```text
520~600
601~1200
1201~1350
```

---

# 6.9 工人重新编号

原始车辆编号可能不连续。

程序按顺序重新编号：

```text
1,2,3,...,N
```

生成：

```text
vehicle_id
```

---

# 6.10 工人属性初始化

---

## ① 报价 cost

每位工人生成一次固定报价：

$cost_i \sim U(5,20)$


同一工人的所有轨迹段共享该报价。

---

## ② 初始真实类别 init_category

随机生成：

若随机数 `r`：

### trusted

$r<0.2$

### malicious

$0.2 \le r < 0.6$


### unknown

其余情况。

即：

| 类别        | 比例  |
| --------- | --- |
| trusted   | 20% |
| malicious | 40% |
| unknown   | 40% |

---

## ③ 基础质量 base_quality

### trusted：

$U(0.80,0.90)$

### unknown：

$U(0.60,1.00)$

### malicious：

$U(0.10,0.45)$


说明：

* trusted 整体质量较高
* unknown 波动较大
* malicious 质量较低

---

# 7. 输出记录结构

最终每条记录：

```text
(vehicle_id,
 region_id,
 start_time,
 end_time,
 cost,
 init_category,
 base_quality)
```

含义：

> 某工人在某区域某时间段可参与任务，并具有固定成本与质量属性。

---

# 8. 代码运行后额外统计输出

程序还会输出：

* 工人数
* trusted 数量
* unknown 数量
* malicious 数量
* trusted 比例
* malicious 比例
* 平均质量
* 各类别平均质量

用于验证初始化是否合理。

---

# 9. 本步骤在整个实验中的作用

该步骤是整个群智感知实验的基础数据生成模块。

它为后续步骤提供：

---

## 给任务生成模块

提供：

* 哪些区域工人多
* 哪些时间段工人活跃

---

## 给工人招募模块

提供：

* 工人报价
* 工人可覆盖区域
* 工人可用时间

---

## 给可信验证模块

提供：

* 工人真实类别
* 基础质量

---

## 给奖励机制模块

提供：

* 工人成本
* 工人参与次数基础

---

# 10. 当前参数的实验含义（重要）

当前代码设定：

| 类别        | 比例  |
| --------- | --- |
| trusted   | 20% |
| unknown   | 40% |
| malicious | 40% |

说明：

这是一个**较强对抗环境**。

即：

* 恶意工人占比较高
* 平台初始可信工人较少
* 更适合验证你的“空间一致性识别 + 信任传播 + 留存机制”

因为如果 malicious 太少，算法优势不明显。

---

# 11. 小结（核心一句话）

本步骤的本质是：

> 将真实车辆轨迹数据转换为具有时间、空间、成本、可信属性的群智感知工人数据集。

完成后，你的系统就拥有了：

```text
谁（工人）
什么时候可用
在哪个区域
成本多少
可信程度如何
```

这正是后续所有实验的基础。
