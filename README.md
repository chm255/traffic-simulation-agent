# Traffic Simulation Agent

基于 **LLM Agent + SUMO / TraCI + RAG + LangGraph** 的交通仿真实验智能助手。

项目目标是让用户通过自然语言描述交通仿真实验任务，由 Agent 自动完成任务理解、知识检索、实验调用、结果计算与解释，并逐步构建面向交通科研实验的智能 Agent。

---

## Goal

通过自然语言完成：

- 交通仿真实验需求理解
- SUMO 仿真调用
- 实验参数配置
- 交通指标自动计算
- 多 seed 批量实验
- 实验统计汇总
- 动态实验决策
- 项目知识检索
- 多方案比较
- 实验结果解释

长期目标是构建一个能够完成：

```text
自然语言实验需求
↓
知识检索 / 任务理解
↓
实验规划
↓
SUMO 仿真执行
↓
指标计算
↓
结果分析
↓
下一步实验决策
```

的 Traffic Simulation Agent。

---

## Tech Stack

- Python
- DeepSeek OpenAI-compatible API
- SUMO
- TraCI
- Sentence Transformers
- RAG
- LangGraph
- SQLite Checkpoint
- JSON / Structured Output

当前本地 Embedding 模型：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## Current Agent Architecture

当前系统已升级为 **Traffic Simulation Agent V3**。

相比 V2，RAG、SUMO Tool、Tool Schema 和 Validation 等能力层基本不变，主要变化是：

> 使用 LangGraph 替代原先手写的 `for / if / elif` Agent Loop，对 Agent 的 State、Node、Edge、Conditional Edge、Checkpoint 与 Thread 进行显式编排。

当前架构：

```text
User
 ↓
LangGraph
 ↓
LLM Node
 ↓
Conditional Edge / Router
 ├─ 无 Tool Call → END
 │
 └─ 有 Tool Call
      ↓
    Tool Node
    ├─ RAG Tool
    │    ↓
    │ Knowledge Base
    │
    └─ SUMO Tool
         ↓
       TraCI
         ↓
       SUMO
      ↓
Tool Result
      ↓
   LLM Node
      ↓
下一步 Tool / Final Answer
```

同时加入 Checkpoint：

```text
LangGraph State
      ↓
 Checkpointer
      ↓
 Thread ID
      ↓
保存 / 恢复 Conversation State
```

核心职责划分：

```text
LLM
→ 理解用户意图
→ 动态决策
→ 工具选择
→ 结果解释

LangGraph
→ 管理 Agent Workflow
→ 管理 State
→ 管理 Node / Edge
→ 管理条件分支与循环
→ 管理 Checkpoint / Thread
→ 支持状态恢复

Agent Runtime / Python
→ 参数解析
→ Validation
→ Error Handling
→ Tool Dispatch
→ 确定性逻辑与计算

RAG
→ 提供项目知识
→ 解决 Knowledge Gap

Tools / Python
→ 执行确定性外部任务
→ 解决 Capability Gap

SUMO / TraCI
→ 执行真实交通仿真实验
```

---

## Current Capabilities

### 1. Structured LLM Interaction

已支持：

- DeepSeek API 调用
- system / user messages
- Structured JSON Output
- `json.loads`
- API Error Handling

核心原则：

> 合法 JSON 不代表业务数据一定正确，因此业务约束仍需由 Runtime Validation 负责。

---

### 2. Tool Calling

当前 Agent 可以通过 Tool Calling 将自然语言任务映射为 Python Tool。

基本流程：

```text
User
↓
LLM
↓
Tool Call Proposal
↓
Runtime Validation
↓
Python Function
↓
Tool Result
↓
LLM
```

Tool Schema 仅负责向 LLM 描述能力。

真实能力由 Python Function 实现。

---

### 3. Agent Loop

已实现通用 Agent Loop：

```text
Observe
↓
Decide
↓
Act
↓
Observe
↓
Decide
↓
Act / Finish
```

支持：

- 多轮 Tool Calling
- `max_steps`
- Tool Result 回传
- Validation
- Tool Execution Error
- API Error

---

### 4. LangGraph Orchestration

Day 7 将原先手写的 Agent Loop 迁移为 LangGraph。

原先的控制方式：

```text
for / while
+
if / elif
+
手动维护 messages
+
手动决定下一步调用哪个函数
```

