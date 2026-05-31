# AI-Ops Platform — 部署运维手册 v2.0

## 1. 架构概览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│    MySQL     │
│  (Nginx:80)  │     │ (FastAPI:8000)│     │   (3306)     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
            ┌──────────┐     ┌──────────────┐
            │  Ollama  │     │  K8s Cluster  │
            │ (11434)  │     │  (SSH:22)     │
            └──────────┘     └──────────────┘
```

## 2. 快速部署 (docker-compose)

### 前置条件
- Docker 24+ & Docker Compose v2+
- 8GB+ RAM (Ollama 需要至少 4GB)
- 20GB+ 磁盘空间

### 2.1 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，至少配置:
#   OPENAI_API_KEY=sk-your-deepseek-key
#   OPENAI_BASE_URL=https://api.deepseek.com/v1
#   JWT_SECRET_KEY=<随机生成>
```

### 2.2 一键启动

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

### 2.3 初始化

```bash
# 拉取 embedding 模型
docker exec aiops-ollama ollama pull qwen3-embedding:0.6b

# 验证服务健康
curl http://localhost:8000/api/health
curl http://localhost
```

### 2.4 访问

| 服务 | URL | 说明 |
|------|-----|------|
| 前端界面 | http://localhost | AI-Ops 对话台 |
| 后端 API | http://localhost:8000 | FastAPI Swagger: /docs |
| MySQL | localhost:3306 | root/aiops_root_2026 |
| Ollama | http://localhost:11434 | 本地 LLM + Embedding |

## 3. Kubernetes 部署 (Helm)

### 前置条件
- Kubernetes 1.26+
- Helm 3.12+
- StorageClass (用于 PVC)
- nginx-ingress-controller (可选)

### 3.1 构建镜像

```bash
# 构建后端镜像
docker build -f Dockerfile.backend -t aiops-backend:2.0 .

# 构建前端镜像
docker build -f Dockerfile.frontend -t aiops-frontend:2.0 .

# 推送到镜像仓库
docker tag aiops-backend:2.0 your-registry/aiops-backend:2.0
docker tag aiops-frontend:2.0 your-registry/aiops-frontend:2.0
docker push your-registry/aiops-backend:2.0
docker push your-registry/aiops-frontend:2.0
```

### 3.2 配置 values

```bash
# 创建自定义配置
cat > my-values.yaml << EOF
backend:
  image:
    repository: your-registry/aiops-backend
    tag: "2.0"
  env:
    OPENAI_API_KEY: "sk-your-key"
    JWT_SECRET_KEY: "$(openssl rand -hex 32)"

frontend:
  image:
    repository: your-registry/aiops-frontend
    tag: "2.0"

ingress:
  enabled: true
  host: aiops.your-domain.com
EOF
```

### 3.3 安装

```bash
# 安装
helm upgrade --install aiops ./helm/aiops \
  -f my-values.yaml \
  --namespace aiops --create-namespace

# 验证
kubectl -n aiops get pods
kubectl -n aiops get svc
```

### 3.4 卸载

```bash
helm uninstall aiops -n aiops
kubectl delete pvc -n aiops -l app.kubernetes.io/name=aiops
```

## 4. 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `mysql+aiomysql://...` | MySQL 连接串 |
| `OPENAI_API_KEY` | - | LLM API Key (必填) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM API 地址 |
| `MODEL_NAME` | `gpt-4o` | LLM 模型名 |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | Embedding 服务地址 |
| `EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | Embedding 模型名 |
| `JWT_SECRET_KEY` | - | JWT 签名密钥 (生产必改) |
| `K8S_MASTER_HOST` | - | K8s 管理节点 IP |
| `K8S_MASTER_USER` | root | SSH 用户名 |
| `K8S_MASTER_PASSWORD` | - | SSH 密码 |
| `DINGTALK_ENABLED` | false | 钉钉通知开关 |
| `DINGTALK_WEBHOOK_URL` | - | 钉钉机器人 Webhook |
| `DB_POOL_SIZE` | 10 | 数据库连接池大小 |
| `LLM_REQUEST_TIMEOUT` | 120 | LLM 请求超时 (秒) |
| `TOOL_EXEC_TIMEOUT` | 45 | 工具执行超时 (秒) |
| `CIRCUIT_BREAKER_FAILURES` | 5 | 熔断器失败阈值 |
| `MAX_COMMAND_LENGTH` | 2000 | 命令最大长度 |

## 5. 运维操作

### 5.1 备份数据库

```bash
docker exec aiops-mysql mysqldump -u root -p$MYSQL_ROOT_PASSWORD aiops > aiops_backup_$(date +%Y%m%d).sql
```

### 5.2 查看巡检结果

```bash
# API 查询
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/inspection/results

# 手动触发巡检
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/inspection/run/pod-health
```

### 5.3 日志查看

```bash
# 后端实时日志
docker-compose logs -f backend

# 特定 Agent 日志
docker-compose logs backend | grep -E "(remedy|observe|diagnose)"
```

### 5.4 健康检查

```bash
# 全栈健康检查
curl http://localhost:8000/api/health
curl http://localhost:8000/api/dashboard/overview
```

## 6. 故障排查

### 问题：LLM 调用超时
```
检查: OPENAI_API_KEY 是否正确
检查: 网络是否能访问 OPENAI_BASE_URL
调整: LLM_REQUEST_TIMEOUT 环境变量
```

### 问题：数据库连接失败
```
检查: MySQL 容器是否运行 (docker-compose ps mysql)
检查: DATABASE_URL 用户名/密码是否正确
检查: 数据库是否已初始化 (aiops 库是否存在)
```

### 问题：Embedding 不可用
```
检查: Ollama 容器是否运行 (docker-compose ps ollama)
拉取模型: docker exec aiops-ollama ollama pull qwen3-embedding:0.6b
检查: curl http://localhost:11434/api/tags
```

### 问题：自愈循环不工作
```
检查: K8S_MASTER_HOST / USER / PASSWORD 配置
检查: SSH 能否连接到 K8s 管理节点
检查: 用户角色是否有足够权限 (admin+ required)
```

## 7. 安全建议

1. **生产环境必改**: JWT_SECRET_KEY, MYSQL_PASSWORD, OPENAI_API_KEY
2. **网络隔离**: 生产环境将 MySQL/Ollama 放在内网，不暴露端口
3. **HTTPS**: 使用 Ingress + cert-manager 自动签发 TLS 证书
4. **审计**: 生产环境不要禁用审计日志 (默认启用)
5. **RBAC**: 为不同用户配置合适角色 (viewer/operator/admin/superadmin)
6. **巡检告警**: 配置 DINGTALK_WEBHOOK_URL 接收异常通知
