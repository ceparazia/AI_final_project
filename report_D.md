# D 模块报告 - 前端可视化与现场 Demo

**组员**：武旻阳（D 同学）  
**模块**：前端可视化与现场 Demo  
**数据来源**：output_A/state_A.json（即 demo_state.json）

---

## 1. 代码文件

### 1.1 scripts_D/app.py —— Streamlit 主页面

主 Streamlit 应用，通过 `streamlit run scripts_D/app.py` 启动。

- 提供 6 个功能标签页：Agent 状态 / 消息日志 / 社交关系图 / 指标图表 / 辩论详情 / 时间线回放
- 启动时自动加载 `output_D/demo_state.json` 中的演示数据
- 侧边栏提供文件上传器，支持加载自定义 `state.json` 文件和 Demo 数据一键加载

### 1.2 scripts_D/visualization.py —— 核心可视化模块

核心可视化模块，提供数据解析与图表渲染功能：

| 函数 | 功能说明 |
|------|---------|
| `load_state(path)` | 从指定路径加载 state.json 文件 |
| `render_agent_table(state)` | 在终端中打印 agent 状态表格（带颜色编码） |
| `render_message_log(state)` | 在终端中打印按时间步分组的对话记录 |
| `render_social_graph(state)` | 使用 NetworkX + Matplotlib 绘制静态社交关系图 |
| `render_metrics(state)` | 绘制 3 个子图：传播率曲线、平均置信度曲线、观点分布堆叠柱状图 |
| `render_social_graph_pyvis(state, html_path)` | 使用 pyvis 生成交互式社交网络图（HTML） |
| `get_agent_table_data(state)` | 提取 agent 表格数据，供 Streamlit 页面使用 |
| `get_debate_summary(state)` | 提取辩论摘要数据 |
| `get_event_info(state)` | 提取事件信息 |
| `get_timeline_data(state)` | 提取时间线数据 |

---

## 2. 功能说明

本模块严格遵循方案约定的统一接口，所有数据均从 A 模块输出的 `state.json` 中读取。

### 页面结构（6 个标签页）

| 标签页 | 内容说明 |
|--------|---------|
| Agent 状态 | 以表格展示各 Agent 的姓名、角色、观点、置信度及信任对象，观点列用绿/红/灰色进行颜色编码 |
| 消息日志 | 按时间步过滤，以 stance 颜色卡片形式展示每轮对话内容 |
| 社交关系图 | 支持 NetworkX 静态图与 pyvis 交互图两种模式，节点颜色表示观点，边粗细表示信任强度 |
| 指标图表 | 三个子图：传播率曲线、平均置信度曲线、观点分布堆叠柱状图 |
| 辩论详情 | 展示辩论触发状态、轮次、投票结果、各方论点和辩论总结 |
| 时间线回放 | 通过下拉菜单选择时间步，逐轮查看各 Agent 在每个时间步的观点状态快照 |

---

## 3. 模块自测结果

使用 A 模块生成的 `output_D/demo_state.json`（与 `output_A/state_A.json` 内容一致）进行模块自测。

自测环境：4 个 Agent，20 条消息（5 个时间步，每步 4 条），5 条时间线快照。

### 3.1 Agent 当前状态

启动页面后，默认显示 **Agent Current Status** 标签页，展示各 Agent 的当前意见、倾向、置信度以及对其他 Agent 的信任情况。页面下方为 **Agent Memory Details**，详细记录了各 Agent 的历史记忆。

![Agent 当前状态](Pic_D/start.png)

**Agent 状态表格：**

| Agent ID | 名称 | 角色 | 观点 | 置信度 | 信任对象 |
|----------|------|------|------|--------|---------|
| agent_1 | 信息传播者 | active_spreader | 相信 | 0.71 | 无 |
| agent_2 | 理性验证者 | rational_verifier | 观望 | 0.46 | 无 |
| agent_3 | 组织协调者 | coordinator | 观望 | 0.46 | agent_2 |
| agent_4 | 风险敏感者 | risk_sensitive | 不相信 | 0.85 | 无 |

### 3.2 社交关系网络图

切换到 **Social Graph** 标签页，展示 Agent 之间的社交关系拓扑图。绿色节点表示"相信"，红色节点表示"不相信"，灰色节点表示"观望"。连边的粗细代表 Agent 之间的信任强度。

![社交关系图](Pic_D/rel_graph.png)

### 3.3 实验指标

切换到 **Metrics** 标签页，展示三张实验指标图表：

- **传播率（Spread Rate）**：随时间步变化的折线图，反映信息在群体中的传播比例
- **平均置信度（Avg Confidence）**：随时间步变化的折线图，反映群体对信息置信度的均值变化
- **观点分布（Opinion Distribution）**：按时间步堆叠的柱状图，展示各时间步中相信/观望/不相信的人数分布

自测结果显示传播率稳定在 25%，平均置信度在 0.62~0.65 范围内波动，观点分布保持为 1 人相信 / 2 人观望 / 1 人不相信。

![指标图表](Pic_D/metric.png)

### 3.4 辩论详情

切换到 **Debate Details** 标签页，展示辩论触发状态、轮次信息、各方立场论点和投票结果。

![辩论详情](Pic_D/deb_detail.png)

**辩论结果摘要：**

- **触发状态**：已触发（共 5 轮辩论）
- **投票结果**：1 票相信 / 2 票观望 / 1 票不相信
- **辩论总结**：群体未达成共识，组织协调者建议等待官方通知

### 3.5 时间线回放

切换到 **Timeline Replay** 标签页，用户可通过下拉菜单选择特定时间步，逐轮查看该轮讨论后各个 Agent 的观点状态和置信度变化。

![时间线回放](Pic_D/replay.png)

---

## 4. 创新点设计（D 模块）

1. **观点驱动可视化（Opinion-Driven Visualization）**  
   节点颜色根据 Agent 的观点状态动态映射——"相信"为绿色、"不相信"为红色、"观望"为灰色，社交关系图中边的粗细代表信任强度，实现一目了然的群体态势感知。

2. **双模式社交图（Dual-Mode Social Graph）**  
   同时支持 NetworkX 静态图与 pyvis 交互式网络图，用户可一键切换。静态模式下快速概览全局关系，交互模式下可拖拽节点、缩放查看 Agent 间的信任链路。

3. **时间线回放（Timeline Replay）**  
   用户通过下拉菜单选择时间步，逐轮查看 Agent 的观点状态和消息传播过程，支持按需回放仿真全流程，为现场 Demo 提供灵活的讲解节奏。

4. **一键演示（One-Click Demo）**  
   预置 `demo_state.json` 模拟数据，只需执行 `streamlit run` 即可启动完整 Demo，无需手动准备数据，适配课程展示现场的快速部署需求。

---

## 5. 运行方式

```bash
# 安装依赖（如尚未安装）
pip install streamlit networkx matplotlib pandas

# 启动 Demo 应用
streamlit run scripts_D/app.py

# 命令行自测
python -c "from scripts_D.visualization import load_state, render_agent_table, render_message_log; state = load_state('output_D/demo_state.json'); render_agent_table(state); print('---'); render_message_log(state)"
```