迁移后：

```text
State
+
Node
+
Edge
+
Conditional Edge
+
Checkpoint
+
Thread
```

#### State

State 表示 Graph 中各个 Node 共同读取和更新的共享数据。

当前 Traffic Simulation Agent 主要使用：

```python
class TrafficAgentState(TypedDict):
    messages: ...
```

因此当前项目中最主要的 State 是 `messages`，但 State 并不等于 messages。

未来可以继续加入：

```text
scenario
seeds
experiment_results
current_stage
error
...
```

#### Node

Node 是 Graph 中真正执行逻辑的节点，本质上通常仍然是 Python 函数。

当前主要节点：

```text
llm_node
→ 调用 DeepSeek
→ 根据当前 messages 生成回答或 Tool Call

tool_node
→ 读取 Tool Call
→ Validation
→ 调用真实 Python Tool
→ 将 Tool Result 写回 State
```

`START` 和 `END` 是 Graph 的特殊入口和出口标记，不是普通业务函数节点。

#### Edge

普通 Edge 表示固定执行顺序：

```text
tool_node
↓
llm_node
```

对应：

```python
builder.add_edge(...)
```

Conditional Edge 根据当前 State 动态决定下一步：

```text
llm_node
↓
是否存在 Tool Call？
├─ Yes → tool_node
└─ No  → END
```

对应：

```python
builder.add_conditional_edges(...)
```

#### LangGraph Agent Loop

当前核心循环：

```text
START
  ↓
LLM Node
  ↓
Router
 ├─ 无 Tool Call → END
 │
 └─ 有 Tool Call
      ↓
   Tool Node
      ↓
   LLM Node
      ↓
     ...
```

因此 LangGraph 并不是简单地“替代 if/else”，而是把原本隐藏在 Python 控制流中的：

```text
状态
+
执行顺序
+
循环
+
条件分支
```

显式组织成 Graph，便于后续扩展复杂 Workflow。

---

### 5. Checkpoint 与多轮 Conversation State

Day 7 进一步加入了 LangGraph Checkpoint。

需要区分三个概念：

```text
State
→ Agent 当前共享的数据

Checkpoint
→ 某一时刻 Graph State 的快照

Thread
→ 一系列属于同一个会话 / 任务的 Checkpoint
```

#### thread_id

每一个独立对话 / Agent 任务可以使用一个 `thread_id`：

```python
{
    "configurable": {
        "thread_id": "traffic-agent-demo"
    }
}
```

同一个 `thread_id`：

```text
恢复已有 Conversation State
```

新的 `thread_id`：

```text
创建新的独立 Conversation State
```

因此不同 Thread 之间不会自动共享历史消息。

#### InMemorySaver

```text
Conversation State
↓
RAM
↓
当前 Python 进程
```

特点：

- 同一次程序运行中可以实现多轮对话；
- 同一个 thread 可以持续恢复历史 State；
- Python 程序退出后，State 消失。

#### SqliteSaver

```text
Conversation State
↓
SQLite
↓
Disk
```

特点：

- State 被持久化到本地 SQLite；
- Python 程序退出后数据仍然存在；
- 下次重新启动程序后，只要使用相同的 `thread_id`，即可恢复历史 State；
- 不同 `thread_id` 之间相互隔离。

当前 Checkpoint 文件：

```text
checkpoints/traffic_agent.sqlite
```

注意：

> `InMemorySaver` 和 `SqliteSaver` 的区别主要是 State 的存储位置和生命周期。

它们目前承载的仍然是 **thread-scoped short-term memory**。

```text
InMemorySaver
→ RAM 中的短期会话状态

SqliteSaver
→ 持久化到磁盘的短期会话状态
```

真正跨不同 Thread / Session 的 Long-term Memory 当前尚未实现。

---

### 6. Conversation Context Growth

Checkpoint 可以恢复历史 messages，但持续对话会使 `messages` 不断增长。

例如：

```text
第 1 轮：
System
User 1
Assistant 1

第 2 轮：
System
User 1
Assistant 1
User 2
Assistant 2

第 N 轮：
历史 messages
+
最新 User
```

因此每一次：

```python
client.chat.completions.create(
    messages=state["messages"]
)
```

都会将越来越多的历史消息作为 LLM 输入。

可能带来：

```text
Input Tokens 增加
↓
API 成本增加
+
响应时间增加
+
最终接近 Context Window 上限
```

