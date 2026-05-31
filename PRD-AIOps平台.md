# PRD：企业级 AI-Ops 智能运维平台 —— 多智能体自愈系统

## 1. 产品定位与核心设计理念

### 1.1 一句话定义
一个以 **多智能体协作** 为核心的 AIOps 平台，实现 **感知→分析→决策→执行→验证→自愈** 的完整闭环，执行失败时自动分析原因、调整策略、重新执行（最多 3 轮），3 轮仍失败则携带完整上下文升级至人工。

### 1.2 与传统运维工具的本质区别

| 维度 | 传统运维工具 | 本平台 |
|------|------------|--------|
| 交互方式 | 人敲命令，工具执行 | 人描述意图，多智能体自主协作完成 |
| 故障处理 | 告警→人分析→人修复 | 告警→Agent 自主诊断→自主修复→自主验证 |
| 失败处理 | 报错，等人来看 | Agent 分析失败原因→换方案→重试 (≤3轮)→升级 |
| 知识沉淀 | 靠人写文档 | 每次故障自动生成案例，RAG 持续进化 |
| 可观测性 | 日志+监控分离 | 全链路追踪：用户意图→Agent 决策→工具调用→系统变更 |

### 1.3 核心技术栈
| 层 | 选型 | 用途 |
|----|------|------|
| AI 编排 | LangGraph | 多智能体状态图、条件路由、Human-in-the-Loop |
| AI 框架 | LangChain | Tool 定义、RAG 链、Prompt 管理 |
| LLM | DeepSeek v4-pro (推理模型) | 主对话模型，支持 reasoning_content 推理链 |
| LLM 可观测 | LangSmith | 全链路 LLM 调用追踪、Token 统计、延迟监控 |
| 后端 | FastAPI (Python 3.11+) | REST API + SSE 流式推送 |
| 前端 | Vue 3 + JS + Element Plus (Dark Mode) | 对话面板、仪表盘、审计回放 |
| 认证 | JWT (access + refresh) | 无状态认证 |
| 数据库 | MySQL 8.0 | 审计、配置、知识库元数据 |
| 向量存储 | Chroma 0.5.23 | 知识库 RAG，持久化于 backend/chroma_data/ |
| Embedding | Ollama + qwen3-embedding:0.6b | 本地向量嵌入 (OpenAI 兼容 API) |
| K8s 交互 | kubectl (SSH 透传) | 集群只读操作，安全白名单校验 |
| Linux 交互 | paramiko SSH | 主机只读诊断命令，安全白名单校验 |

---

## 2. 多智能体架构设计

### 2.1 智能体全景图

#### Phase 3 已实现架构（7 Agent + 自愈闭环 + HITL 审批）

```
                              ┌─────────────────────────┐
                              │     用户 / 告警系统       │
                              └───────────┬─────────────┘
                                          │ 自然语言意图
                                          ▼
                              ┌─────────────────────────┐
                              │  Orchestrator Agent     │
                              │  (意图分类 & 路由)       │
                              │  • diagnosis / change   │
                              │  • inquiry              │
                              │  • target_scope 提取    │
                              └───────────┬─────────────┘
                                          │  ALL intents → observe first
                                          ▼
                              ┌─────────────────────────┐
                              │   Observe Agent          │
                              │   (数据采集 & 异常检测)    │
                              │                          │
                              │  工具:                   │
                              │  • kubectl_exec          │
                              │  • linux_exec            │
                              └───────────┬─────────────┘
                                          │ 基于 intent_type 路由
                         ┌────────────────┼────────────────┐
                         │                │                │
                         ▼                ▼                ▼
              ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
              │  Diagnose    │  │  Remedy      │  │  Knowledge   │
              │  Agent       │  │  Agent       │  │  Agent       │
              │  (诊断+假设)  │  │  (修复+审批)  │  │  (RAG 检索)  │
              └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                     │                 │                  │
                     ▼                 ▼                  │
              ┌──────────────┐  ┌──────────────┐         │
              │ (有根因时)   │  │   Verify     │         │
              │     →        │  │   Agent      │         │
              │   Remedy     │  │  (验证修复)   │         │
              └──────────────┘  └──┬───────┬───┘         │
                                   │       │              │
                              ┌────┘       └────┐         │
                              ▼                 ▼         │
                         (passed)          (failed +      │
                              │          retry ≤ 3)      │
                              │            │              │
                              │            ▼              │
                              │      ┌──────────────┐    │
                              │      │   Remedy     │    │
                              │      │  (重试修复)   │    │
                              │      └──────┬───────┘    │
                              │             │             │
                              └──────┬──────┘             │
                                     │                    │
                                     ▼                    │
                          ┌──────────────────┐           │
                          │  Orchestrator    │◄──────────┘
                          │  Final (汇总)    │
                          └────────┬─────────┘
                                   │
                                   ▼
                                [ END ]
```

**路由规则** (Phase 3 实际实现):
- `diagnosis` → observe → diagnose → (root_cause ? remedy → verify ↻ retry) → orchestrator_final
- `change`    → observe → remedy → verify ↻ retry (≤3) → orchestrator_final
- `inquiry`   → observe → knowledge → orchestrator_final

**Human-in-the-Loop (HITL)**:
- L2+ 风险命令在执行前通过 LangGraph `interrupt()` 暂停图
- 前端显示审批卡片，用户批准/拒绝后通过 `POST /api/chat/resume` 恢复
- 评审拒绝后验证 Agent 检测失败 → 自动重试 → 再次请求审批

所有意图都先经过 Observe Agent 采集实时集群数据。

#### 完整规划架构（Phase 3+ 含自愈闭环）

```
                            ┌─────────────────────────┐
                            │     用户 / 告警系统       │
                            └───────────┬─────────────┘
                                        │ 自然语言意图 / Webhook
                                        ▼
                            ┌─────────────────────────┐
                            │   Orchestrator Agent    │
                            │   (编排主控)             │
                            │   • 意图理解 & 任务分解   │
                            │   • 多智能体调度          │
                            │   • 自愈循环计数器管理     │
                            │   • 最终升级决策          │
                            └───────────┬─────────────┘
                                        │
        ┌───────────┬───────────┬───────┼───────┬───────────┬───────────┐
        │           │           │       │       │           │           │
        ▼           ▼           ▼       │       ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐    │  ┌────────┐ ┌────────┐ ┌────────┐
   │Observe │ │Diagnose│ │Remedy  │    │  │Verify  │ │Knowled.│ │Security│
   │ Agent  │ │ Agent  │ │ Agent  │    │  │ Agent  │ │ Agent  │ │ Agent  │
   │(感知)  │ │(诊断)  │ │(修复)  │    │  │(验证)  │ │(知识)  │ │(安全)  │
   └───┬────┘ └───┬────┘ └───┬────┘    │  └───┬────┘ └───┬────┘ └───┬────┘
       │          │          │         │      │          │          │
       │    ┌─────┴──────────┴─────┐   │      │          │          │
       │    │      工具池           │   │      │          │          │
       └────┤  • kubectl / K8s API │   │      │          │          │
            │  • SSH / paramiko    │◄──┘      │          │          │
            │  • Prometheus API    │          │          │          │
            │  • Loki / ELK        │          │          │          │
            │  • MySQL             │          │          │          │
            │  • HTTP / curl       │          │          │          │
            └──────────────────────┘          │          │          │
                                              ▼          ▼          ▼
                                        ┌─────────────────────────────┐
                                        │      知识 & 数据层           │
                                        │  MySQL │ Chroma │ Redis     │
                                        └─────────────────────────────┘
```

### 2.2 各智能体职责详述

#### Orchestrator Agent（编排主控）✅ Phase 1-2 已实现

**当前实现**:
- 节点: `orchestrator_router_node` (意图分类 + 路由) + `orchestrator_final_node` (结果汇总)
- 意图分类: 纯 LLM 分类为 `diagnosis | change | inquiry`，提取 target_scope `{service, namespace, node}`
- 路由: 所有 intent 先经过 observe 获取 live data，再根据 intent 分发到 diagnose / knowledge / final
- 汇总: 整合 observe + diagnose + knowledge 输出，生成自然语言最终回答

**规划完整版**:
```
输入: 用户自然语言 / 告警 Webhook
职责:
  1. 意图分类: 
     - 故障诊断 (70%)  "payment-service 崩了"
     - 变更操作 (20%)  "把 frontend 扩到 5 副本"
     - 咨询问答 (10%)  "这个集群还有多少资源"
  2. 任务分解: 将复杂意图拆解为子任务 DAG
  3. Agent 调度: 根据子任务类型分发给专业 Agent
  4. 循环控制: attempt_counter = 0 → max 3
  5. 升级决策: attempt=3 仍失败 → 打包上下文 → 通知人类
  6. 结果聚合: 汇总各 Agent 输出，生成最终报告
```

#### Observe Agent（感知智能体）✅ Phase 2 已实现

**当前实现**:
- 节点: `observe_node` — 使用 DeepSeek v4-pro 推理模型
- 工具: `kubectl_exec` (K8s 只读操作) + `linux_exec` (Linux 系统诊断)
- 双轮 LLM 调用: 第一轮 LLM 生成工具调用 → 执行 → 第二轮 LLM 分析采集数据
- 输出: `anomaly_summary` (异常描述) + `anomaly_severity` (critical / warning / info) + `tool_results`
- 安全约束: Prompt 强制生成简单命令，禁止 `&&` / `||` / `2>/dev/null` 等 shell 构造

**规划完整版**:
```
职责: 多维度数据采集 + 异常检测 + 关联分析

采集能力:
  • K8s Metrics API: CPU/Memory/Disk/Network
  • Prometheus: 自定义业务指标
  • kubectl: Pod/Deploy/Service/Event/Node 状态
  • SSH: Linux 主机 CPU/内存/磁盘/进程/网络连接
  • Loki/ELK: 应用日志
  • K8s Events: 集群事件流

分析能力:
  • 时序异常检测 (CPU 突增、内存泄漏模式、流量骤降)
  • 多指标关联 (CPU 飙升 + OOM 事件 + 日志 ERROR 频率 = 内存溢出)
  • 事件时间线重建 (Pod 被杀前 5 分钟发生了什么)
  • 依赖链追溯 (Service A 异常 → 导致 Service B 超时 → 导致 Service C 积压)

输出:
  • 异常摘要: "payment-service 3 个 Pod 在 14:32:15 同时 OOMKilled"
  • 相关指标快照: 故障时刻前后 5 分钟的资源趋势
  • 关联事件链: 事件时间线 + 依赖影响图
  • 异常严重程度: critical / warning / info
```

#### Diagnose Agent（诊断智能体）✅ Phase 2 已实现

**当前实现**:
- 节点: `diagnose_node` — 基于 Observe 采集的数据做根因分析
- 输入: `anomaly_summary` + `tool_results` (来自 Observe Agent)
- 输出: `hypotheses` (假设列表 + 置信度 + 证据) + `confirmed_root_cause` (根因 + 置信度)
- RAG 增强: 可通过 `search_knowledge_base` 检索历史相似案例辅助诊断

**规划完整版**:
```
职责: 基于 Observed 数据做根因分析

工作流程:
  1. 接收 Observe Agent 采集的多维度数据
  2. 生成诊断假设列表 (并行):
     Hypothesis A: "内存泄漏导致 OOMKill" (confidence: 0.85)
     Hypothesis B: "配置错误导致启动失败" (confidence: 0.40)
     Hypothesis C: "依赖服务不可达" (confidence: 0.30)
  3. 逐个验证假设 (主动采集额外证据):
     - 查询历史案例 (RAG): "OOMKill + payment-service + 过去30天"
     - 深度日志分析: grep ERROR/Exception 并上下文分析
     - 对比正常基线: 同时段昨天该服务内存曲线
  4. 确定根因 + 影响范围 + 建议修复方向

输出:
  • 根因: "JVM 堆内存上限 512Mi, 实际业务峰值 580Mi → OOMKill"
  • 影响: "payment-service 不可用, 上游 order-service 超时率 15%"
  • 修复方向: "提升 memory limit 至 1Gi, 调整 JVM -Xmx"
  • 置信度: 0.92
```

#### Remedy Agent（修复智能体）✅ Phase 3 已实现

**当前实现**:
- 节点: `remedy_node` — 基于 Observe/Diagnose 结果生成修复计划并执行
- LLM 生成 PLAN + COMMANDS 结构（`PLAN:` 行 + `- kubectl_exec: <cmd>` 列表）
- 风险分级: 通过 `risk_classifier.py` 对每个命令进行 L0-L4 风险定级
- HITL 审批: L2+ 命令若用户角色无权自动执行 → `interrupt()` 暂停图
- 自动审批: admin 可自动执行 L2 命令，superadmin 可自动执行 L3 命令
- 命令执行: 调用 `kubectl_exec` / `linux_exec` 工具，受 RBAC 控制
- 回退命令: LLM 未生成命令时自动生成兜底命令（基于 target_scope + anomaly）
- 输出: `remedy_plan` + `remedy_results`

