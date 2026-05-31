"""Seed the Chroma knowledge base with common K8s troubleshooting documents."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.chroma_store import add_document, get_collection

DOCUMENTS = [
    {
        "id": "oom-1",
        "title": "Pod OOMKilled 故障排查",
        "content": """
Pod 出现 OOMKilled 状态的可能原因和排查步骤：

1. 内存限制不足：检查 Pod 的 resources.limits.memory 是否设置过低。
   使用 kubectl top pod 查看实际内存使用，对比 limits 值。
   如果实际使用接近或超过 limit，需要扩容。

2. 内存泄漏：应用代码存在内存泄漏，内存持续增长直至超限。
   使用 kubectl logs 检查是否有 OutOfMemoryError。
   Java 应用检查 -Xmx 参数，Node.js 检查 --max-old-space-size。

3. 流量突增：突发流量导致内存使用飙升。
   检查 HPA 配置，考虑启用自动伸缩。
   短期方案：增大 memory limit；长期方案：优化代码或启用 HPA。

4. 常见修复步骤：
   - 临时扩容: kubectl patch deploy <name> -p '{"spec":{"template":{"spec":{"containers":[{"name":"<name>","resources":{"limits":{"memory":"1Gi"}}}]}}}}'
   - 检查节点资源: kubectl describe node <node> 确认节点有足够可分配内存
   - 如果节点资源不足，考虑节点扩容或 Pod 迁移
""",
    },
    {
        "id": "crashloop-1",
        "title": "Pod CrashLoopBackOff 排查指南",
        "content": """
Pod CrashLoopBackOff 表示 Pod 反复启动后崩溃。排查步骤：

1. 查看 Pod 事件：kubectl describe pod <name> 查看 Events 部分。
   重点关注 Exit Code:
   - exit code 0: 正常退出（可能是完成型 Job）
   - exit code 1: 应用错误
   - exit code 137: 被 SIGKILL 杀死（通常是 OOM）
   - exit code 139: 段错误（SIGSEGV）

2. 查看容器日志：kubectl logs <pod> --previous 查看上一次崩溃的日志。
   这是最重要的排查手段。

3. 常见原因：
   - 配置错误：环境变量、ConfigMap、Secret 配置不正确
   - 依赖不可达：数据库、缓存、下游服务连接失败
   - 资源不足：OOMKilled 导致重启
   - 健康检查失败：readiness/liveness probe 配置不当
   - 镜像问题：镜像不存在或拉取失败

4. 修复建议：
   - 如果是 OOM：增加 memory limit
   - 如果健康检查失败：调整 probe 的 initialDelaySeconds 和 failureThreshold
   - 如果依赖问题：检查 Service 和 NetworkPolicy 配置
""",
    },
    {
        "id": "imagepull-1",
        "title": "ImagePullBackOff 和 ErrImagePull 故障处理",
        "content": """
ImagePullBackOff 表示 Kubernetes 无法拉取容器镜像。

1. 检查镜像名称和标签是否正确：
   kubectl describe pod <name> | grep -A5 Events

2. 常见原因：
   - 镜像不存在或标签错误
   - 私有镜像仓库认证失败 (imagePullSecrets 未配置)
   - 网络问题导致无法访问镜像仓库
   - 仓库速率限制（Docker Hub 匿名用户 100 pulls/6h）

3. 修复步骤：
   - 验证镜像: docker pull <image> 在本地测试
   - 配置 Secret: kubectl create secret docker-registry regcred --docker-server=<registry> --docker-username=<user> --docker-password=<pass>
   - 在 Deployment 中引用: imagePullSecrets: [{name: regcred}]
   - 检查节点网络: 节点是否能访问镜像仓库
""",
    },
    {
        "id": "pending-1",
        "title": "Pod 长时间 Pending 问题排查",
        "content": """
Pod 一直处于 Pending 状态的排查：

1. 查看原因：kubectl describe pod <name> 查看 Events
   常见提示：
   - "0/N nodes are available: insufficient cpu/memory" → 资源不足
   - "pod has unbound immediate PersistentVolumeClaims" → PVC 未绑定
   - "node(s) had taint" → 节点有污点，Pod 无对应 toleration

2. 资源不足：
   - 检查节点资源: kubectl top nodes
   - 调整 Pod requests: 降低 requests 值
   - 扩容节点: 增加集群节点数
   - 驱逐低优 Pod: kubectl drain <node> --ignore-daemonsets

3. PVC 未绑定：
   - 检查 PVC 状态: kubectl get pvc
   - 检查 StorageClass: kubectl get sc
   - 检查 PV 是否可用: kubectl get pv

4. 节点选择器/亲和性不匹配：
   - 检查 nodeSelector: kubectl describe pod <name> | grep Node-Selectors
   - 检查节点标签: kubectl get nodes --show-labels
   - 检查污点和容忍: kubectl describe node <node> | grep Taints
""",
    },
    {
        "id": "network-1",
        "title": "K8s 服务网络故障排查",
        "content": """
Service 无法访问或连接超时：

1. 检查 Service 和 Endpoints：
   kubectl get svc <name> -o wide
   kubectl get endpoints <name>
   如果 Endpoints 为空，说明 selector 不匹配任何 Pod。

2. 检查 Pod 标签：
   kubectl get pods --show-labels | grep <app>
   确保 Service selector 与 Pod label 匹配。