后续可考虑：

```text
Message Trimming
→ 只保留最近 N 轮

Conversation Summary
→ 将早期历史压缩为摘要

Structured State
→ 将 scenario / seed / results 等任务状态从聊天文本中独立出来

Experiment Result Storage
→ 正式实验结果单独保存为 CSV / JSON / Database
```

Checkpoint 的职责是恢复 Agent Workflow State，并不应该替代正式科研实验结果存储。

---

### 7. Real SUMO Integration

已实现：

```text
Natural Language
↓
Agent
↓
SUMO Tool
↓
TraCI
↓
Real SUMO Simulation
↓
Traffic Metrics
```

当前支持场景：

```text
cross
```

对应：

```text
sumotest/cross.sumocfg
```

当前监测进口车道：

```text
E_C_0
N_C_0
S_C_0
W_C_0
```

---

## Traffic Metrics

当前项目正式使用以下交通指标：

### average_queue

每个仿真时间步：

1. 对所有 monitored approach lanes 的 halting vehicles 数量求和；
2. 对所有时间步取平均。

单位：

```text
veh
```

该指标表示监测进口道范围内的时间平均总排队车辆数。

不是每车道平均队列。

---

### mean_network_waiting_time

每个仿真时间步：

1. 对所有 monitored approach lanes 上车辆当前 waiting time 求和；
2. 对所有时间步取平均。

单位：

```text
s
```

表示监测进口道范围内的 time-average network-level waiting-time state。

不是平均每辆车等待时间。

---

### mean_vehicle_waiting_time

对于观察窗口内所有曾进入 monitored lanes 的车辆，累计其在 monitored lanes 内处于 waiting 状态的时间：

```text
total_vehicle_waiting_time
/
observed_vehicle_count
```

单位：

```text
s/veh
```

包括仿真结束时尚未完成行程、但曾在监测车道出现的车辆。

不是完整 trip waitingTime。

---

### throughput

仿真观察窗口内累计到达目的地的车辆数。

单位：

```text
veh
```

---

### completion_rate

定义为：

```text
total_arrived / total_departed
```

表示有限仿真时间窗口内的车辆行程完成比例。

---

## Batch Experiment

已支持多 seed 实验：

```text
Batch Experiment
├─ seed 42 → SUMO
├─ seed 43 → SUMO
├─ seed 44 → SUMO
└─ Python Statistics
```

当前统计指标：

- mean
- sample standard deviation
- minimum
- maximum

其中标准差使用：

```python
statistics.stdev
```

即 sample standard deviation。

核心原则：

> 多 seed 的统计计算由 Python 完成，不依赖 LLM 心算。

---

## Dynamic Experiment Decision

Agent 已能够根据真实实验结果决定是否继续执行下一阶段实验。

示例：

```text
Initial Seeds
↓
Run SUMO
↓
Calculate average_queue sample std
↓
Compare with threshold
↓
Condition True?
├─ Yes → Run Extra Seeds
└─ No  → Stop
```

Runtime 自己维护实验状态并验证条件。

LLM 负责提出下一步 Action，但不能绕过 Runtime Validation。

---

## RAG

项目知识已从 System Prompt 中逐步外置到：

```text
knowledge/
├── metrics.md
├── scenarios.md
└── experiment_rules.md
```

当前 RAG Pipeline：

```text
Knowledge Base
↓
Document Loading
↓
Markdown Chunking
↓
Embedding
↓
Cosine Similarity
↓
Top-K Retrieval
↓
Retrieved Context
↓
LLM
↓
Grounded Answer
```

RAG 当前支持中英文跨语言语义检索。

例如：

```text
用户：
我们项目里的吞吐量怎么定义？

↓ Embedding Retrieval

metrics.md
→ throughput
```

---

## RAG + Tool Agent

RAG 已被进一步封装为 Agent Tool：

```text
search_project_knowledge
```

当前 Agent 主要拥有两类能力：

```text
Knowledge Capability
→ search_project_knowledge

Execution Capability
→ run_sumo_experiment
```

因此 Agent 可以自主区分：

### Knowledge-only

```text
mean_vehicle_waiting_time 怎么定义？
↓
RAG Tool
```

不会启动 SUMO。

### Simulation-only

```text
cross 场景，seed=42，运行300秒
↓
SUMO Tool
```