**HITL 审批流程**:
```
remedy_node 生成命令列表
    ↓
risk_classifier 风险分级 (L0-L4)
    ↓
is_auto_approved(user_role, risk_level)?
    ├── YES → 直接执行所有命令
    └── NO  → interrupt() 暂停图
                ├── SSE: approval_required 事件
                ├── 前端显示审批卡片
                ├── 用户批准/拒绝 → POST /api/chat/resume
                ├── 批准 → Command(resume={approved: true}) 恢复执行
                └── 拒绝 → loop_complete=true, 不执行命令
```

**核心循环** (Phase 3 实际实现):
```
  ┌──────────────────────────────────────────────┐
  │  Round N (N=0,1,2, 共3次)                    │
  │                                              │
  │  1. Plan:  LLM 生成修复方案 (PLAN + COMMANDS) │
  │  2. Risk:  risk_classifier 风险分级           │
  │  3. HITL:  若需审批 → interrupt() 暂停        │
  │  4. Exec:  执行已批准命令 (kubectl/linux)      │
  │  5. Verify: → 交给 Verify Agent               │
  │     ├── PASS → loop_complete=true → final     │
  │     └── FAIL & retry<3 → 回到 remedy (N++)    │
  └──────────────────────────────────────────────┘
```

#### Verify Agent（验证智能体）✅ Phase 3 已实现

**当前实现**:
- 节点: `verify_node` — 修复后效果验证 + 重试决策
- 双轮 LLM 调用: 第一轮调用 kubectl_exec/linux_exec 采集状态 → 第二轮 LLM 分析结果
- 验证项: Deployment 状态、Pod 运行状态、集群 Events
- 输出: `verification_results` (health_checks + overall passed/failed) + `verification_passed`
- 重试决策: `verification_passed=false` 且 `retry_count < 3` → 路由回 remedy 节点
- 成功时设置 `loop_complete=true` 进入 orchestrator_final

**重试循环** (Phase 3 实际实现):
```
verify_node 验证
  ├── passed → loop_complete=true → orchestrator_final
  └── failed → retry_count++ 
       ├── retry_count ≤ 2 → 路由回 remedy (新方案)
       └── retry_count ≥ 3 → loop_complete=true → orchestrator_final
```

#### Knowledge Agent（知识智能体）✅ Phase 2 已实现

**当前实现**:
- 节点: `knowledge_node` — RAG 检索 + 知识库查询
- 工具: `search_knowledge_base(query)` — 语义检索 Chroma 向量库
- 向量引擎: Chroma 0.5.23 + Ollama qwen3-embedding:0.6b (本地部署)
- 知识库: 预置 10+ 条 K8s 常见故障知识（OOM、CrashLoopBackOff、ImagePullBackOff、Pending 等）
- 持久化: `backend/chroma_data/` 目录

**规划完整版**:
```
职责: 运维知识的沉淀与检索

核心功能:
  1. RAG 检索: 
     - 诊断时检索相似历史案例
     - 修复时检索已验证的修复方案
     - 咨询时检索运维文档
     
  2. 案例自动生成:
     每次完整的 "故障→诊断→修复→验证" 闭环, 
     自动生成结构化案例:
     {
       "title": "payment-service OOM 修复",
       "symptoms": ["CrashLoopBackOff", "OOMKilled", "exit code 137"],
       "root_cause": "JVM heap > memory limit",
       "solution": "调整 Deployment resources.limits.memory 512Mi→1Gi",
       "failed_attempts": [
         "Round1: 直接扩容失败-节点资源不足",
         "Round2: cordon节点失败-缺少PDB"
       ],
       "successful_approach": "释放低优服务资源后扩容",
       "verification": "Pod Running, 健康检查通过, 5min无新告警",
       "tags": ["OOM", "payment-service", "扩容", "资源不足"],
       "timestamp": "2026-05-30T14:35:00"
     }

  3. 知识图谱:
     - 自动发现服务依赖关系
     - 构建 "服务→依赖→基础设施" 拓扑图
     - 故障时辅助分析爆炸半径
     
  4. 知识衰减:
     - 超过 90 天未验证的案例标记为 "待验证"
     - K8s 版本升级后关联案例自动标记 "需重新验证"
```

#### Security & Compliance Agent（安全合规智能体）✅ Phase 3 风险分级已实现

**风险分级器** (`backend/agents/tools/risk_classifier.py`):
- 确定性 L0-L4 分类，复用 `ops_tools.py` 的 RBAC 权限集，零 LLM 调用
- 86/86 安全测试全部通过

**风险等级定义**:
| 等级 | 描述 | kubectl 操作 | Linux 操作 | 审批规则 |
|------|------|-------------|-----------|---------|
| L0 | 只读 | get/describe/logs/top/explain | df/ps/free/ss/ls/cat | 所有角色自动通过 |
| L1 | 安全写 | apply/create/label/annotate/set | touch/mkdir/cp/curl | viewer+/operator 需审批 |
| L2 | 破坏性 | delete/scale/patch/rollout restart | systemctl restart, docker restart, kill, rm | admin+ 自动通过 |
| L3 | 危险 | exec/drain/port-forward/cordon/taint | docker exec, iptables, sysctl | superadmin 自动通过 |
| L4 | 灾难 | drain, delete ns, delete pvc | dd/fdisk/mkfs/reboot/useradd | 始终需要显式审批 |

**审批决策** (Phase 3 实现):
- `is_auto_approved(risk_level, user_role)` — 基于角色自动决定
- `get_required_approver(risk_level)` — 返回需要的审批者级别
- L2+ 命令若角色权限不足 → LangGraph `interrupt()` 暂停 → SSE `approval_required` → 前端审批卡片 → `POST /api/chat/resume`

**规划完整版** (待 Phase 4):
  4. 合规审计:
     - 每次操作生成完整审计日志
     - 敏感信息自动脱敏 (password, token, secret)
     - 支持导出为 SOC2/ISO27001 合规报告

---

## 3. 记忆机制架构（Memory System）

多智能体系统的记忆不是简单的"存和取"，而是一套**分层、分域、有生命周期**的认知系统。记忆决定了一个 Agent 是"每次都从零开始"还是"越用越聪明"。

### 3.1 记忆分层模型

```
┌──────────────────────────────────────────────────────────────────┐
│                      记忆分层架构                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    L0: 感知记忆 (Sensory Memory)             │ │
│  │  容量: 巨大 | 生命周期: 秒-分钟 | 存储: Redis / 内存          │ │
│  │  内容: 原始采集数据                                            │ │
│  │  • Prometheus 拉取的时序数据快照                               │ │
│  │  • kubectl logs 的原始日志流                                   │ │
│  │  • K8s Events 事件流                                           │ │
│  │  • 当前会话的 SSE 事件缓冲区                                    │ │
│  │  作用: 为上层记忆提供原始素材，用完即焚或选择性升格              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                    选择性提取 & 摘要                               │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 L1: 工作记忆 (Working Memory)                 │ │
│  │  容量: 中等 | 生命周期: 单次会话 | 存储: LangGraph State       │ │
│  │  内容: 当前任务上下文 + 中间推理结果                            │ │
│  │  • 当前会话的 AIOpsState (完整的图状态)                         │ │
│  │  • Agent 之间的消息传递历史                                     │ │
│  │  • 诊断假设及其验证状态                                         │ │
│  │  • 自愈循环的 attempt_history                                   │ │
│  │  • 工具调用的输入输出缓存 (同一次会话内复用)                     │ │
│  │  特点: 图执行期间读写最频繁，图结束后选择性升格到 L2              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                    会话结束 → 摘要 & 结构化                        │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   L2: 情节记忆 (Episodic Memory)              │ │
│  │  容量: 大 | 生命周期: 天-月 | 存储: MySQL + Chroma             │ │
│  │  内容: 结构化的历史事件片段                                     │ │
│  │  • 完整故障案例 (symptoms → root_cause → attempts → solution)  │ │
│  │  • 每次巡检报告及其发现的异常                                    │ │
│  │  • 用户操作审计记录 (谁在何时做了什么、结果如何)                  │ │
│  │  • Agent 决策路径记录 (用于复盘和优化 prompt)                    │ │
│  │  检索方式: 语义相似度 + 标签过滤 + 时间衰减                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                   跨案例抽象 & 模式归纳                            │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  L3: 语义记忆 (Semantic Memory)               │ │
│  │  容量: 中等 | 生命周期: 月-年 | 存储: Chroma + 知识图谱        │ │
│  │  内容: 从众多案例中提炼的通用知识                               │ │
│  │  • 服务依赖拓扑 (自动发现 + 手动标注)                           │ │
│  │  • Pod/Node 的正常行为基线 (CPU/Memory 水位基线)                │ │
│  │  • 故障模式库 (OOM 模式、网络分区模式、调度失败模式...)          │ │
│  │  • 修复策略库 (每种故障模式对应的高成功率修复策略及排序)         │ │
│  │  • 运维文档/Runbook 的向量化索引                                │ │
│  │  • 基础设施元数据 (集群版本、节点规格、网络策略)                 │ │
│  │  特点: 不保存原始数据，只保存经过归纳的"认知"                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                   稳定知识 + 人工标注                              │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                 L4: 程序记忆 (Procedural Memory)              │ │
│  │  容量: 小 | 生命周期: 永久 | 存储: MySQL + System Prompt       │ │
│  │  内容: 经过验证的 SOP 和自动化流程                              │ │
│  │  • 黄金修复路径 (某种故障类型的最优修复流程)                    │ │
│  │  • 审批策略 (什么场景需要什么级别的审批)                        │ │
│  │  • Agent 行为准则 (安全策略、优先级规则、升级条件)              │ │
│  │  • 经过验证的 LangGraph 子图模板                                │ │
│  │  特点: 变更需要严格审核，视为"代码"而非"数据"                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 记忆流转与升格机制

记忆不是静止的——它在不同层级之间流动，低层记忆经过**提取→总结→结构化→验证**逐渐升格为高层记忆。

```
                    ┌─────────────────────────────────────────┐
                    │           记忆生命周期管理               │
                    └─────────────────────────────────────────┘

  L0 感知记忆 ──► 会话结束 ──► 90% 丢弃
        │                       10% 关键帧提取
        │                       
        └────── 提取关键帧 ──────► L1 工作记忆 (当前 State)
                                      │
                                      │ 会话结束
                                      ▼
                              ┌──────────────┐
                              │   记忆巩固    │  ← Consolidation Agent
                              │  (后台异步)   │     (新增)
                              └──────┬───────┘
                                     │
                          ┌──────────┼──────────┐
                          │          │          │
                          ▼          ▼          ▼
                     失败会话     成功会话     咨询会话
                          │          │          │
                          ▼          ▼          ▼
                    ┌─────────┐ ┌─────────┐ ┌──────────┐
                    │记录失败  │ │生成案例  │ │更新检索  │
                    │教训     │ │入库      │ │计数+FAQ  │
                    │(避免重复│ │(L2情节)  │ │          │
                    │犯错)    │ │          │ │          │
                    └────┬────┘ └────┬────┘ └──────────┘
                         │           │
                         └─────┬─────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  模式归纳 (Pattern)  │  ← 每隔 N 个案例触发
                    │  Mining Agent       │     (新增)
                    │                     │
                    │  分析近期案例, 发现:  │
                    │  • service-A 每48h   │
                    │    OOM 一次 (模式)   │
                    │  • node-3 磁盘每     │
                    │    周增长 15% (趋势) │
                    │  • 扩容策略B的成功率 │
                    │    比策略A高 3.2倍   │
                    └────────┬────────────┘
                             │
                             ▼
                    ┌─────────────────────┐
                    │  更新 L3 语义记忆    │
                    │  • 故障模式库        │
                    │  • 修复策略排序      │
                    │  • 基线更新          │
                    └────────┬────────────┘
                             │
                             │ 人工审核 (关键变更)
                             ▼
                    ┌─────────────────────┐
                    │  更新 L4 程序记忆    │
                    │  (变更需审批)        │
                    └─────────────────────┘
