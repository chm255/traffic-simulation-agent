# Traffic Simulation Agent

基于 **LLM Agent + SUMO / TraCI + RAG** 的交通仿真实验智能助手。

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
- JSON / Structured Output

当前本地 Embedding 模型：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## Current Agent Architecture

当前系统架构：

```text
User
 ↓
LLM
 ↓
Agent Runtime
 ├─ Tool Calling
 ├─ Validation
 ├─ Agent Loop
 ├─ Error Handling
 └─ State / Workflow Control
 ↓
 ├───────────────┐
 ↓               ↓
RAG Tool       SUMO Tool
 ↓               ↓
Knowledge       TraCI
Base              ↓
                  SUMO
 └───────┬────────┘
         ↓
     Tool Results
         ↓
        LLM
         ↓
下一步 Tool / Final Answer
```

核心职责划分：

```text
LLM
→ 理解用户意图
→ 动态决策
→ 工具选择
→ 结果解释

Agent Runtime
→ Agent Loop
→ 参数解析
→ Validation
→ Error Handling
→ Tool Dispatch
→ 状态控制

RAG
→ 提供项目知识
→ 解决 Knowledge Gap

Tools / Python
→ 执行确定性任务
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

### 4. Real SUMO Integration

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

当前系统可以称为：

> **Traffic Simulation Agent V2**

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
├── knowledge/
│   ├── metrics.md
│   ├── scenarios.md
│   └── experiment_rules.md
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

## Running Traffic Simulation Agent V2

激活环境：

```powershell
conda activate traffic-agent
```

从项目根目录运行：

```powershell
python -m day06.day06_rag_tool_agent
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

---

## API Key

DeepSeek API Key 保存在项目根目录：

```text
api.txt
```

该文件不应提交到 Git。

请确保 `.gitignore` 包含：

```gitignore
api.txt
```

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
- [ ] LangGraph
- [ ] MCP
- [ ] Agent Evaluation
- [ ] Experiment Memory
- [ ] Scenario Modification Tools
- [ ] Automatic Experiment Comparison
- [ ] Visualization / Plot Tools
- [ ] Research Workflow Agent

---

## Notes

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