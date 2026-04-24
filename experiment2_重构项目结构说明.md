# experiment2 重构项目结构说明

## 1. 重构目标

本次重构的目标是把 `experiment2` 中原来逐步叠加形成的脚本式实验代码，整理为一个可以复用、可以热插拔切换算法的工程化结构。

重构后的设计原则如下：

1. 不改变原有算法核心逻辑。
2. 不改变原有指标口径。
3. 不改变原有实验主流程。
4. 将公共流程抽离，避免 `random / cmab / trust / pgrd / lgsc` 多份重复代码。
5. 让不同算法只保留自己的“增量逻辑”，通过统一接口接入实验器。


## 2. 重构后核心文件

当前重构后的核心模块统一使用 `experiment2_重构_*` 前缀：

```text
experiment2_重构_配置.py
experiment2_重构_数据加载.py
experiment2_重构_算法基类.py
experiment2_重构_算法数据结构.py
experiment2_重构_随机算法.py
experiment2_重构_CMAB算法.py
experiment2_重构_Trust算法.py
experiment2_重构_PGRD算法.py
experiment2_重构_LGSC算法.py
experiment2_重构_评价.py
experiment2_重构_工人状态.py
experiment2_重构_结果管理.py
experiment2_重构_实验器.py
experiment2_重构_main.py
```


## 3. 分层结构

### 3.1 配置层

```text
experiment2_重构_配置.py
```

职责：

- 管理实验公共参数
- 管理不同算法模式的输出前缀
- 管理不同模式下的绘图字段
- 统一构造 `config`


### 3.2 数据层

```text
experiment2_重构_数据加载.py
```

职责：

- 读取 `experiment2_worker_options.json`
- 构建 `workers`
- 构建 `task_dict`
- 构建 `tasks_by_slot`
- 构建 `task_grid_map`
- 根据模式初始化：
  - `base`
  - `trust`
  - `pgrd`
  - `lgsc`


### 3.3 算法接口层

```text
experiment2_重构_算法基类.py
experiment2_重构_算法数据结构.py
```

职责：

- 统一算法父类 `BaseAlgorithm`
- 统一算法输入 `RoundContext`
- 统一算法输出 `AlgorithmDecision`

其中：

- `run_round(context)`：每轮算法决策入口
- `update(feedback)`：每轮结束后算法状态更新入口


### 3.4 算法实现层

```text
experiment2_重构_随机算法.py
experiment2_重构_CMAB算法.py
experiment2_重构_Trust算法.py
experiment2_重构_PGRD算法.py
experiment2_重构_LGSC算法.py
```

职责：

- 每个文件只负责一个算法类
- 各算法通过继承 `BaseAlgorithm` 接入统一实验器
- 不同算法只保留各自独有逻辑

算法关系如下：

```text
RandomAlgorithm
CMABAlgorithm
TrustCMABAlgorithm   -> 在 CMAB 基础上增加验证任务与 trust 更新
PGRDAlgorithm        -> 在 Trust 基础上增加会员机制
LGSCAlgorithm        -> 在 PGRD 基础上增加沉没成本与奖励金机制
```


### 3.5 实验运行层

```text
experiment2_重构_实验器.py
```

职责：

- 统一实验主循环
- 每轮提取 `available_workers`
- 每轮提取 `round_tasks`
- 构造 `RoundContext`
- 调用 `algorithm.run_round(context)`
- 调用评价模块
- 调用工人状态更新模块
- 调用 `algorithm.update(feedback)`
- 聚合每轮结果


### 3.6 评价与状态管理层

```text
experiment2_重构_评价.py
experiment2_重构_工人状态.py
```

职责：

`experiment2_重构_评价.py`

- `evaluate_round()`
- `compute_platform_utility()`
- `update_cumulative_metrics()`

`experiment2_重构_工人状态.py`

- `get_available_workers()`
- `update_worker_statistics()`
- `update_worker_reward_cost()`
- `update_worker_leave_state()`
- `update_active_rounds()`


### 3.7 结果管理层

```text
experiment2_重构_结果管理.py
```

职责：

- `aggregate_round_results()`
- `average_dict_records()`
- `save_json()`
- `plot_metric()`
- `summarize_results()`


### 3.8 主程序入口

```text
experiment2_重构_main.py
```

职责：

- 根据 `mode` 选择算法类
- 创建 `DataLoader`
- 创建算法对象
- 创建 `Simulator`
- 运行实验
- 汇总结果
- 保存结果
- 画图


## 4. 核心调用流程

重构后的主流程如下：