```

### 3.3 每种记忆的存储与检索

```
┌──────────┬─────────────────┬──────────────────┬──────────────────────────┐
│ 记忆层级  │ 存储引擎         │ 检索策略          │ 典型查询                  │
├──────────┼─────────────────┼──────────────────┼──────────────────────────┤
│ L0 感知   │ Redis Stream    │ 时序索引          │ "14:30-14:35 payment     │
│          │ + 内存 buffer   │ (时间窗口)        │ 的 CPU 数据"              │
├──────────┼─────────────────┼──────────────────┼──────────────────────────┤
│ L1 工作   │ LangGraph       │ 直接字段访问      │ state["collected_metrics"]│
│          │ State (内存)    │ (代码内)          │ state["attempt_history"]  │
├──────────┼─────────────────┼──────────────────┼──────────────────────────┤
│ L2 情节   │ MySQL (元数据)  │ 混合检索:         │ "payment-service OOM      │
│          │ + Chroma (向量) │ 语义相似度 0.7+   │ 且发生在过去30天内        │
│          │                 │ + 标签过滤        │ 且修复成功的案例"         │
│          │                 │ + 时间衰减        │                          │
├──────────┼─────────────────┼──────────────────┼──────────────────────────┤
│ L3 语义   │ Chroma (向量)   │ 语义检索 +        │ "OOM 类型故障的高成功率   │
│          │ + Neo4j/MySQL   │ 图谱遍历          │ 修复策略"                 │
│          │ (知识图谱)      │                   │ "payment 依赖哪些服务"    │
├──────────┼─────────────────┼──────────────────┼──────────────────────────┤
│ L4 程序   │ MySQL           │ 精确匹配          │ "L2 级别操作的审批策略"   │
│          │ + System Prompt │ + 模板注入        │ "OOM 故障的黄金修复路径"  │
└──────────┴─────────────────┴──────────────────┴──────────────────────────┘
```

### 3.4 各 Agent 如何使用记忆

不同 Agent 对记忆的读写模式完全不同：

```
┌────────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│    Agent       │  读取 (R)    │  写入 (W)    │  主要记忆层   │  典型读写模式 │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Orchestrator   │ L1, L2, L4   │ L1            │ L1           │ R: 历史案例  │
│                │              │               │              │ W: 任务分解  │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Observe        │ L0 (新建)    │ L0, L1        │ L0→L1        │ R: 实时指标  │
│                │ L3 (基线)    │               │              │ W: 采集数据  │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Diagnose       │ L1 (观测数据)│ L1 (假设,根因)│ L1, L2, L3   │ R: 相似案例  │
│                │ L2 (历史案例)│               │              │ W: 诊断结论  │
│                │ L3 (故障模式)│               │              │              │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Remedy         │ L1 (根因)    │ L1 (尝试历史)│ L1, L2, L3   │ R: 修复策略库│
│                │ L2 (过去方案)│               │              │ W: 执行结果  │
│                │ L3 (策略库)  │               │              │              │
│                │ L4 (SOP)     │               │              │              │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Verify         │ L1 (修复结果)│ L1 (验证结论)│ L1            │ R: 修复前后  │
│                │ L3 (基线)    │               │              │   快照对比   │
│                │              │               │              │ W: 验证结果  │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Knowledge      │ L2, L3 (全部)│ L2, L3       │ L2, L3        │ 高频读写     │
│                │              │               │              │ 唯一管理所有 │
│                │              │               │              │ 持久记忆的   │
│                │              │               │              │ Agent       │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Security       │ L1 (计划)    │ L1 (风险评级)│ L4            │ R: 安全策略  │
│                │ L4 (策略)    │               │              │ W: 审计记录  │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Consolidation  │ L1 (会话记录)│ L2 (案例)     │ L1→L2        │ 后台异步     │
│ (新增)         │              │               │              │ 会话结束后   │
│                │              │               │              │ 自动触发     │
├────────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Pattern Mining │ L2 (案例集)  │ L3 (模式/基线)│ L2→L3        │ 定时触发     │
│ (新增)         │              │               │              │ 跨案例分析   │
└────────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### 3.5 新增两个记忆管理 Agent

#### Consolidation Agent（记忆巩固智能体）

```
触发时机: 每次会话结束 (异步, 不阻塞 SSE 返回)
运行频率: 每会话一次
处理对象: 完整的 AIOpsState (L1 → L2)

工作流程:
  1. 接收完整会话的 AIOpsState
  
  2. 判断会话价值 (是否值得记):
     - 咨询类/简单查询 → 只更新检索计数, 不生成案例
     - 诊断+成功修复 → 生成完整案例 (高价值)
     - 诊断+修复失败+升级 → 生成失败案例 (教训)
     - 诊断但未修复 → 生成半成品案例 (待补全)
  
  3. 结构化提取:
     从 State 中提取:
     {
       "symptoms_summary":      ← state.anomaly_summary
       "root_cause_analysis":   ← state.confirmed_root_cause
       "attempts_detail":       ← state.attempt_history (每轮的 plan, result, analysis)
       "final_solution":        ← 最后一轮成功的 plan
       "verification_result":   ← state.verification_summary
       "key_metrics_snapshot":  ← state.pre_fix_snapshot, post_fix_snapshot
       "decision_path":         ← 各 Agent 的关键决策点
     }
  
  4. 向量化 & 入库:
     - 元数据 → MySQL (knowledge_cases)
     - 全文向量化 → Chroma (knowledge_chunks)
     - 提取标签: 服务名, 故障类型, 严重程度, 涉及组件
  
  5. 更新服务关联:
     - 更新或创建 "payment-service" 的服务画像
     - 记录: 该服务第N次发生OOM, 频率如何, 是否在恶化
  
  6. 检查是否需要触发 Pattern Mining:
     - 如果某个 (服务+故障模式) 近30天出现 ≥3 次 → 触发 Pattern Mining
```

#### Pattern Mining Agent（模式挖掘智能体）

```
触发时机: 
  - 定时: 每天凌晨执行
  - 事件触发: 同一(服务+故障) 30天内 ≥3 次
  - 手动触发: 用户在知识库页面点击 "分析模式"

运行频率: 每天一次 (增量) / 每周一次 (全量)
处理对象: 跨案例分析 (L2 → L3)

工作流程:
  1. 拉取近期案例集 (默认30天)
  
  2. 多维度聚合分析:
    
    a. 故障频次分析:
       发现: "payment-service 过去30天发生了 8 次 OOM, 频率上升"
       → 更新 L3: 故障模式库中 OOM 的权重和优先级
    
    b. 修复策略效果分析:
       对比: "同一故障模式下, 不同修复策略的成功率"
       发现: "OOM 场景: 策略A(直接扩容)成功率 45%, 
              策略B(先腾挪资源再扩容)成功率 82%"
       → 更新 L3: 修复策略库中的策略排序
    
    c. 根因相关性分析:
       发现: "80% 的 OOM 发生在流量高峰时段 (18:00-20:00)"
       → 更新 L3: 故障预测规则
    
    d. 服务依赖爆炸半径分析:
       发现: "payment 故障平均影响 3.2 个上游服务"
       → 更新 L3: 知识图谱中的依赖权重
    
    e. 基线漂移检测:
       发现: "node-3 的磁盘使用率每周增长15%，预计14天后满载"
       → 更新 L3: 容量预测基线
    
  3. 生成洞察报告:
     - 自然语言摘要 (给运维人员看)
     - 结构化更新 (给 Agent 用)
     - 如果发现严重趋势，自动创建巡检告警规则
  
  4. 人工审核门:
     - L3→L4 的变更 (如修改黄金修复路径) 必须人工审核
     - L2→L3 的自动更新 (如策略排序调整) 记录变更日志
```

### 3.6 记忆衰减与清理策略

```
┌──────────┬────────────────────┬──────────────────────────────────────┐
│ 记忆层    │ 衰减策略            │ 说明                                  │
├──────────┼────────────────────┼──────────────────────────────────────┤
│ L0 感知   │ TTL: 5分钟         │ Redis EXPIRE, 会话期间实时覆盖         │
│          │ (会话结束立即清理)   │                                       │
├──────────┼────────────────────┼──────────────────────────────────────┤
│ L1 工作   │ 会话结束即释放      │ LangGraph State 随图生命周期销毁       │
│          │ 重要数据升格到 L2    │                                       │
├──────────┼────────────────────┼──────────────────────────────────────┤
│ L2 情节   │ 活跃期: 90天        │ 90天内案例全量保留                     │
│          │ 衰减期: 90-365天    │ 超过90天: 保留摘要, 删除原始日志       │
│          │ 归档期: >365天      │ 超过1年: 仅保留统计摘要 (聚合数据)      │
│          │                    │ K8s 大版本升级后关联案例标记"需验证"     │
├──────────┼────────────────────┼──────────────────────────────────────┤
│ L3 语义   │ 持续更新, 不删除    │ 旧基线被新基线覆盖                     │
│          │ 保留变更历史        │ 故障模式永不删除, 只标记 "已过时"       │
│          │                    │ 知识图谱随集群变化自动更新               │
├──────────┼────────────────────┼──────────────────────────────────────┤
│ L4 程序   │ 永久保留            │ 每次变更需要审批                       │
│          │ 版本化管理          │ 保留完整变更历史 (Git-like)             │
│          │                    │ 支持回滚到历史版本                      │
└──────────┴────────────────────┴──────────────────────────────────────┘
```

### 3.7 记忆检索的核心流程

当一个 Agent 需要利用记忆时（以 Diagnose Agent 为例）：

```
Diagnose Agent 调用: recall(query="payment-service OOMKilled", context=state)

Step 1: 多路召回 (并行)
  ├─ 向量检索 (Chroma): 语义相似度 Top-20
  │   query_embedding = embed("payment-service OOMKilled 内存溢出")
  │   → 从 knowledge_chunks 检索相似案例
  │
  ├─ 标签过滤 (MySQL): 精确匹配
  │   WHERE service_name='payment-service' 
  │   AND JSON_CONTAINS(symptoms, '"OOMKilled"')
  │   → 精确查找同服务同症状案例
  │
  ├─ 图谱遍历 (知识图谱): 关联扩散
  │   payment-service → [依赖] → order-service, inventory-service
  │   → 扩大搜索: 这些上游服务最近的异常案例
  │
  └─ 时间衰减: 加权
      30天内: weight=1.0
      30-90天: weight=0.7
      90-180天: weight=0.4
      >180天: weight=0.1

Step 2: 融合排序 (RRF: Reciprocal Rank Fusion)
  合并多路结果 → 去重 → 时间衰减加权 → Top-10

Step 3: 上下文注入
  将 Top-3 最相关案例注入 Diagnose Agent 的 System Prompt:
  
  """
  ## 历史相似案例 (仅供参考)
  
  案例1 (相似度 0.89, 7天前):
    症状: payment-service CrashLoopBackOff + OOMKilled
    根因: JVM heap 512Mi 不足, 实际使用 580Mi
    修复: 扩容至 1Gi, 策略: 先释放dev资源再扩容 (1次重试)
    结果: 成功
  
  案例2 (相似度 0.76, 15天前):
    症状: payment-service OOMKilled at 19:00 (流量高峰)
    根因: 促销流量突增 3x, memory buffer 不够
    修复: 扩容至 1.5Gi + HPA 启用 (直接成功)
    结果: 成功
  
  案例3 (相似度 0.71, 45天前):
    症状: payment-service OOMKilled after deploy
    根因: 新版本引入内存泄漏
    修复: 回滚到旧版本 (直接成功)
    结果: 成功
  """
  
  同时注入 L3 策略:
  """
  ## 已验证的修复策略 (按成功率排序)
  
  OOM 类故障:
    1. 扩容 memory limit (成功率 82%)  ← 优先尝试
    2. 回滚最近部署 (成功率 68%)
    3. 迁移到资源更充裕的节点 (成功率 55%)
    4. 降低非关键服务资源配置 (作为腾挪手段)
  """
```

### 3.8 记忆对应的数据模型补充