不会无意义调用 RAG。

### Hybrid Task

```text
先查询 completion_rate 定义
↓
运行 SUMO
↓
结合定义解释真实实验结果
```

当前系统已经进一步通过 LangGraph 完成编排层升级，可以称为：

> **Traffic Simulation Agent V3**

V2 与 V3 的主要区别：

```text
V2
→ RAG + SUMO + 手写 Agent Loop

V3
→ RAG + SUMO + LangGraph Orchestration
→ State / Node / Edge
→ Checkpoint / Thread
→ Persistent Conversation State
```

RAG、SUMO、Tool 本身的能力并没有因为 LangGraph 而改变，变化的主要是 Agent 的 Workflow Orchestration。

---

## Project Structure

当前主要目录：

```text
traffic-simulation-agent/
│
├── day01/
├── day02/
├── day03/
├── day04/
│   ├── day04_real_sumo_agent.py
│   ├── day04_sumo_connection.py
│   ├── day04_sumo_metrics.py
│   └── day04_sumo_run_test.py
│
├── day05/
│
├── day06/
│   ├── day06_knowledge_test.py
│   ├── day06_chunking.py
│   ├── day06_keyword_retrieval.py
│   ├── day06_embedding_test.py
│   ├── day06_embedding_similarity.py
│   ├── day06_embedding_retrieval.py
│   ├── day06_retrieval_evaluation.py
│   ├── day06_rag_qa.py
│   └── day06_rag_tool_agent.py
│
├── day07/
│   ├── __init__.py
│   ├── day07_basic_graph.py
│   ├── day07_conditional_graph.py
│   ├── day07_llm_tool_graph.py
│   ├── day07_traffic_agent_graph.py
│   ├── day07_traffic_agent_memory.py
│   └── day07_traffic_agent_sqlite.py
│
├── knowledge/
│   ├── metrics.md
│   ├── scenarios.md
│   └── experiment_rules.md
│
├── checkpoints/
│   └── traffic_agent.sqlite
│
├── sumotest/
│   ├── cross.sumocfg
│   ├── cross.net.xml
│   └── cross.rou.xml
│
├── api.txt
└── README.md
```

---

## Running Traffic Simulation Agent V3

激活环境：

```powershell
conda activate traffic-agent
```

### V2：手写 Agent Loop

```powershell
python -m day06.day06_rag_tool_agent
```

### V3：LangGraph Agent

```powershell
python -m day07.day07_traffic_agent_graph
```

### V3：进程内多轮 Conversation State

```powershell
python -m day07.day07_traffic_agent_memory
```

使用：

```text
InMemorySaver
```

程序退出后 Conversation State 消失。

### V3：SQLite Persistent Conversation State

```powershell
python -m day07.day07_traffic_agent_sqlite
```

使用：

```text
SqliteSaver
+
thread_id
```

程序退出后，可通过同一个 `thread_id` 恢复之前的 Conversation State。

示例知识问题：

```text
我们项目里的 mean_vehicle_waiting_time 是怎么定义的？
```

示例仿真实验：

```text
使用 cross 场景，seed=42，运行300秒。
```

示例混合任务：

```text
先告诉我 completion_rate 在我们项目中的定义，
然后使用 cross 场景，seed=42，运行300秒，
并结合这个定义解释实验结果。
```

示例多轮对话：

```text
User:
我们项目里的 throughput 是怎么定义的？

Assistant:
...

User:
那它的单位呢？

Assistant:
知道“它”指 throughput。
```

---

## API Key

DeepSeek API Key 保存在项目根目录：

```text
api.txt
```

该文件不应提交到 Git。

请确保 `.gitignore` 至少包含：

```gitignore
api.txt
```

Checkpoint 数据库是否提交 Git 可按项目需求决定。学习阶段通常建议忽略运行时状态文件，例如：

```gitignore
checkpoints/*.sqlite
```

正式科研结果应独立保存在 `results/`、CSV、JSON 或数据库中，而不是依赖 LangGraph Checkpoint。

---

## Reproducibility

交通仿真实验应记录并固定：

- SUMO version
- Python environment
- scenario files
- source code version
- random seed
- simulation duration
- simulation step length
- monitored lanes
- metric definitions

当前测试使用的 SUMO 版本：

```text
SUMO 1.26.0
SUMO 1.27.1
```