```text
experiment2_重构_main.py
    ↓
build_config(mode)
    ↓
DataLoader.load()
    ↓
Simulator.run()
    ↓
每轮构造 RoundContext
    ↓
algorithm.run_round(context)
    ↓
返回 AlgorithmDecision
    ↓
evaluate_round()
    ↓
update_worker_reward_cost()
update_worker_leave_state()
update_worker_statistics()
    ↓
algorithm.update(feedback)
    ↓
update_cumulative_metrics()
    ↓
summarize_results()
```


## 5. 热插拔机制

本次重构最关键的目标，是让不同算法可以直接替换，而不需要改实验主流程。

在主程序中，只需要切换算法模式即可：

```python
algorithm = RandomAlgorithm(config)
# 或
algorithm = CMABAlgorithm(config)
# 或
algorithm = TrustCMABAlgorithm(config)
# 或
algorithm = PGRDAlgorithm(config)
# 或
algorithm = LGSCAlgorithm(config)
```

在 `experiment2_重构_main.py` 中，这个切换通过工厂映射统一完成：

```text
random -> RandomAlgorithm
cmab   -> CMABAlgorithm
trust  -> TrustCMABAlgorithm
pgrd   -> PGRDAlgorithm
lgsc   -> LGSCAlgorithm
```

因此，实验器 `Simulator` 不需要关心当前运行的是哪一种算法。


## 6. 与原始脚本的关系

原来的逐步实验脚本仍然保留为兼容入口，例如：

```text
experiment2_第4步随机招募算法对比.py
experiment2_第4步CMAB.py
experiment2_第5步加入验证任务该轮所有可做.py
experiment2_第6步加入PGRD.py
experiment2_第7步加入LGSC.py
```

这些旧文件现在的作用是：

- 保留原有文件名，方便沿用旧运行方式
- 作为外层入口转发到新的 `experiment2_重构_main.py`

也就是说：

- 旧文件负责“兼容入口”
- 新框架负责“统一调度”


## 7. 各文件职责简表

| 文件名 | 职责 |
|---|---|
| `experiment2_重构_配置.py` | 配置管理 |
| `experiment2_重构_数据加载.py` | 数据加载与工人/任务初始化 |
| `experiment2_重构_算法基类.py` | 算法统一接口 |
| `experiment2_重构_算法数据结构.py` | 统一算法输入输出结构 |
| `experiment2_重构_随机算法.py` | 随机算法 |
| `experiment2_重构_CMAB算法.py` | CMAB 算法 |
| `experiment2_重构_Trust算法.py` | Trust-CMAB 算法 |
| `experiment2_重构_PGRD算法.py` | PGRD 算法 |
| `experiment2_重构_LGSC算法.py` | LGSC 算法 |
| `experiment2_重构_评价.py` | 每轮评价与累计指标 |
| `experiment2_重构_工人状态.py` | 工人长期状态更新 |
| `experiment2_重构_结果管理.py` | 结果汇总、保存、绘图 |
| `experiment2_重构_实验器.py` | 统一实验主循环 |
| `experiment2_重构_main.py` | 总入口 |


## 8. 运行方式

### 8.1 使用新入口运行

```bash
python experiment2_重构_main.py --mode random
python experiment2_重构_main.py --mode cmab
python experiment2_重构_main.py --mode trust
python experiment2_重构_main.py --mode pgrd
python experiment2_重构_main.py --mode lgsc
```

### 8.2 使用原有文件名运行

```bash
python experiment2_第4步随机招募算法对比.py
python experiment2_第4步CMAB.py
python experiment2_第5步加入验证任务该轮所有可做.py
python experiment2_第6步加入PGRD.py
python experiment2_第7步加入LGSC.py
```


## 9. 重构后的优点

本次重构完成后，项目相比原来的脚本式结构有以下优点：

1. 主流程统一，不再需要维护多份重复实验循环代码。
2. 数据加载统一，避免不同文件中重复构造 `workers / tasks_by_slot / task_grid_map`。
3. 算法接口统一，便于后续继续增加新算法。
4. 各算法职责更清晰，便于老师检查每种方法的独立逻辑。
5. 实验器、评价器、结果管理器解耦后，后续调试和复现实验更方便。


## 10. 总结

重构后的 `experiment2` 项目已经从“按步骤堆叠的大脚本”整理为“可热插拔的模块化实验框架”。

它的核心特点可以概括为：

```text
数据统一加载
算法统一接口
实验统一调度
结果统一管理
算法模块可热插拔
```

这使得项目结构更符合面向对象和工程化组织方式，也更方便后续继续扩展新的实验算法。