```sql
-- ========== 新增: 记忆管理相关表 ==========

-- 服务画像 (L3 语义记忆)
CREATE TABLE service_profiles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    service_name VARCHAR(128) NOT NULL,
    namespace VARCHAR(128),
    total_incidents INT DEFAULT 0,           -- 总故障次数
    incident_frequency JSON,                 -- {"30d": 8, "90d": 15, "all": 42}
    top_failure_modes JSON,                  -- [{"mode":"OOM","count":12},{"mode":"CrashLoop","count":5}]
    normal_baseline JSON,                    -- {"cpu_p50":0.3,"memory_p50":"400Mi","restart_rate":0.01}
    dependency_graph JSON,                   -- {"depends_on":["mysql","redis"],"depended_by":["order","web"]}
    blast_radius_avg FLOAT,                  -- 平均影响上游服务数
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_service (service_name, namespace)
);

-- 故障模式库 (L3 语义记忆)
CREATE TABLE failure_patterns (
    id INT PRIMARY KEY AUTO_INCREMENT,
    pattern_name VARCHAR(128),               -- "OOM-Kill", "CrashLoopBackOff", "ImagePullBackOff"
    category VARCHAR(64),                    -- "resource", "configuration", "network", "dependency"
    typical_symptoms JSON,                   -- 典型症状列表
    common_root_causes JSON,                 -- [{"cause":"...","probability":0.45}]
    ranked_strategies JSON,                  -- [{"strategy":"扩容","success_rate":0.82,"avg_attempts":1.3}]
    occurrence_count INT DEFAULT 0,
    severity_distribution JSON,              -- {"critical":0.6,"warning":0.3,"info":0.1}
    avg_time_to_resolve_seconds INT,         -- 平均修复耗时
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 记忆检索日志 (用于优化检索质量)
CREATE TABLE memory_retrieval_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36),
    agent_name VARCHAR(64),
    query_text TEXT,
    query_embedding JSON,
    retrieved_case_ids JSON,                 -- 召回的案例 ID 列表
    selected_case_ids JSON,                  -- 实际使用的案例 ID
    user_feedback ENUM('helpful', 'not_helpful', 'not_relevant'),
    retrieval_latency_ms INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 基线快照 (L3 语义记忆 - 用于趋势分析)
CREATE TABLE baseline_snapshots (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_type ENUM('service', 'node', 'namespace', 'cluster'),
    target_name VARCHAR(128),
    metric_name VARCHAR(64),                 -- cpu_usage, memory_usage, disk_usage
    metric_value JSON,                       -- {"p50":..., "p95":..., "p99":..., "avg":...}
    sample_period VARCHAR(16),               -- "7d", "30d", "90d"
    snapshot_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_baseline_target (target_type, target_name, snapshot_date)
);

-- 记忆变更日志 (L3→L4 变更审计)
CREATE TABLE memory_change_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    memory_type ENUM('L2', 'L3', 'L4'),
    change_type ENUM('create', 'update', 'delete', 'decay', 'consolidate'),
    source_entity VARCHAR(64),               -- 变更来源: knowledge_cases / failure_patterns / service_profiles
    source_id INT,
    change_description TEXT,
    previous_value JSON,
    new_value JSON,
    triggered_by VARCHAR(64),                -- 'auto' / 'pattern_mining' / 'user_id'
    approved_by INT,                         -- L3→L4 变更需要审批
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.9 记忆驱动的智能体行为进化

```
┌─────────────────────────────────────────────────────────────────┐
│              记忆如何让 Agent 越来越聪明                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  第1个 OOM 案例 (冷启动):                                        │
│    Diagnose: "我先查 Prometheus, 看看日志, 分析一下..."          │
│    耗时: 45s, 尝试次数: 2                                        │
│    → 生成案例 #1                                                 │
│                                                                  │
│  第3个 OOM 案例:                                                 │
│    Diagnose: "OOMKilled? 过去30天有2个同类案例,                  │
│               都是 JVM heap 超限, 我先验证这个方向"               │
│    耗时: 20s, 尝试次数: 1                                        │
│    → Pattern Mining 发现: "payment OOM 频率上升"                 │
│                                                                  │
│  第8个 OOM 案例:                                                 │
│    Diagnose: "payment 又 OOM 了 (第8次),                         │
│              历史数据显示 80% 发生在 18-20 点流量高峰,           │
│              最优修复策略是腾挪资源后扩容 (成功率82%),            │
│              跳过假设验证，直接用最优策略"                        │
│    耗时: 8s, 尝试次数: 1 (直接用最优策略)                        │
│    → Pattern Mining 建议: "建议为该服务启用 HPA"                 │
│                                                                  │
│  巡检主动发现:                                                   │
│    Observe Agent 发现 18:00 payment CPU 开始上升                 │
│    → 匹配模式: "这是 OOM 前兆模式 (置信度 0.78)"                 │
│    → 主动建议: "建议现在预扩容 payment, 避免 19:00 OOM"          │
│    → 用户确认后自动执行, 故障被提前消灭                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. LangGraph 状态图设计（核心）

### 4.1 全局状态定义

#### Phase 3 当前实现 (`backend/agents/state.py`)

```python
from typing import TypedDict

class AIOpsState(TypedDict, total=False):
    # 用户输入 & 路由控制
    user_input: str
    user_role: str            # viewer | operator | admin | superadmin
    session_id: str
    intent_type: str          # diagnosis | change | inquiry
    target_scope: dict        # {service, namespace, node}
    flow_stage: str
    current_agent: str

    # Observe Agent 输出
    collected_data: dict
    anomaly_summary: str
    anomaly_severity: str     # critical | warning | info

    # Diagnose Agent 输出
    hypotheses: list          # [{hypothesis, confidence, evidence}]
    confirmed_root_cause: dict

    # Knowledge Agent 输出
    rag_context: str          # 检索到的知识片段

    # Remedy Agent (Phase 3 新增)
    remedy_plan: dict         # {"strategy": str, "commands": [{tool, args, risk_level}]}
    remedy_results: list[dict]  # [{command, success, output, attempt, risk_level}]
    remedy_attempts: int      # 当前尝试次数
    remedy_needed: bool       # 是否需要进入自愈循环

    # HITL 审批 (Phase 3 新增)
    approval_requests: list[dict]  # [{risk_level, commands, reason, status}]
    approval_decisions: dict  # {"approved": bool, "reason": str}

    # Verify Agent (Phase 3 新增)
    verification_results: dict  # {"health_checks": [...], "overall": "passed"|"failed"}
    verification_passed: bool

    # 自愈循环控制 (Phase 3 新增)
    loop_complete: bool       # 结束标志
    retry_count: int          # 总重试次数 (max 3)

    # 通用字段
    messages: list[dict]
    tool_results: list[dict]
    reasoning_trace: list     # DeepSeek reasoning_content 累积
    final_response: str
    error: str
    errors: list[str]
```

#### 完整规划版（Phase 3+ 含自愈闭环字段）

```python
from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum

class RiskLevel(str, Enum):
    L0 = "L0"  # 只读
    L1 = "L1"  # 低风险
    L2 = "L2"  # 中风险
    L3 = "L3"  # 高风险
    L4 = "L4"  # 毁灭操作

class AIOpsState(TypedDict):
    # === 用户输入 ===
    user_intent: str                    # 原始输入
    intent_type: str                    # diagnosis / change / inquiry
    target_scope: Dict[str, Any]        # {service, namespace, node, host}
    session_id: str
    
    # === Observe 阶段 ===
    collected_metrics: Dict[str, Any]   # CPU/Memory/Disk 等时序数据
    collected_logs: List[Dict]          # 相关日志行
    collected_events: List[Dict]        # K8s 事件
    collected_topology: Dict            # 服务依赖拓扑
    anomaly_summary: str                # 异常检测结果摘要
    anomaly_severity: str               # critical / warning / info
    
    # === Diagnose 阶段 ===
    hypotheses: List[Dict]              # [{hypothesis, confidence, evidence}]
    confirmed_root_cause: Dict          # {cause, confidence, evidence_chain, impact_scope}
    historical_cases: List[Dict]        # RAG 检索到的相似案例
    
    # === Remedy 阶段 (自愈循环) ===
    attempt_count: int                  # 0..3
    max_attempts: int                   # 3
    current_plan: Dict                  # 当前修复方案
    attempt_history: List[Dict]         # 每轮记录
    remedy_status: str                  # pending / executing / success / failed / escalated
    
    # === Verify 阶段 ===
    pre_fix_snapshot: Dict              # 修复前指标快照
    post_fix_snapshot: Dict             # 修复后指标快照
    health_check_passed: bool
    regression_detected: bool
    verification_summary: str
    
    # === Security ===
    risk_level: RiskLevel
    needs_approval: bool
    approval_status: str
    approved_by: Optional[str]
    
    # === 流程控制 ===
    current_agent: str
    flow_stage: str
    errors: List[str]
    
    # === 输出 ===
    final_summary: str
    sse_events: List[Dict]
    
    # === 可观测性 ===
    trace_id: str
    langsmith_run_id: str
```

### 4.2 LangGraph 状态图

#### Phase 3 当前实现 (`backend/agents/graph.py`)

```
                         ┌─────────┐
                         │  START   │
                         └────┬─────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  orchestrator       │  ← 意图分类 + target_scope 提取
                   │  (router_node)      │     remedy_needed / retry_count 初始化
                   └─────────┬───────────┘
                             │ ALL intents → observe
                             ▼
                   ┌─────────────────────┐
                   │  observe_node       │  ← kubectl_exec + linux_exec
                   │  (数据采集+异常检测)  │
                   └─────────┬───────────┘
                             │ 基于 intent_type 条件路由
              ┌──────────────┼──────────────────┐
              │              │                  │
              ▼              ▼                  ▼
        intent=         intent=            intent=
        diagnosis       change             inquiry
              │              │                  │
              ▼              ▼                  ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │  diagnose    │ │  remedy      │ │  knowledge   │
   │  (假设+根因) │ │  (修复+审批)  │ │  (RAG 检索)  │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                  │
     root_cause?           ▼                  │
     ├─YES → remedy   ┌──────────────┐       │
     └─NO  → final   │   verify     │       │
                     │  (验证修复)   │       │
                     └──┬───────┬───┘       │
                        │       │            │
                   ┌────┘       └────┐       │
                   ▼                 ▼       │
              (passed)         (failed +     │
                   │          retry ≤ 2)    │
                   │            │            │
                   │            ▼            │
                   │      ┌──────────┐      │
                   │      │  remedy  │      │
                   │      │ (重试修复)│      │
                   │      └────┬─────┘      │
                   │           │             │
                   └─────┬─────┘             │
                         │                   │
                         ▼                   │
                ┌──────────────────┐        │
                │  orchestrator    │◄───────┘
                │  (final_node)    │  ← 汇总所有 Agent 输出
                └────────┬─────────┘     (含 remedy + verify 结果)
                         │
                         ▼
                       [ END ]
```

**关键设计决策**:
- 所有意图先经过 Observe Agent 采集 live data
- `change` 意图直接进入 remedy（跳过 diagnose），适合用户明确操作请求
- `diagnosis` 意图在 diagnose 生成根因后才进入 remedy
- Verify → Remedy 重试循环最多 3 次 (retry_count 0→1→2→loop_complete)
- L2+ 命令在 remedy 中触发 LangGraph `interrupt()` 暂停 → HITL 审批 → `Command(resume=...)` 恢复
- MemorySaver checkpointer 按 `thread_id=session_id` 持久化检查点

#### 完整规划版（Phase 4+ 扩展）

```
                          ┌─────────┐
                          │  START   │
                          └────┬─────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  orchestrator_node  │  ← 意图分类、任务分解
                    └─────────┬───────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
           intent=      intent=       intent=
          diagnosis     change        inquiry
                │             │             │
                ▼             │             ▼
    ┌───────────────────┐    │    ┌───────────────────┐
    │  observe_node     │    │    │  knowledge_rag    │
    │  (数据采集+异常检测)│    │    │  (直接检索回答)    │
    └────────┬──────────┘    │    └────────┬──────────┘
             │               │             │
             ▼               │             ▼
    ┌───────────────────┐    │    ┌───────────────────┐
    │  diagnose_node    │    │    │  finalize_node    │
    │  (根因分析+RAG)   │    │    │  (生成回答→END)   │
    └────────┬──────────┘    │    └───────────────────┘
             │               │
             ▼               │
    ┌───────────────────┐    │
    │  remedy_plan_node │◄───┘  ← 制定修复方案
    │  (方案生成)        │
    └────────┬──────────┘
             │
             ▼
    ┌───────────────────┐
    │  security_review  │  ← 安全审查 + 风险定级
    └────────┬──────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
  需要审批          无需审批
    │                 │
    ▼                 │
┌──────────────┐      │
│ human_approval│      │
│ (中断等待)    │      │
└──────┬───────┘      │
       │              │
   ┌───┴───┐          │
   ▼       ▼          │
 通过    拒绝/超时     │
   │       │          │
   │       ▼          │
   │   ┌─────────┐    │
   │   │finalize │    │
   │   │(拒绝说明)│    │
   │   └────┬────┘    │
   │        │         │
   │        ▼         │
   │       END        │
   │                  │
   └────────┬─────────┘
            │
            ▼
┌──────────────────────┐
│  remedy_execute_node │  ← 执行修复命令
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  remedy_analyze_node │  ← LLM 深度分析执行结果
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
  成功         失败
     │           │
     │      ┌────┴────┐
     │      │         │
     │      ▼         ▼
     │   attempt    attempt
     │    < 3        >= 3
     │      │         │
     │      ▼         ▼
     │  ┌────────┐ ┌──────────┐
     │  │re-analyze│ │escalate │
     │  │+ re-plan│ │to_human │
     │  │attempt++│ └────┬─────┘
     │  └────┬────┘      │
     │       │           ▼
     │       │      ┌─────────┐
     │       │      │finalize │
     │       │      └────┬────┘
     │       │           │
     │       │           ▼
     │       │          END
     │       │
     │       └──────→ 回到 remedy_execute_node
     │
     ▼
┌──────────────────────┐
│  verify_node         │  ← 验证修复效果
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
  验证通过    验证失败
     │           │
     │           ▼
     │       attempt < 3 → 回到 re-analyze (消耗一次)
     │       attempt >= 3 → escalate_to_human
     │
     ▼
┌──────────────────────┐
│  knowledge_record    │  ← 自动生成案例入库
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  finalize_node       │  ← 生成完整操作报告
└──────────┬───────────┘
           │
           ▼
          END
```

