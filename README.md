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
- [x] Agent Loop
- [ ] SUMO Integration
- [ ] RAG
- [ ] LangGraph
- [ ] MCP
- [ ] Agent Evaluation

## 笔记
LLM负责理解、决策和工具选择；Agent Runtime负责循环、校验、异常处理和执行控制；Tools负责真正完成确定性的外部任务。