正式科研实验中应进一步保存完整实验环境与版本信息。

---

## Roadmap

- [x] DeepSeek API 基础调用
- [x] Structured JSON Output
- [x] Input Validation
- [x] Tool Calling
- [x] Agent Loop
- [x] Error Handling
- [x] Real SUMO Integration
- [x] Traffic Metrics
- [x] Batch Experiment
- [x] Multi-seed Statistics
- [x] Dynamic Agent Decision
- [x] Knowledge Base
- [x] Keyword Retrieval
- [x] Embedding Retrieval
- [x] RAG
- [x] RAG Tool
- [x] RAG + SUMO Agent
- [x] LangGraph
- [ ] MCP
- [ ] Agent Evaluation
- [x] Thread-scoped Conversation State
- [x] SQLite Persistent Checkpoint
- [ ] Long-term Memory
- [ ] Context / Message Management
- [ ] Experiment Memory
- [ ] Scenario Modification Tools
- [ ] Automatic Experiment Comparison
- [ ] Visualization / Plot Tools
- [ ] Research Workflow Agent

---

## Notes

### Day 7：LangGraph 学习总结

Day 7 的核心不是让 Agent 获得新的 RAG 或 SUMO 能力，而是升级 **Agent Orchestration**。

```text
Day 6
→ 手写 for / if / elif 管理 Agent Loop

Day 7
→ LangGraph 管理 State / Node / Edge / Checkpoint
```

最重要的理解：

```text
Node
→ 执行什么

Edge
→ 下一步去哪里

State
→ Graph 当前共享数据

Conditional Edge
→ 根据 State 动态选择路径

Checkpoint
→ 保存某一时刻 State

Thread ID
→ 标识并恢复某一个独立会话 / Agent 任务
```

LangGraph 并不是为了替代所有 Python `if / else`。

函数内部的确定性业务逻辑仍然适合使用普通 Python：

```python
if seed < 0:
    ...
```

LangGraph 更适合管理 Agent / Workflow 级别的复杂流程：

```text
LLM
↓
RAG / SUMO
↓
Evaluate
↓
Retry / Continue / End
```

---

### Agent 职责划分

> LLM 负责理解、决策和工具选择；Agent Runtime 负责循环、校验、异常处理和执行控制；RAG 提供项目知识；Tools 负责真正完成确定性的外部任务。

---

### LLM vs Python

- LLM 负责语言理解、任务意图识别、动态决策和结果解释。
- Python 负责确定性执行、统计计算、Validation 和文件操作。
- 能用确定性程序可靠完成的工作，不应该让 LLM 猜测或心算。

---

### Workflow

固定、重复、确定的流程应该封装为 Workflow。

例如：

```text
Multi-seed Experiment
↓
SUMO × N
↓
Python Statistics
```

而：

```text
是否需要执行这个 Workflow？
下一步执行哪个 Workflow？
```

更适合由 Agent 决定。

---

### Runtime Validation

不能理解为：

```text
LLM要求执行
↓
程序无条件执行
```

而应该是：

```text
LLM提出 Action
↓
Runtime Validation
↓
合法才执行
```

LLM 可以理解动态条件，但涉及确定数值判断和执行权限时，应尽可能由 Runtime 控制。

---

### Knowledge vs Capability

```text
RAG
→ Knowledge Gap

Tool
→ Capability Gap

Agent Loop
→ Dynamic Decision
```

知识和能力不能混为一谈。

RAG 即使告诉 Agent：

```text
如何修改 SUMO route 文件
```

也不意味着 Agent 已经拥有：

```text
write_route_file()
```

这样的真实执行能力。

---

### Retrieval

Embedding similarity 表示语义相似程度，但：

```text
Semantic Similarity
≠
Business Equivalence
≠
Answerability
```

Retriever 找出的 Top-1 只是“最相似的候选知识”，不代表它一定能够正确回答用户问题。

因此 RAG 的检索结果仍需谨慎解释。

---

### Scientific Interpretation

Agent 可以根据实验数据描述观测结果，但不应在缺乏证据时自动进行因果推断。

例如：

```text
观察到排队增加
+
completion_rate 下降
```

不等价于已经证明：

```text
排队增加导致 completion_rate 下降
```

科研场景下需要区分：

```text
Observation
Correlation
Causal Explanation
```

并避免超出实验数据证据范围进行解释。