### 4.3 自愈循环关键节点伪代码

```python
# === REMEDY ANALYZE NODE (自愈循环的核心) ===

def remedy_analyze_node(state: AIOpsState) -> AIOpsState:
    """
    分析执行结果，决定继续重试还是升级
    """
    last_attempt = state["attempt_history"][-1]
    
    # 构建分析 Prompt
    analysis_prompt = f"""
    你是 K8s 运维专家。分析以下执行结果并给出下一步建议。
    
    ## 原始问题
    {state['user_intent']}
    
    ## 根因诊断
    {state['confirmed_root_cause']}
    
    ## 第 {state['attempt_count']} 次尝试
    ### 执行方案
    {last_attempt['plan']}
    
    ### 执行的命令
    {last_attempt['commands']}
    
    ### 执行输出
    stdout: {last_attempt['stdout']}
    stderr: {last_attempt['stderr']}
    exit_code: {last_attempt['exit_code']}
    
    ### 任务
    1. 判断执行是否成功
    2. 如果失败，分析根本原因（不是表面原因）
    3. 基于失败原因，提出一个新的、不同的修复方案（不要重复同样的错误）
    4. 评估新方案的预期效果和风险
    """
    
    analysis = llm.invoke(analysis_prompt)
    
    if analysis["success"]:
        state["remedy_status"] = "success"
        # 进入 verify_node
    elif state["attempt_count"] >= state["max_attempts"]:
        state["remedy_status"] = "failed"
        # 打包升级信息
        state["escalation_context"] = build_escalation_context(state)
        # 进入 escalate_to_human_node
    else:
        state["attempt_count"] += 1
        state["current_plan"] = analysis["new_plan"]
        state["attempt_history"][-1]["analysis"] = analysis["failure_analysis"]
        state["attempt_history"][-1]["adjusted_strategy"] = analysis["adjusted_strategy"]
        # 回到 remedy_execute_node (重新执行)

    return state
```

### 4.4 SSE 事件流设计

#### Phase 3 已实现事件（18 种）

| 事件 | 触发时机 | 前端展示 | Phase |
|------|----------|----------|-------|
| `agent_active` | 每个 Agent 节点开始时 | Agent 阶段指示器（亮起当前颜色） | P2 |
| `agent_reasoning` | LLM 返回 reasoning_content 时 | 可展开的 DeepSeek 推理链 | P2 |
| `tool_call` | Agent 调用工具时 | 终端风格命令卡片（cyan 等宽字体） | P2 |
| `tool_result` | 工具执行完成时 | 命令输出展示 | P2 |
| `anomaly_detected` | Observe 发现异常时 | 异常高亮卡片（红/黄/蓝 severity 左边框） | P2 |
| `hypothesis` | Diagnose 生成假设时 | 假设卡片（琥珀色 + 置信度进度条） | P2 |
| `root_cause` | Diagnose 确认根因时 | 根因面板（红色 accent） | P2 |
| `rag_context` | Knowledge 检索完成时 | RAG 引用卡片（绿色图标） | P2 |
| `agent_response` | Orchestrator Final 汇总 | 最终自然语言回答 | P2 |
| `remedy_plan` | Remedy 生成修复方案时 | 蓝色修复计划卡（strategy + 命令列表 + 风险徽章） | **P3** |
| `approval_required` | HITL 暂停等待审批时 | 红色边框审批卡（命令列表 + 批准/拒绝按钮） | **P3** |
| `graph_paused` | 图执行暂停时 | loading=false，前端停止等待流 | **P3** |
| `approval_result` | POST /resume 后恢复时 | 审批结果提示 | **P3** |
| `remedy_executing` | 执行修复命令时 | 命令执行中状态 (spinner) | **P3** |
| `remedy_result` | 修复命令执行完成时 | 成功/失败状态（绿色✓ / 红色✗） | **P3** |
| `verification_status` | Verify 检查完成时 | 验证清单（passed/warning/failed） | **P3** |
| `retry_attempt` | 自愈循环重试时 | 重试进度条（attempt 1/3 → 2/3 → 3/3） | **P3** |
| `done` | 会话完成 | 关闭流，触发回调 | P2 |

#### 规划完整版（Phase 3+ 含自愈闭环事件）

用户在前端将看到 Agent 的完整思考过程，包括每次重试的决策：

```
[SSE] event: stage_enter       | data: {"stage":"observe","message":"开始采集多维数据..."}
[SSE] event: tool_call          | data: {"agent":"observe","tool":"prometheus_query","args":"..."}
[SSE] event: tool_result        | data: {"agent":"observe","output":"CPU 85% at 14:32:15"}
[SSE] event: agent_thought      | data: {"agent":"observe","content":"检测到 CPU 异常峰值 + OOMKilled 事件"}
[SSE] event: anomaly_detected   | data: {"severity":"critical","summary":"payment-service OOM"}
[SSE] event: stage_complete     | data: {"stage":"observe","summary":"采集完成, 发现1个严重异常"}

[SSE] event: stage_enter       | data: {"stage":"diagnose","message":"开始根因分析..."}
[SSE] event: hypothesis         | data: {"hypothesis":"内存泄漏","confidence":0.85,"evidence":["OOMKilled","内存持续增长"]}
[SSE] event: hypothesis         | data: {"hypothesis":"配置错误","confidence":0.30,"evidence":["最近一次部署在1h前"]}
[SSE] event: rag_query          | data: {"query":"payment-service OOM 历史案例","results_count":3}
[SSE] event: root_cause_found   | data: {"cause":"JVM heap 超限","confidence":0.92}
[SSE] event: stage_complete     | data: {"stage":"diagnose","summary":"根因: 内存limit 512Mi不够, 实际峰值580Mi"}

[SSE] event: stage_enter       | data: {"stage":"remedy","attempt":1,"message":"第1次修复尝试..."}
[SSE] event: remedy_plan        | data: {"plan":"扩容 memory limit 512Mi → 1Gi","risk":"L2"}
[SSE] event: approval_required  | data: {"level":"L2","commands":["kubectl patch deploy..."]}
[SSE] event: approval_granted   | data: {"by":"user:zhangsan","at":"14:35:01"}
[SSE] event: tool_call          | data: {"tool":"kubectl_patch","command":"kubectl patch deploy payment --patch '...'"}
[SSE] event: tool_result        | data: {"exit_code":1,"stderr":"Error: insufficient memory on nodes"}
[SSE] event: attempt_failed     | data: {
                                    "attempt":1,
                                    "reason":"节点资源不足, Pod 无法调度",
                                    "analysis":"当前3个节点可用内存总量仅200Mi, 扩容1Gi需要更多资源"
                                  }
[SSE] event: retry_planning     | data: {"attempt":2,"message":"正在分析失败原因并调整策略..."}
[SSE] event: remedy_plan        | data: {"plan":"方案B: 临时降低dev环境资源 + 扩容payment","risk":"L2"}
[SSE] event: tool_call          | data: {"tool":"kubectl_patch","command":"降低dev资源→扩容payment→恢复dev"}
[SSE] event: tool_result        | data: {"exit_code":0,"stdout":"deployment.apps/payment patched"}
[SSE] event: attempt_success    | data: {"attempt":2,"message":"第2次尝试成功！"}

[SSE] event: stage_enter       | data: {"stage":"verify","message":"验证修复效果..."}
[SSE] event: tool_call          | data: {"tool":"health_check","target":"payment-service"}
[SSE] event: tool_result        | data: {"status":200,"latency_ms":45}
[SSE] event: verification_pass  | data: {"checks":{"pod_running":true,"health_200":true,"no_new_alerts":true}}
[SSE] event: stage_complete     | data: {"stage":"verify","summary":"所有验证通过"}

[SSE] event: knowledge_record   | data: {"case_id":"INC-2026-0042","title":"payment-service OOM 自愈"}
[SSE] event: done               | data: {
                                    "session_id":"abc123",
                                    "total_attempts":2,
                                    "total_tokens":18450,
                                    "duration_seconds":127,
                                    "final_status":"success",
                                    "summary":"payment-service 内存溢出已修复。共尝试2次。\n"
                                             "Round1 失败: 节点资源不足。\n"
                                             "Round2 成功: 临时调整dev资源后扩容。\n"
                                             "建议: 扩容集群节点,当前资源紧张。"
                                  }
```

---

---

## 4.5 工具架构与安全模型 ✅ Phase 3

### 4.5.1 工具架构总览

Phase 3 包含 3 个核心工具模块：

| 工具 | 文件 | 能力 | 安全校验 | Phase |
|------|------|------|----------|-------|
| `kubectl_exec(command)` | `ops_tools.py` | 通用 kubectl 操作 | 动词 + 子命令白名单 × RBAC | P2 |
| `linux_exec(command)` | `ops_tools.py` | 通用 Linux 系统操作 | 命令 + 子命令白名单 × RBAC | P2 |
| `risk_classifier` | `risk_classifier.py` | L0-L4 风险分级 + 自动审批决策 | 确定性分类，复用 RBAC 权限集 | **P3** |

### 4.5.2 风险分级器 (`risk_classifier.py`) ✅ Phase 3

确定性 L0-L4 分类器，复用 `ops_tools.py` 的 RBAC 权限集。零 LLM 调用，纯规则匹配。

**API**:
- `classify_kubectl_risk(command: str) -> str` — 基于 kubectl 动词分类 (get/describe=L0, apply/create=L1, delete/scale=L2, exec/drain=L3, drain=L4)
- `classify_linux_risk(command: str) -> str` — 基于 Linux 命令分类，含 systemctl/docker/crontab 子命令处理
- `classify_ops_risk(tool_name: str, tool_args: dict) -> str` — 统一入口，自动分发
- `is_auto_approved(risk_level: str, user_role: str) -> bool` — 角色 × 风险自动审批规则
- `get_required_approver(risk_level: str) -> str` — 返回需要的审批者级别

**自动审批矩阵**:
| 风险 | viewer | operator | admin | superadmin |
|------|--------|----------|-------|------------|
| L0 (只读) | ✅ | ✅ | ✅ | ✅ |
| L1 (安全写) | ❌ 需审批 | ❌ 需审批 | ✅ | ✅ |
| L2 (破坏性) | ❌ 需审批 | ❌ 需审批 | ✅ | ✅ |
| L3 (危险) | ❌ 需审批 | ❌ 需审批 | ❌ 需审批 | ✅ |
| L4 (灾难) | ❌ 需审批 | ❌ 需审批 | ❌ 需审批 | ❌ 需审批 |

**验证**: 86/86 单元测试全部通过

### 4.5.3 RBAC 权限模型

工具权限按用户角色分级，通过 `contextvars` 在请求链路中传递角色上下文。

| 操作类型 | viewer | operator | admin | superadmin |
|----------|--------|----------|-------|------------|
| kubectl get/describe/logs/top/explain | ✅ | ✅ | ✅ | ✅ |
| kubectl rollout status/history | ✅ | ✅ | ✅ | ✅ |
| kubectl apply/create/edit/patch/label | ❌ | ❌ | ✅ | ✅ |
| kubectl delete (pods/services/deploys) | ❌ | ❌ | ✅ | ✅ |
| kubectl scale/rollout restart | ❌ | ❌ | ✅ | ✅ |
| kubectl exec/cp/port-forward | ❌ | ❌ | ❌ | ✅ |
| kubectl drain/cordon/taint | ❌ | ❌ | ❌ | ✅ |
| kubectl 危险操作 (delete ns/pvc) | ❌ | ❌ | ❌ | ✅ |
| Linux 只读 (df/ps/free/ss/ls...) | ✅ | ✅ | ✅ | ✅ |
| systemctl start/stop/restart | ❌ | ❌ | ✅ | ✅ |
| docker start/stop/restart/rm | ❌ | ❌ | ✅ | ✅ |
| apt/yum install/update | ❌ | ❌ | ✅ | ✅ |
| kill/killall | ❌ | ❌ | ✅ | ✅ |
| rm/cp/mv/touch/chmod | ❌ | ❌ | ✅ | ✅ |
| iptables/firewall-cmd | ❌ | ❌ | ❌ | ✅ |
| reboot/shutdown/init | ❌ | ❌ | ❌ | ✅ |
| useradd/usermod/userdel | ❌ | ❌ | ❌ | ✅ |
| Shell 元字符注入 (`;&|$(){}\<>`) | ❌ | ❌ | ❌ | ❌ |

