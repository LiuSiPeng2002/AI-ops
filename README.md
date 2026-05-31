# AI-Ops Platform v2.0

**多智能体自愈运维平台** — 7 Agent 协作实现感知→分析→决策→执行→验证→自愈闭环

[English](#english) | [中文](#中文)

---

## English

### Overview

AI-Ops is an enterprise Kubernetes operations platform powered by a **multi-agent AI system**. 7 specialized agents collaborate to diagnose issues, execute repairs, verify results, and auto-retry up to 3 attempts — all with human-in-the-loop approval for risky operations.

### Key Features

| Feature | Description |
|---------|-------------|
| **7-Agent Pipeline** | Orchestrator → Observe → Diagnose → Knowledge → Remedy → Verify → Consolidation |
| **Self-Healing Loop** | Auto-diagnose → Auto-repair → Auto-verify → Retry ≤3 rounds with adjusted strategies |
| **Human-in-the-Loop** | L2+ risk operations pause for user approval via LangGraph `interrupt()` |
| **RBAC Security** | 4 roles (viewer/operator/admin/superadmin) × L0-L4 risk classifier |
| **DingTalk Alerts** | Anomaly + remedy + verify notifications via webhook |
| **Scheduled Inspections** | 5 periodic checks (pod/node/disk/memory/service) with auto-remediation |
| **Bilingual UI** | Chinese/English toggle with 180+ translation keys |
| **Markdown Rendering** | LLM responses rendered with syntax highlighting, tables, and code blocks |
| **DAG Visualization** | SVG agent decision path graph with node status indicators |
| **SSE Replay** | Play/pause/speed-controlled audit session replay |
| **Web Terminal** | xterm.js interactive shell via WebSocket with RBAC |
| **Multi-Machine** | Manage multiple SSH targets with connectivity checks |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Orchestration | LangGraph (StateGraph + MemorySaver) |
| AI Framework | LangChain (Tools + RAG + Prompt Management) |
| LLM | DeepSeek v4-pro (reasoning model) |
| Backend | FastAPI (Python 3.11+) + SSE Streaming |
| Frontend | Vue 3 + Pinia + Element Plus + xterm.js |
| Database | MySQL 8.0 (async) + ChromaDB (vector) |
| Embedding | Ollama + qwen3-embedding:0.6b |
| Auth | JWT (access + refresh) with bcrypt |
| Deployment | Docker + docker-compose + Helm Chart |

### Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd AI-ops-k8s

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit .env with your LLM API key and MySQL credentials

# 3. Start with docker-compose
docker-compose up -d --build

# 4. Pull embedding model
docker exec aiops-ollama ollama pull qwen3-embedding:0.6b

# 5. Access
# Frontend: http://localhost
# Backend API: http://localhost:8000/docs
```

### Project Structure

```
AI-ops-k8s/
├── backend/agents/        7 AI Agents (LangGraph nodes)
├── backend/api/           15 REST API modules (31 endpoints)
├── backend/models/        3 SQLAlchemy models (user, session, machine)
├── backend/services/      7 business services (audit, scheduler, security...)
├── frontend/src/          Vue 3 SPA (11 pages, 21 components)
├── helm/aiops/            Kubernetes Helm Chart
├── docker-compose.yml     Local deployment (5 services)
└── DEPLOY.md              Full deployment guide
```

### Default Accounts

| Username | Password | Role |
|----------|----------|------|
| `superadmin` | `admin123` | superadmin |
| `admin` | `admin123` | admin |
| `viewer` | — | viewer |

### Documentation

- [PRD (Chinese)](./PRD-AIOps平台.md) — Product requirements & architecture
- [Deployment Guide](./DEPLOY.md) — Docker + K8s deployment
- [Operations Manual (Chinese)](./操作手册.md) — Runbook & troubleshooting

---

## 中文

### 概述

AI-Ops 是一个基于**多智能体 AI 系统**的企业级 Kubernetes 运维平台。7 个专业 Agent 协作完成故障诊断、自动修复、效果验证，最多 3 轮自动重试，高风险操作需人工审批。

### 核心功能

| 功能 | 说明 |
|------|------|
| **7 Agent 流水线** | 编排→感知→诊断→知识→修复→验证→记忆巩固 |
| **自愈闭环** | 自动诊断→自动修复→自动验证→失败自动调整策略重试 ≤3 轮 |
| **人工审批 (HITL)** | L2+ 风险操作暂停等待用户批准/拒绝 |
| **RBAC 权限** | viewer/operator/admin/superadmin × L0-L4 风险分级 |
| **钉钉告警** | 异常/修复/验证失败即时推送 |
| **定时巡检** | 5 个巡检任务 (Pod/节点/磁盘/内存/服务) + 自动修复 |
| **中英双语** | 一键切换，180+ 翻译键覆盖全界面 |
| **Markdown 渲染** | LLM 回答支持表格/代码高亮/列表 |
| **DAG 可视化** | SVG 流程图展示 Agent 决策路径 + 状态指示灯 |
| **SSE 回放** | 审计会话支持播放/暂停/调速 |
| **Web 终端** | xterm.js 命令行，WebSocket + RBAC |
| **多机器管理** | 管理多台 SSH 目标，在线检测，一键切换 |

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `superadmin` | `admin123` | 超级管理员 |
| `admin` | `admin123` | 管理员 |
| `viewer` | — | 只读用户 |

### 文档索引

- [PRD 产品需求文档](./PRD-AIOps平台.md)
- [部署运维手册](./DEPLOY.md)
- [操作手册](./操作手册.md)
