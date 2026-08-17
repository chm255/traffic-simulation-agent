# Traffic Simulation Agent

基于 **LLM Agent + SUMO / TraCI + RAG + LangGraph** 的交通仿真实验智能助手，并逐步加入 Human-in-the-loop、Tool Permission Policy 与 Context Management。

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
LangGraph State
 ↓
Context Manager
 ↓
LLM Node
 ↓
Tool Call?
 ├─ No → END
 │
 └─ Yes
      ↓
Permission Policy
 ┌────────┼──────────┐
 ↓        ↓          ↓
AUTO   APPROVAL     DENY
 ↓        ↓          ↓
Tool   interrupt()  Block
Node      ↓
        Human
       /     \
    Approve  Reject
      ↓        ↓
   Tool Node  Reject Node
       \       /
        \     /
        Tool Result
            ↓
         LLM Node
            ↓
   Next Tool / Final Answer
```

工具执行层：

```text
RAG Tool
↓
Knowledge Base

SUMO Tool
↓
TraCI
↓
SUMO
```

同时保留 Checkpoint：

```text
LangGraph State
      ↓
 Checkpointer
      ↓
 Thread ID
      ↓
保存 / 恢复 Conversation State
```

其中 Day 8 新增了两个重要边界：

```text
Memory / State
≠
本轮真正发送给 LLM 的 Context

LLM Proposed Action
≠
Runtime 已授权执行
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

### 7. Human-in-the-loop

Day 8 在原有 LangGraph Agent Workflow 中加入人工审核机制。

基本流程：

```text
LLM Proposed Action
↓
Runtime / Permission Policy
↓
是否需要人工审核？
├─ No  → 继续执行
└─ Yes → interrupt()
          ↓
        Graph Pause
          ↓
        Human Review
          ↓
        Command(resume=...)
          ↓
        Graph Resume
```

核心 API：

```python
interrupt(...)
```

表示：

```text
暂停当前 Graph 执行，
等待外部人工输入。
```

恢复时：

```python
Command(resume=value)
```

人工审核结果会作为之前 `interrupt()` 的返回值继续参与后续路由。

需要特别注意：

> Resume 并不是重新从 `START` 执行整张 Graph。

更准确地说：

```text
读取相同 thread_id 对应的 checkpoint
↓
恢复之前的 Graph State
↓
重新进入发生 interrupt 的 Node
↓
该 Node 从函数开头重新执行
↓
interrupt() 获得 resume value
↓
继续执行后续 Graph
```

因此，`interrupt()` 所在 Node 在恢复时会重新从函数开头执行。

所以真实副作用不应放在：

```text
副作用
↓
interrupt()
```

之前。

例如 SUMO 应设计为：

```text
Approval Node
↓
interrupt()
↓
Human Approve
↓
SUMO Tool Node
```

而不是：

```text
SUMO Run
↓
interrupt()
```

这样可以避免恢复 Node 时重复执行 SUMO。

---

### 8. Tool Safety / Permission Policy

Day 8 将 Tool 的安全规则从 Agent Workflow 中进一步独立出来。

当前 Policy 使用：

```text
category
+
permission
```

描述一个 Tool。

当前类别示例：

```text
READ
COMPUTE
WRITE
DESTRUCTIVE
```

当前权限：

```text
AUTO
→ Runtime 可以自动执行

APPROVAL
→ 必须经过人工审核

DENY
→ Runtime 直接禁止执行
```

当前 Tool Policy：

```text
search_project_knowledge
→ category = READ
→ permission = AUTO

run_sumo_experiment
→ category = COMPUTE
→ permission = APPROVAL

unknown tool
→ category = UNKNOWN
→ permission = DENY
```

基本流程：

```text
LLM Tool Call
↓
get_tool_policy(tool_name)
↓
Permission Router
├─ AUTO     → Tool Node
├─ APPROVAL → Approval Node → Human
└─ DENY     → Denied Tool Node
```

这里采用：

```text
Default Deny / Fail Closed
```

即：

> 一个 Tool 如果没有明确注册安全策略，默认不允许执行。

这样做的主要意义是把：

```text
Agent Workflow
```

和：

```text
Tool Permission Policy
```

解耦。

新增 Tool 时，不需要在多个 Router 中反复写：

```python
if tool_name == ...
elif tool_name == ...
```

而是主要通过独立的 Policy Registry 配置权限。

但需要注意：

> Permission Policy 只负责“能不能执行、是否需要审核”。

如果要让 LLM 真正能够调用一个新 Tool，仍然需要：

```text
Tool Schema / TOOLS
→ 向 LLM 暴露该能力

TOOL_MAP
→ 将 Tool Name 映射到真实 Python Function

Tool Policy Registry
→ 定义执行权限
```

三者职责不同，不能混为一谈。

完整执行边界：

```text
User Intent
↓
LLM Proposal
↓
Tool Schema
↓
Runtime Validation
↓
Permission Policy
↓
Human Approval（如需要）
↓
Tool Execution
```

因此：

```text
LLM 提出 Action
≠
Action 合法
≠
Action 获准执行
```

---

### 9. Context Management

Day 8 进一步区分：

```text
Memory / Persistent State
```

与：

```text
LLM Context
```

二者不是同一个概念。

例如 LangGraph / SQLite 可以保存完整的历史：

```text
System
User 1
Assistant 1
Tool Call
Tool Result
User 2
Assistant 2
...
```

这是：

```text
Memory / State
```

但每一次真正调用 LLM 时，不一定需要把所有历史重新发送。

当前教学版 Context Manager：

```text
完整 messages
↓
build_llm_context()
↓
保留 System Prompt
+
最近 N 条非 System 消息
↓
发送给 LLM
```

因此：

```text
Full State Messages
≠
LLM Context Messages
```