**实现**: `ops_tools.py` 中使用三种权限集：
- `READONLY_*_VERBS/COMMANDS` — 所有角色
- `ADMIN_*_VERBS/COMMANDS` — admin + superadmin
- `SUPERADMIN_*_VERBS/COMMANDS` — superadmin only

### 4.5.4 kubectl_exec 安全模型 (RBAC)

```
Verb (viewer/operator):
  get, describe, logs, top, explain, version, cluster-info,
  api-resources, api-versions, rollout (仅 status/history)

额外 Verb (admin):
  apply, create, delete, edit, patch, scale, label, annotate,
  autoscale, set, rollout (含 restart/undo)

额外 Verb (superadmin):
  exec, cp, port-forward, drain, cordon, uncordon, taint, certificate

安全规则:
  - 禁止 Shell 元字符: [;&`$(){}<>\\] (所有角色)
  - 子命令白名单按角色分级校验
```

### 4.5.5 linux_exec 安全模型 (RBAC)

```
命令 (viewer/operator, 30+ 个):
  ls, cat, head, tail, find, stat | df, du, mount, lsblk
  ps, pstree, top, free, vmstat, dmesg, uname, uptime
  ip, ifconfig, ss, netstat, ping | systemctl (仅 status/list-units)
  docker (仅 ps/logs/images/stats/inspect) | journalctl, lsof, which

额外命令 (admin, 20+ 个):
  apt, yum, dnf | kill, killall | rm, cp, mv, touch, chmod, chown
  curl, wget | sysctl, modprobe, swapoff, swapon
  systemctl (含 start/stop/restart/enable/disable)
  docker (含 start/stop/restart/rm/exec/pull)
  crontab (含 -e)

额外命令 (superadmin):
  dd, fdisk, mkfs, parted | iptables, firewall-cmd, ufw
  reboot, shutdown, init | useradd, usermod, userdel, passwd

Pipe 白名单 (所有角色):
  grep, head, tail, wc, sort, uniq, cut, awk, sed, tr, column

