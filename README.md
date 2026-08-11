# Traffic Simulation Agent

基于 LLM Agent 的交通仿真实验智能助手。

## Goal

通过自然语言完成：

- 交通仿真实验需求理解
- SUMO 仿真调用
- 实验参数配置
- 指标自动计算
- 多方案比较
- 实验结果解释

## Tech Stack

- Python
- DeepSeek API
- SUMO / TraCI

## Roadmap

- [x] DeepSeek API 基础调用
- [x] JSON Output
- [x] Input Validation
- [x] Tool Calling
- [ ] Agent Loop
- [ ] SUMO Integration
- [ ] RAG
- [ ] LangGraph
- [ ] MCP
- [ ] Agent Evaluation

## 笔记
LLM 负责理解和决策，Tool 负责执行，Agent Runtime 负责连接和控制两者