例如测试：

```text
Full message count = 9
LLM context count = 5
```

说明完整 State 仍有 9 条消息，但真正送给 LLM 的只有：

```text
System
+
最近 4 条消息
```

这样可以缓解：

```text
Conversation 越长
↓
Input Tokens 越多
↓
成本增加
+
延迟增加
+
Context Window 压力增加
```

当前 Context Trimming 只是教学版，按消息数量截取。

正式 Tool Agent 还需要保证：

```text
Assistant Tool Call
+
对应 Tool Result
```

不会被裁剪拆开。

未来可以进一步扩展：

```text
Token-based Trimming
Conversation Summary
Structured State
Experiment Result Storage
```

推荐的状态分层：

```text
Conversation Messages
→ 语言上下文

Structured State
→ scenario / seed / current_stage / experiment_results

Checkpoint
→ Workflow 恢复

Experiment Storage
→ 正式科研结果
```

因此：

> Memory 负责“保存了什么”，Context Manager 负责“这一轮让 LLM 看什么”。

---

### 10. Real SUMO Integration

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
├── day08/
│   ├── __init__.py
│   ├── day08_human_interrupt_basic.py
│   ├── day08_traffic_agent_approval.py
│   ├── day08_tool_policy.py
│   ├── day08_traffic_agent_policy.py
│   ├── day08_context_management.py
│   └── day08_traffic_agent_context.py
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


### Day 8：Human Approval

```powershell
python -m day08.day08_traffic_agent_approval
```

验证：

```text
RAG Tool
→ 自动执行

SUMO Tool
→ interrupt
→ Human Approve / Reject
```

### Day 8：Permission Policy

```powershell
python -m day08.day08_traffic_agent_policy
```

验证：

```text
READ / AUTO
COMPUTE / APPROVAL
UNKNOWN / DENY
```

### Day 8：Context Management

基础测试：

```powershell
python -m day08.day08_context_management
```

接入真实 Agent：

```powershell
python -m day08.day08_traffic_agent_context
```

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
- [x] Human-in-the-loop
- [x] Tool Permission Policy
- [x] Context / Message Management
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


### Day 8：Human-in-the-loop、Tool Safety 与 Context Management

Day 8 的核心是在 Day 7 的 LangGraph Workflow 之上继续增加：

```text
人工审核
+
执行权限边界
+
上下文管理
```

#### 1. Human-in-the-loop

原有流程：

```text
LLM
↓
Runtime Validation
↓
Tool Execution
```

加入人工审核后：

```text
LLM
↓
Runtime Validation
↓
Permission Policy
↓
需要审核？
├─ No  → Tool Execution
└─ Yes → interrupt()
          ↓
        Human
          ↓
        Command(resume=...)
          ↓
        Continue
```

一个容易混淆的点：

```text
Resume
≠
重新从 START 执行整张 Graph
```

更准确的是：

```text
Checkpoint 恢复之前的 State
↓
重新进入 interrupt 所在 Node
↓
该 Node 从函数开头重新执行
↓
interrupt 获得人工 resume value
↓
继续后续路径
```

所以这里不是“创建一个全新的 State”，而是：

> 恢复 checkpoint 中已有的 Graph State，并用人工输入补充本次恢复所需要的 resume value。

#### 2. Tool Policy

之前如果把权限逻辑直接写在 Agent Router：

```python
if tool_name == "run_sumo_experiment":
    ...
```

随着 Tool 越来越多，会变得难以维护。

Day 8 将 Tool Policy 单独放在：

```text
day08_tool_policy.py
```

通过：

```python
get_tool_policy(tool_name)
```

统一获得：

```text
category
permission
reason
```

这样 Agent Workflow 只关心：

```text
AUTO
APPROVAL
DENY
```

而不需要到处判断具体 Tool 名字。

需要特别记住：

```text
Tool Schema
→ LLM 知道有哪些 Tool

TOOL_MAP
→ Python 知道 Tool Name 对应哪个真实函数

Tool Policy
→ Runtime 知道 Tool 是否允许执行
```

所以增加新 Tool 时，Policy 可以避免反复修改权限路由逻辑，但并不意味着 `TOOLS / Tool Schema` 和 `TOOL_MAP` 永远不需要更新。

#### 3. Memory ≠ Context

Day 8 另一个重要认识：

```text
Memory
≠
Context
```

Memory / State 可以保存完整历史：

```text
全部 User
全部 Assistant
Tool Calls
Tool Results
```

但是 LLM 每轮不一定需要读取全部历史。

因此引入：

```text
Context Manager
```

当前流程：

```text
完整 State messages
↓
build_llm_context()
↓
System Prompt
+
最近 N 条消息
↓
LLM
```

所以：

```text
保存多少
≠
每轮发送多少
```

这意味着以后可以同时拥有：

```text
完整持久化 Memory
+
受控的 LLM Context
```

从而减少无关历史对 Token、延迟和 Context Window 的压力。

当前按消息数量裁剪只是教学实现。

正式 Tool Agent 后续还需要处理：

```text
Tool Call / Tool Result 成对完整性
Token-based Trimming
Conversation Summary
Structured State
```

---


### Agent 职责划分

> LLM 负责理解、决策和提出 Action；Agent Runtime 负责流程编排、Validation、异常处理与执行控制；Permission Policy 决定 Tool 的权限边界；Human-in-the-loop 对需要审批的 Action 给出最终审核结果；RAG 提供项目知识；Tools 负责真正完成确定性的外部任务。

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


Day 8 进一步扩展为：

```text
LLM提出 Action
↓
Runtime Validation
↓
Permission Policy
↓
Human Approval（如需要）
↓
Tool Execution
```

因此：

```text
Valid
≠
Approved
```

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