安全规则:
  - 禁止 Shell 元字符: [;&`$(){}<>\\] (所有角色)
  - 最多 1 个 pipe (所有角色)
  - 子命令白名单按角色分级校验
```

### 4.5.6 安全测试覆盖

**RBAC 安全测试**: 49 条全部通过 (kubectl 26 + linux 23) + **风险分级器测试**: 86 条全部通过 = **总计 135 条安全测试**

```
✅ kubectl_viewer_read: viewer 可执行 get/describe/logs
✅ kubectl_viewer_write: viewer 被拒绝 delete/apply/scale/exec
✅ kubectl_admin_write: admin 可执行 delete/apply/scale/rollout restart
✅ kubectl_admin_dangerous: admin 被拒绝 exec/drain/port-forward
✅ kubectl_superadmin_full: superadmin 可执行 exec/drain/taint
✅ linux_viewer_read: viewer 可执行 df/ps/systemctl status
✅ linux_viewer_write: viewer 被拒绝 systemctl restart/docker restart/rm/apt
✅ linux_admin_write: admin 可执行 systemctl restart/docker restart/kill/rm/apt
✅ linux_admin_dangerous: admin 被拒绝 iptables/useradd
✅ linux_superadmin_full: superadmin 可执行 iptables/reboot/useradd
✅ shell_injection_all: 所有角色被拒绝 ; && $( `` {} <> \\
✅ pipe_all: 所有角色支持 grep/head/tail/wc/sort 管道
✅ risk_classifier L0-L4: 86 条分级 + 自动审批 + 审批级别测试全部通过
```

### 4.5.6 Prompt 安全约束

Observe Agent 的 System Prompt 包含命令约束和角色权限级别声明，LLM 可根据角色生成相应权限的操作指令。

---

## 5. 数据库设计

### 5.1 核心模型 ER 关系

```
users ──1:N──▶ sessions ──1:N──▶ messages
  │               │
  │               └──1:N──▶ audit_logs ──1:N──▶ command_executions
  │                              │
  │                              └──1:N──▶ approval_records
  │
  └──1:N──▶ knowledge_cases ──1:N──▶ case_attempts (记录每次重试)
                 │
                 └──1:N──▶ knowledge_chunks (向量块)
```

### 5.2 表结构

```sql
-- ========== 用户 & 权限 ==========
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('viewer', 'operator', 'admin', 'superadmin') NOT NULL DEFAULT 'viewer',
    email VARCHAR(128),
    status ENUM('active', 'disabled') DEFAULT 'active',
    last_login_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ========== 会话 & 消息 ==========
CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,  -- UUID
    user_id INT NOT NULL,
    title VARCHAR(256),           -- 自动摘要生成
    intent_type ENUM('diagnosis', 'change', 'inquiry'),
    risk_level ENUM('L0','L1','L2','L3','L4'),
    status ENUM('active', 'completed', 'escalated', 'cancelled'),
    trace_id VARCHAR(64),         -- LangSmith trace
    total_attempts INT DEFAULT 0,
    final_status ENUM('success', 'partial_success', 'failed', 'escalated', 'cancelled'),
    total_tokens INT DEFAULT 0,
    duration_seconds INT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36) NOT NULL,
    role ENUM('user', 'agent', 'system'),
    agent_name VARCHAR(64),       -- orchestrator / observe / diagnose / remedy / verify / knowledge / security
    message_type ENUM(
        'user_input', 'agent_thought', 'stage_enter', 'stage_complete',
        'tool_call', 'tool_result', 'hypothesis', 'anomaly_detected',
        'root_cause', 'remedy_plan', 'attempt_start', 'attempt_result',
        'approval_required', 'approval_granted', 'approval_denied',
        'verification', 'knowledge_record', 'summary', 'error', 'done'
    ),
    content JSON,                  -- 结构化消息体
    token_count INT,
    sequence_num INT,              -- 消息序号 (用于回放)
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    INDEX idx_session_seq (session_id, sequence_num)
);

-- ========== 审计日志 ==========
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36),
    user_id INT,
    action_type ENUM('diagnosis', 'change', 'inquiry', 'inspection'),
    intent_summary TEXT,              -- 用户原始意图摘要
    agent_decision_path JSON,         -- 完整 Agent 决策链
    risk_level ENUM('L0','L1','L2','L3','L4'),
    approval_id BIGINT,
    attempt_summary JSON,            -- [{attempt, plan, result, analysis}]
    final_result ENUM('success', 'failed', 'escalated', 'cancelled'),
    trace_id VARCHAR(64),
    langsmith_url VARCHAR(512),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_audit_user (user_id, created_at),
    INDEX idx_audit_session (session_id)
);

CREATE TABLE command_executions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    audit_log_id BIGINT,
    session_id VARCHAR(36),
    attempt_num INT,                  -- 第几次尝试
    command_text TEXT NOT NULL,
    command_hash VARCHAR(64),         -- SHA256 (用于去重/审计)
    target_type ENUM('k8s', 'linux', 'http', 'sql'),
    target_host VARCHAR(128),
    target_namespace VARCHAR(128),
    stdout TEXT,
    stderr TEXT,
    exit_code INT,
    duration_ms INT,
    executed_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    FOREIGN KEY (audit_log_id) REFERENCES audit_logs(id),
    INDEX idx_cmd_audit (audit_log_id)
);

-- ========== 审批记录 ==========
CREATE TABLE approvals (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36) NOT NULL,
    audit_log_id BIGINT,
    risk_level ENUM('L2','L3','L4') NOT NULL,
    requested_by INT NOT NULL,        -- user_id
    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'approved', 'rejected', 'timeout') DEFAULT 'pending',
    responded_by INT,
    responded_at DATETIME,
    commands_preview JSON,            -- 待审批命令列表 (脱敏后)
    impact_scope JSON,                -- {affected_services, affected_namespaces, affected_nodes}
    risk_description TEXT,
    timeout_seconds INT DEFAULT 30,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (requested_by) REFERENCES users(id),
    FOREIGN KEY (responded_by) REFERENCES users(id)
);

-- ========== 知识库 ==========
CREATE TABLE knowledge_cases (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(256) NOT NULL,
    symptoms JSON,                     -- ["CrashLoopBackOff", "OOMKilled"]
    root_cause TEXT,
    solution TEXT,
    severity ENUM('critical', 'warning', 'info'),
    tags JSON,
    service_name VARCHAR(128),
    namespace VARCHAR(128),
    total_attempts INT DEFAULT 1,
    successful_attempt INT,           -- 第几次尝试成功的
    verified BOOLEAN DEFAULT TRUE,
    verified_at DATETIME,
    expires_at DATETIME,              -- 案例有效期
    source_session_id VARCHAR(36),    -- 来源会话
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id),
    INDEX idx_case_service (service_name),
    INDEX idx_case_tags (tags)
);

CREATE TABLE case_attempts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    case_id INT NOT NULL,
    attempt_num INT NOT NULL,         -- 1, 2, 3
    plan_description TEXT,
    commands_executed JSON,
    result ENUM('success', 'failure'),
    failure_reason TEXT,              -- 失败时的分析
    adjusted_strategy TEXT,           -- 失败后如何调整
    FOREIGN KEY (case_id) REFERENCES knowledge_cases(id)
);

CREATE TABLE knowledge_chunks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    case_id INT,
    doc_name VARCHAR(256),
    chunk_index INT,
    content TEXT NOT NULL,
    embedding JSON,                   -- 向量 (或使用 VECTOR 类型)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES knowledge_cases(id)
);

-- ========== 巡检 & 告警 ==========
CREATE TABLE inspection_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    cron_expr VARCHAR(64),           -- */30 * * * *
    target_scope JSON,               -- {namespaces, nodes, services}
    agent_prompt TEXT,                -- 巡检 Agent 的 system prompt
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at DATETIME,
    last_status ENUM('success', 'warning', 'error'),
    next_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inspection_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id INT NOT NULL,
    session_id VARCHAR(36),
    summary TEXT,
    anomalies_found JSON,            -- [{severity, description, suggested_action}]
    full_report TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES inspection_tasks(id)
);

-- ========== 平台可观测性 ==========
CREATE TABLE platform_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    metric_name VARCHAR(64),          -- agent_call_duration, tool_call_duration, token_usage
    labels JSON,                      -- {agent: "remedy", intent: "diagnosis"}
    value DOUBLE,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metric_time (metric_name, recorded_at)
);
```

---

## 6. 前端设计

### 6.1 核心页面：智能运维对话台 ✅ Phase 3 已实现

**Phase 3 新增特性**:
- **修复计划卡** (蓝色 accent, 策略描述 + 命令列表 + L0-L4 风险徽章)
- **审批卡** (红色 2px 边框, 命令列表 + 风险等级 + 批准/拒绝按钮)
- **验证清单** (绿色✓ / 红色✗ / 黄色 pending 图标)
- **重试进度通知** (旋转箭头 + attempt N/3)
- **Agent 管道已扩展**: Orchestrator → Observe → Diagnose → **Remedy** → **Verify** → Final (7 阶段)

**Phase 2 已实现特性**:
- Dark Mode 工业风主题 (Element Plus dark CSS vars + 自定义深层配色)
- Agent 阶段管道指示器 (7 色圆点对应 7 个 Agent)
- 终端风格命令卡片 (Cascadia Code / Fira Code 等宽字体, 青色高亮)
- 异常检测卡片 (红/黄/蓝 severity 左边框 + badge)
- 诊断假设卡片 (琥珀色 accent + 置信度进度条)
- 根因分析面板 (红色 accent)
- RAG 知识引用卡片 (绿色图标)
- 可展开推理链 (DeepSeek reasoning_content, 终端风 cyan 边框)
- Shell 风格输入框 (`$` prompt + 快捷命令)

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔷 AI-Ops Platform                          🔔 3 待审批  👤 张三   │
├────────────┬────────────────────────────────────────────────────────┤
│            │                                                        │
│  历史会话   │              对话区 (SSE 实时流)                       │
│            │                                                        │
│  ┌────────┐│  ┌──────────────────────────────────────────────────┐ │
│  │🔴 OOM  ││  │  🧠 Orchestrator: 正在分析你的意图...              │ │
│  │payment ││  │  ✅ 意图: 故障诊断 | 目标: payment-service        │ │
│  │14:30   ││  │  📊 危险等级: L0 (只读诊断, 无需审批)             │ │
│  └────────┘│  └──────────────────────────────────────────────────┘ │
│  ┌────────┐│                                                        │
│  │部署失败 ││  ┌──────────────────────────────────────────────────┐ │
│  │frontend││  │  👁️ Observe Agent (感知阶段)                      │ │
│  │昨天    ││  │  ├─ Prometheus 查询: CPU/Memory 时序数据 ✅        │ │
│  └────────┘│  │  ├─ kubectl describe pod: OOMKilled, exit 137 ✅   │ │
│            │  │  ├─ kubectl logs: OutOfMemoryError ✅               │ │
│            │  │  └─ 🔴 异常: payment-service 3/3 OOMKilled         │ │
│            │  └──────────────────────────────────────────────────┘ │
│            │                                                        │
│            │  ┌──────────────────────────────────────────────────┐ │
│            │  │  🔬 Diagnose Agent (诊断阶段)                     │ │
│            │  │  ├─ 假设A: 内存泄漏 (置信度 0.85)                   │ │
│            │  │  ├─ 假设B: 配置错误 (置信度 0.30)                   │ │
│            │  │  ├─ RAG 检索: 找到 3 个相似案例                     │ │
│            │  │  └─ 🎯 根因: JVM heap > memory limit (置信度 0.92)│ │
│            │  └──────────────────────────────────────────────────┘ │
│            │                                                        │
│            │  ┌──────────────────────────────────────────────────┐ │
│            │  │  🔧 Remedy Agent (修复阶段)                       │ │
│            │  │                                                    │ │
│            │  │  ┌─ 第1次尝试 ──────────────────────────────┐     │ │
│            │  │  │ 📋 方案: 扩容 memory limit 512Mi→1Gi       │     │ │
│            │  │  │ 🔒 风险: L2 (需确认)                       │     │ │
│            │  │  │                                              │     │ │
│            │  │  │   [批准] [拒绝] [查看详情]  ← 审批卡片      │     │ │
│            │  │  │                                              │     │ │
│            │  │  │   等待审批中... (30s 超时)                   │     │ │
│            │  │  └────────────────────────────────────────┘     │ │
│            │  │                                                    │ │
│            │  │  ┌─ 审批已通过 ✅ ──────────────────────┐        │ │
│            │  │  │ ▶ kubectl patch deploy payment ...     │        │ │
│            │  │  │ ❌ 失败: insufficient memory on nodes   │        │ │
│            │  │  │ 🧠 分析: 节点可用内存仅200Mi             │        │ │
│            │  │  └──────────────────────────────────────┘        │ │
│            │  │                                                    │ │
│            │  │  ┌─ 第2次尝试 (自动调整策略) ────────────┐       │ │
│            │  │  │ 🔄 调整方案: 释放dev资源→扩容payment    │       │ │
│            │  │  │ ▶ kubectl patch deploy dev-env ...      │       │ │
│            │  │  │ ✅ 成功                                 │       │ │
│            │  │  │ ▶ kubectl patch deploy payment ...      │       │ │
│            │  │  │ ✅ 成功                                 │       │ │
│            │  │  └──────────────────────────────────────┘        │ │
│            │  │                                                    │ │
│            │  └──────────────────────────────────────────────────┘ │
│            │                                                        │
│            │  ┌──────────────────────────────────────────────────┐ │
│            │  │  ✅ Verify Agent (验证阶段)                       │ │
│            │  │  ├─ Pod Running: ✅                               │ │
│            │  │  ├─ Health Check 200: ✅                          │ │
│            │  │  ├─ CPU/Memory 正常: ✅                           │ │
│            │  │  └─ 5min 无新告警: ✅                              │ │
│            │  └──────────────────────────────────────────────────┘ │
│            │                                                        │
│            │  ┌──────────────────────────────────────────────────┐ │
│            │  │  📝 操作摘要                                      │ │
│            │  │  payment-service OOM 修复完成，共尝试 2 次。       │ │
│            │  │  ⚠️ 建议: 集群节点资源紧张，建议扩容节点。         │ │
│            │  │  📋 案例已自动保存到知识库 #INC-2026-0042          │ │
│            │  └──────────────────────────────────────────────────┘ │
│            │                                                        │
│            ├────────────────────────────────────────────────────────┤
│            │  💬 输入运维意图...                          [发送]   │
│            │  ⚡快捷: [排查崩溃] [检查集群] [资源分析] [巡检]        │
└────────────┴────────────────────────────────────────────────────────┘
```

### 6.2 前端组件树

✅ = 已实现 | ⬜ = 规划中 | 🆕 = Phase 3 新增

```
src/
├── views/
│   ├── ChatView.vue ✅ 🆕         # 核心对话台 (7 Agent 管道 + Remedy/Verify 阶段指示)
│   ├── LoginView.vue ✅           # Dark 主题登录页
│   ├── DashboardView.vue ⬜       # 集群仪表盘 + 智能体运行状态
│   ├── AuditCenterView.vue ⬜     # 审计中心
│   ├── ApprovalCenterView.vue ⬜  # 审批中心
│   ├── KnowledgeBaseView.vue ⬜   # 知识库管理
│   └── SettingsView.vue ⬜        # 系统设置
│
├── components/
│   ├── chat/
│   │   ├── ChatPanel.vue ✅ 🆕   # 对话主面板 (18 种 SSE 事件渲染, 审批/验证/重试卡片)
│   │   ├── SessionList.vue ⬜     # 历史会话列表
│   │   └── (Remedy/Verify/Approval/Retry 等内联在 ChatPanel 中)
│   │
│   ├── dashboard/ ⬜
│   └── knowledge/ ⬜
│
├── stores/
│   ├── auth.js ✅
│   ├── chat.js ✅ 🆕             # SSE 流式消息管理 (18 种事件 + sendApproval action)
│   └── approval.js ⬜
│
├── api/
│   ├── index.js ✅                # Axios 实例 + JWT 拦截器
│   ├── chat.js ✅                 # SSE EventSource 管理
│   └── auth.js ✅
│
├── router/
│   └── index.js ✅
│
└── App.vue ✅                     # Dark theme 全局样式 + 自定义滚动条
```

---

## 7. 关键场景流程

### 7.1 场景一：故障自愈全流程 (Success + 1次重试)

```
触发: 用户输入 "payment-service 三个 Pod 都在 CrashLoop，帮我看看"

[Phase 1: Observe]  耗时 ~3s
  • Prometheus 查询 payment-service CPU/Memory 最近 15min
  • kubectl get pods -n production | grep payment
  • kubectl describe pod 获取 OOMKilled 事件
  • kubectl logs --tail=200 获取 OutOfMemoryError
  • 异常检测: 3 个 Pod 在 14:32 同时 OOMKilled → severity=critical
  
[Phase 2: Diagnose]  耗时 ~5s
  • 生成假设: 内存泄漏 (0.85), 配置变更引起 (0.30), 流量突增 (0.20)
  • RAG 检索: 找到 2025-03-15 同类案例 "payment-service OOM → 扩容至1Gi"
  • kubectl top pod 确认实际内存使用 580Mi > limit 512Mi
  • 确认根因: "JVM heap 超限 | 置信度 0.92 | 建议扩容至 1Gi"
  
[Phase 3: Remedy - Round 1]  耗时 ~4s
  • 修复方案: patch Deployment memory limit → 1Gi
  • Security Agent 评审: L2 中风险, 需要用户确认
  • 用户点击 [批准]
  • 执行: kubectl patch deploy payment -n production --patch '{"resources":{"limits":{"memory":"1Gi"}}}'
  • 结果: ❌ FAIL — "0/3 nodes available: insufficient memory"
  • Remedy Agent 分析: "3 个节点可用内存总计 200Mi, 扩容 1Gi 放不下"
  
[Phase 4: Remedy - Round 2]  耗时 ~6s
  • 调整策略: "不直接扩容 payment, 先临时降低 dev 环境资源释放空间"
  • 新方案:
    1. kubectl patch deploy dev-env --patch '{"resources":{"limits":{"memory":"256Mi"}}}' → ✅
    2. kubectl patch deploy payment --patch '{"resources":{"limits":{"memory":"1Gi"}}}' → ✅
    3. kubectl patch deploy dev-env --patch '{"resources":{"limits":{"memory":"512Mi"}}}' → ✅
  • 全部成功!
  
[Phase 5: Verify]  耗时 ~3s
  • kubectl get pods payment: 3/3 Running ✅
  • curl health-check: 200 ✅
  • Prometheus 查询: 内存使用 450Mi/1Gi, 稳定 ✅
  • 5 分钟内无新异常 Event ✅
  
[Phase 6: Knowledge]  耗时 ~2s
  • 自动生成案例 INC-2026-0042
  • 标记: Round1 失败原因 "节点资源不足", Round2 成功方案 "释放低优→扩容→恢复"
  • 向量化入库

总耗时: ~23s | 尝试次数: 2 | 人工介入: 1次(审批) | 结果: 成功
```

### 7.2 场景二：3次全部失败 → 升级人工

```
触发: 用户输入 "扩容 payment-service 到 10 副本"

[Round 1] 方案: 直接 scale → ❌ 失败: 节点资源不足
[Round 2] 方案: 添加节点 + scale → ❌ 失败: 节点加入超时
[Round 3] 方案: 使用 cluster-autoscaler 触发扩容 + scale → ❌ 失败: autoscaler 未响应

[最终升级]
  Orchestrator: "3 次尝试均失败, 自动升级给管理员"
  
  升级通知内容:
  ┌─────────────────────────────────────────────┐
  │ 🔴 故障升级: payment-service 扩容失败        │
  │                                              │
  │ 📋 原始需求: 扩容至 10 副本                   │
  │                                              │
  │ ❌ 尝试 1: 直接 scale                        │
  │    失败原因: 节点资源不足                     │
  │                                              │
  │ ❌ 尝试 2: 添加新节点                         │
  │    失败原因: 节点注册超时                     │
  │                                              │
  │ ❌ 尝试 3: 触发 cluster-autoscaler            │
  │    失败原因: autoscaler 服务未响应             │
  │                                              │
  │ 💡 AI 建议:                                  │
  │   1. 检查 cluster-autoscaler 服务状态         │
  │   2. 检查云厂商 API 配额是否耗尽              │
  │   3. 考虑手动添加节点                         │
  │                                              │
  │ 📎 完整上下文已保存, 会话ID: abc-123          │
  │                                              │
  │ [一键接管] [查看详情] [通知运维群]            │
  └─────────────────────────────────────────────┘
```

### 7.3 场景三：自动巡检 + 主动修复

```
触发: Cron 触发巡检任务 (每 30 分钟)

巡检 Agent 执行:
  ✅ 节点健康: 3/3 Ready
  ✅ Pod 健康: 47/49 Running, 2 Pending (frontend, 已 Pending 15 分钟)
  ⚠️ 资源水位: node-3 Memory 89% (阈值 85%)
  ✅ 证书: 全部有效 (>30天)
  ⚠️ Events: 发现 5 条 "FailedScheduling" 事件

巡检结论: 2 个异常需处理
  → 自动触发 Diagnose Agent

Diagnose Agent:
  1. Pending Pod 分析:
     - kubectl describe pod frontend-xxx → "0/3 nodes available: insufficient memory"
     - 根因: node-3 内存水位 89%, 无法调度新 Pod
     
  2. 资源水位分析:
     - node-1: Memory 45%, node-2: Memory 62%, node-3: Memory 89%
     - 根因: 调度不均衡, node-3 负载过高

自动修复 (无需人工触发):
  Remedy Agent: 
    Plan: 将部分 node-3 上的低优 Pod 驱逐到其他节点
  
  Round 1:
    • kubectl drain node-3 --ignore-daemonsets --delete-emptydir-data
    → 部分 Pod 迁移到 node-1, node-2
    → 2 个 Pending frontend 成功调度 ✅
    → node-3 Memory 降至 58%
  
  Verify:
    • 所有 Pod Running ✅
    • node-3 资源恢复正常 ✅
    • frontend 健康检查 200 ✅

巡检报告 (自动生成并推送):
  "14:30 巡检发现 node-3 资源紧张导致 frontend Pending,
   Agent 自动执行节点再平衡, 问题已解决。详情: #INC-2026-0043"
```

---

## 8. 分阶段实施计划

### Phase 1: 基础框架 + 单 Agent 跑通 (Week 1-2) ✅ 已完成
- [x] FastAPI + MySQL + JWT 骨架
- [x] Vue 3 前端骨架 (路由、登录、基本布局)
- [x] LangGraph 基础图 + 单 Agent (Orchestrator + Echo Tool)
- [x] SSE 通道打通，前端可接收流式消息
- [x] kubectl Tool 封装 → Phase 2 升级为通用 kubectl_exec
- [x] Linux/SSH Tool 封装 → Phase 2 升级为通用 linux_exec
- [x] Kubernetes 集群 SSH 连接配置 (paramiko)

### Phase 2: 多智能体 + 诊断链路 (Week 3-4) ✅ 已完成
- [x] 完整的智能体注册: Orchestrator (router + final), Observe, Diagnose, Knowledge
- [x] Observe Agent: kubectl_exec + linux_exec 双工具，两轮 LLM 调用采集+分析
- [x] Diagnose Agent: 假设生成 + 根因确认 + RAG 检索历史案例
- [x] Knowledge Agent: RAG 检索 (Chroma 0.5.23 + Ollama qwen3-embedding:0.6b)
- [x] 智能体间通信 (LangGraph State 传递 + 条件路由)
- [x] 对话面板: Agent 阶段管道 + 推理链展开 + 异常卡片 + 假设气泡 + 根因面板 + RAG 引用
- [x] DeepSeek v4-pro 推理模型兼容 (reasoning_content 提取 + SSE 推送)
- [x] 通用工具架构: kubectl_exec + linux_exec，覆盖全部 K8s + Linux 只读运维
- [x] 安全白名单验证: 20 条安全测试通过 (9 允许, 11 拒绝)
- [x] Element Plus Dark Mode 主题
- [x] 预置知识库: 10+ 条 K8s 常见故障知识种子数据
- [x] 路由优化: 所有意图先经 Observe 采集 live data（包括 inquiry）

### Phase 3: 自愈循环 + 审批 (Week 5-6)✅ 已完成
- [x] Remedy Agent: 修复方案生成 + 执行 + 结果分析
- [x] **自愈循环核心**: 失败分析 + 策略调整 + 自动重试 (≤3)
- [x] Verify Agent: 修复后验证
- [x] Security Agent: 风险等级评估 + 命令安全校验
- [x] 审批工作流: L2 确认 / L3-L4 审批 / 超时机制
- [x] 前端: 重试时间线 + 审批卡片 + 验证清单
- [x] 风险分级器 (risk_classifier.py): L0-L4 确定性分级 + 86 个单元测试
- [x] HITL 中断/恢复: LangGraph `interrupt()` + SSE 事件 + `Command(resume=...)` + 双暂停图管理
- [x] SSE 事件扩展: 8 个新事件类型 (remedy_plan, approval_required, graph_paused, approval_result, remedy_executing, remedy_result, verification_status, retry_attempt)
- [x] RBAC 双层防护: HITL 审批门控决策 + RBAC 工具级执行鉴权
- [x] 端到端测试: viewer 审批流 + admin 自动 L2 + RBAC 拦截验证 + 拒绝重试循环

### Phase 4: 企业特性 (Week 7-8) ✅ 已完成
- [x] 知识库完整功能: 案例自动生成 + 手动上传 + 向量检索
- [x] 仪表盘: 集群健康 + Agent 运行状态
- [x] 巡检系统: Cron 触发 + 自动修复
- [x] 审计中心: 查询 + 详情 + SSE 会话回放
- [x] Agent 决策路径可视化 (DAG 图)
- [x] 告警集成: 企业微信/钉钉通知
- [x] 中英双语面板切换
- [x] 巡检调度器 API + 前端管理界面
- [x] 审计 SSE 时序回放 (播放/暂停/速度控制)

### Phase 5: 生产加固 (Week 9-10) ✅ 已完成
- [x] 性能优化 (LLM 并发调用、命令执行超时控制、连接池)
- [x] 安全加固 (敏感信息脱敏、命令长度限制、SSH 异常捕获)
- [x] 熔断器 + 优雅关闭 + 错误处理降级
- [x] 部署文档 + 运维手册 (DEPLOY.md)
- [x] Dockerfile + docker-compose + Helm Chart (7 个模板)

### Phase 6: 高级智能特性 (Week 11-12) ✅ 已完成
- [x] 记忆巩固 Agent — 会话结束后 LLM 提取症状/根因/修复链生成结构化案例入库
- [x] 用户管理界面 — CRUD + 角色分配 (viewer/operator/admin/superadmin)
- [x] Prometheus 集成 — prometheus_query 工具 + Observe Agent 实时指标
- [x] Web Terminal — xterm.js 交互式命令行，WebSocket + RBAC 权限
- [x] 知识图谱 — 服务依赖拓扑 + 爆炸半径分析 API + 前端可视化
- [x] 3 个新前端页面 (UsersView / TopologyView / TerminalView)

---

## 9. 非功能性需求

| 维度 | 指标 |
|------|------|
| 故障诊断耗时 | 简单故障 < 30s, 复杂故障 < 120s (含重试) |
| 自愈成功率 | > 70% 故障在 3 次内自动修复 |
| SSE 首字延迟 | < 1.5s |
| 并发会话 | 50 个同时进行中的诊断会话 |
| 审计完整性 | 100% 操作可追溯到具体命令和人员 |
| LLM Token 效率 | 每次诊断平均 < 20K tokens (含重试) |
| 安全 | 命令注入 0 容忍，敏感信息 100% 脱敏 |
| 可用性 | 平台自身 99.5% (非核心链路) |

---

## 10. 核心设计原则

### 10.1 AIOps 三大铁律
1. **可观测先于可执行**: 先充分采集数据，再执行操作。绝不盲操。
2. **影响可控**: 所有变更操作评估影响范围，危险操作必须审批。
3. **失败可回退**: 每次变更记录前置状态，失败时优先回退而非继续硬来。

### 10.2 自愈循环设计原则
1. **每次重试策略必须不同**: 不能简单地重试同样的命令
2. **每次失败必须深度分析**: 不仅是 "失败了"，还要分析 "为什么失败"
3. **第 3 次失败必须升级**: 不自作聪明地无限循环
4. **升级时携带完整上下文**: 让接管的人不用重新排查

### 10.3 智能体协作原则
1. **单一职责**: 每个 Agent 只做一件事，做好一件事
2. **通过 State 通信**: Agent 之间不直接调用，通过共享 State 传递信息
3. **可独立测试**: 每个 Agent 可以独立测试和调试
4. **可替换**: 每个 Agent 可以被更强的版本替换，不影响整体架构

---

## 附录 A：项目结构总览 (v2.0)

```
AI-ops-k8s/
├── backend/                          # Python FastAPI 后端
│   ├── main.py                       # 应用入口 + 路由注册 + 生命周期
│   ├── config.py                     # 全局配置 (Settings)
│   ├── database.py                   # 异步数据库引擎 + 会话工厂
│   ├── requirements.txt              # Python 依赖
│   │
│   ├── agents/                       # 7 Agent 多智能体系统
│   │   ├── state.py                  # AIOpsState 状态定义 (TypedDict)
│   │   ├── graph.py                  # LangGraph 状态图 + 条件路由
│   │   ├── orchestrator.py           # 编排主控 (意图分类 + 结果汇总)
│   │   ├── observe.py                # 感知 Agent (数据采集 + 异常检测)
│   │   ├── diagnose.py               # 诊断 Agent (假设 + 根因分析)
│   │   ├── knowledge.py              # 知识 Agent (RAG 检索)
│   │   ├── remedy.py                 # 修复 Agent (修复计划 + HITL 审批)
│   │   ├── verify.py                 # 验证 Agent (验证 + 重试决策)
│   │   ├── consolidation.py          # 记忆巩固 Agent (会话→案例)
│   │   ├── chroma_store.py           # ChromaDB 向量存储 + Embedding
│   │   └── tools/
│   │       ├── ops_tools.py          # kubectl_exec + linux_exec + prometheus_query
│   │       ├── risk_classifier.py    # L0-L4 风险分级器 + 自动审批
│   │       ├── knowledge.py          # search_knowledge_base 工具
│   │       └── echo.py               # echo 调试工具
│   │
│   ├── api/                          # REST API 路由 (15 个模块)
│   │   ├── auth.py                   # 登录 / 注册 / 修改密码
│   │   ├── chat.py                   # SSE 流式聊天 + 审批恢复
│   │   ├── audit.py                  # 审计中心 (会话查询/详情/统计)
│   │   ├── dashboard.py              # 仪表盘 (概览/集群/Agent 状态)
│   │   ├── inspection.py             # 巡检管理 (任务 CRUD + 手动触发)
│   │   ├── knowledge.py              # 知识库 (上传/搜索/列表/删除/自动生成)
│   │   ├── machines.py               # 机器管理 (CRUD + SSH 检测)
│   │   ├── notification.py           # 钉钉通知 (测试/配置)
│   │   ├── terminal.py               # WebSocket 终端
│   │   ├── topology.py               # 服务拓扑 (图 + 爆炸半径)
│   │   └── users.py                  # 用户管理 (CRUD + 角色分配)
│   │
│   ├── models/                       # SQLAlchemy 数据模型
│   │   ├── user.py                   # 用户 (4 角色 RBAC)
│   │   ├── session.py                # 会话 + 消息
│   │   └── machine.py                # SSH 目标机器
│   │
│   ├── schemas/                      # Pydantic 请求/响应模型
│   │   ├── auth.py                   # LoginRequest / TokenResponse / ChangePasswordRequest
│   │   ├── chat.py                   # ChatRequest / ResumeRequest
│   │   ├── knowledge.py              # KnowledgeUpload / Search / AutoGenerate
│   │   ├── machine.py                # MachineCreate / MachineUpdate
│   │   └── notification.py           # TestNotification / ConfigUpdate
│   │
│   ├── services/                     # 业务服务层
│   │   ├── audit.py                  # 审计持久化 (会话/消息 CRUD)
│   │   ├── chat_service.py           # SSE 流式生成器 + 审计同步 + HITL 管理
│   │   ├── circuit_breaker.py        # 熔断器 (滑动窗口)
│   │   ├── knowledge_graph.py        # 服务拓扑图
│   │   ├── notification.py           # 钉钉通知服务 (HMAC 签名)
│   │   ├── scheduler.py              # 巡检调度器 (5 个定时任务)
│   │   └── security.py               # 敏感数据脱敏
│   │
│   └── core/
│       ├── security.py               # JWT + bcrypt
│       └── deps.py                   # FastAPI 依赖注入 (认证)
│
├── frontend/                         # Vue 3 前端 (Dark Mode)
│   ├── src/
│   │   ├── main.js                   # 入口 (Pinia + Vue Router + i18n)
│   │   ├── App.vue
│   │   ├── api/index.js              # Axios 实例 (JWT 拦截器)
│   │   ├── router/index.js           # 路由 (11 个页面 + 认证守卫)
│   │   ├── stores/
│   │   │   ├── auth.js               # 认证 Store (token/user)
│   │   │   └── chat.js               # 聊天 Store (SSE 流 + 多 Agent 事件)
│   │   ├── i18n/
│   │   │   ├── index.js              # vue-i18n 初始化
│   │   │   ├── zh-CN.js              # 中文翻译 (~180 键)
│   │   │   └── en-US.js              # 英文翻译 (~180 键)
│   │   ├── components/
│   │   │   ├── chat/ChatPanel.vue    # 聊天面板 (Agent 流水线 + 多类型卡片)
│   │   │   ├── DagViewer.vue         # SVG Agent 决策路径图
│   │   │   ├── LangSwitcher.vue      # 中英切换按钮
│   │   │   ├── MachineSelector.vue   # 多机器选择器
│   │   │   ├── MarkdownRenderer.vue  # Markdown 渲染器
│   │   │   ├── NotificationBell.vue  # 通知铃铛 + 下拉列表
│   │   │   └── SessionHistory.vue    # 会话历史列表
│   │   └── views/
│   │       ├── ChatView.vue          # 对话页 (侧边栏 + 输入 + 停止按钮)
│   │       ├── LoginView.vue         # 登录页
│   │       ├── DashboardView.vue     # 仪表盘 (30s 自动刷新)
│   │       ├── AuditView.vue         # 审计中心 (DAG + SSE 回放 + CSV 导出)
│   │       ├── KnowledgeView.vue     # 知识库 (搜索/上传/自动生成)
│   │       ├── InspectionView.vue    # 巡检管理 (任务开关 + 手动触发)
│   │       ├── UsersView.vue         # 用户管理 (CRUD + 角色分配)
│   │       ├── TopologyView.vue      # 服务拓扑 (SVG 图 + 爆炸半径)
│   │       ├── TerminalView.vue      # Web 终端 (xterm.js + WebSocket)
│   │       ├── MachinesView.vue      # 机器管理 (SSH 检测 + 默认设置)
│   │       └── ProfileView.vue       # 个人中心 (查看信息 + 改密码)
│
├── helm/aiops/                       # Kubernetes Helm Chart
│   ├── Chart.yaml
│   ├── values.yaml                   # 完整可配置参数
│   └── templates/                    # 6 个 K8s 资源模板
│
├── Dockerfile.backend                # Python 后端镜像
├── Dockerfile.frontend               # 多阶段前端镜像 (Node + Nginx)
├── docker-compose.yml                # 本地一键部署 (5 服务)
├── nginx.conf                        # 前端 Nginx 配置
├── DEPLOY.md                         # 部署运维手册
├── .dockerignore
└── PRD-AIOps平台.md                  # 产品需求文档
```