3. DNS 解析检查：
   kubectl run -it --rm debug --image=busybox -- nslookup <service-name>
   验证集群 DNS 是否正常工作。

4. NetworkPolicy 检查：
   kubectl get networkpolicies
   确认没有策略阻止流量。

5. kube-proxy 检查：
   kubectl get pods -n kube-system | grep kube-proxy
   确保 kube-proxy 在所有节点正常运行。
""",
    },
    {
        "id": "disk-1",
        "title": "节点磁盘压力与驱逐策略",
        "content": """
节点出现 DiskPressure 状态：

1. 检查节点状态：
   kubectl describe node <name> | grep -A5 Conditions
   如果 DiskPressure 为 True，节点将开始驱逐 Pod。

2. 清理磁盘空间：
   - 清理未使用的镜像: docker image prune -a (节点上执行)
   - 清理已退出的容器: docker container prune
   - 清理旧日志: journalctl --vacuum-size=500M
   - 检查大文件: du -sh /* 2>/dev/null | sort -rh | head -10

3. 调整驱逐阈值：
   Kubelet 参数 --eviction-hard 控制清理阈值
   默认: memory.available<100Mi, nodefs.available<10%, imagefs.available<15%

4. 预防措施：
   - 设置 Pod 的 emptyDir sizeLimit
   - 配置日志轮转
   - 监控磁盘使用趋势
""",
    },
    {
        "id": "deploy-fail-1",
        "title": "Deployment 滚动更新失败",
        "content": """
Deployment 更新后 Pod 无法启动或不健康：

1. 查看 Deployment 状态：
   kubectl rollout status deploy/<name>
   kubectl describe deploy <name>

2. 回滚到上一个版本：
   kubectl rollout undo deploy/<name>
   kubectl rollout history deploy/<name> 查看历史版本

3. 常见原因：
   - 新镜像有问题（启动失败、健康检查失败）
   - 资源不足导致新 Pod 无法调度
   - ConfigMap/Secret 变更后格式错误
   - 就绪探针配置过严导致 Pod 一直 NotReady

4. 安全部署策略：
   - 使用 maxSurge 和 maxUnavailable 控制更新速度
   - 配置 minReadySeconds 给新 Pod 预热时间
   - 使用 readiness probe 确保流量切换前服务已就绪
""",
    },
    {
        "id": "cert-1",
        "title": "K8s 证书过期检查与更新",
        "content": """
Kubernetes 集群证书管理：

1. 检查证书有效期：
   kubeadm certs check-expiration
   openssl x509 -in /etc/kubernetes/pki/apiserver.crt -noout -dates

2. 证书过期影响：
   - API server 证书过期 → kubectl 无法连接
   - etcd 证书过期 → 集群数据不可访问
   - kubelet 证书过期 → 节点 NotReady

3. 更新证书：
   kubeadm certs renew all
   systemctl restart kubelet

4. 预防：
   - 设置证书监控告警（过期前 30 天）
   - 自动化证书轮换 (kubeadm 支持自动 renew)
""",
    },
    {
        "id": "etcd-1",
        "title": "etcd 故障与备份恢复",
        "content": """
etcd 是 K8s 集群的核心存储，故障影响整个集群。

1. etcd 健康检查：
   etcdctl endpoint health
   etcdctl endpoint status --write-out=table

2. 定期备份：
   etcdctl snapshot save /backup/etcd-$(date +%Y%m%d).db

3. 恢复步骤：
   etcdctl snapshot restore /backup/etcd-xxx.db --data-dir=/var/lib/etcd-restore
   然后更新 etcd manifest 中的 data-dir 指向恢复目录

4. etcd 性能问题：
   - 检查磁盘 IO (etcd 对磁盘延迟敏感)
   - 检查 etcd 日志: journalctl -u etcd
   - 碎片整理: etcdctl defrag
""",
    },
    {
        "id": "resources-1",
        "title": "K8s 资源配额与限制最佳实践",
        "content": """
Kubernetes 资源管理最佳实践：

1. 始终设置 requests 和 limits：
   - requests: 调度器用来决定 Pod 放在哪个节点
   - limits: kubelet 用来限制容器资源使用
   - 建议 requests = limits 对于生产环境（Guaranteed QoS）

2. 使用 ResourceQuota 限制命名空间：
   apiVersion: v1
   kind: ResourceQuota
   spec:
     hard:
       requests.cpu: "10"
       requests.memory: 20Gi
       limits.cpu: "20"
       limits.memory: 40Gi

3. 使用 LimitRange 设置默认值：
   防止 Pod 没有设置 resources 导致无限使用。

4. QoS 等级：
   - Guaranteed: requests = limits (每个容器)
   - Burstable: requests < limits
   - BestEffort: 未设置 requests/limits (最先被驱逐)

5. HPA 自动伸缩：
   - 基于 CPU/Memory 的 HPA
   - 基于自定义指标的 HPA (Prometheus adapter)
""",
    },
]


def main():
    collection = get_collection()
    print(f"Seeding {len(DOCUMENTS)} documents into collection '{collection.name}'...")

    for doc in DOCUMENTS:
        add_document(
            doc_id=doc["id"],
            title=doc["title"],
            content=doc["content"],
            metadata={"source": "seed", "tags": "k8s,troubleshooting"},
        )
        print(f"  [OK] {doc['title']}")

    print(f"\nDone. Knowledge base ready at: {os.path.abspath('chroma_data')}")


if __name__ == "__main__":
    main()
