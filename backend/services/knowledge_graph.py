"""Knowledge Graph — service dependency topology and blast radius analysis.

Builds a graph from observed service relationships, session data,
and K8s service/endpoint information. Stores in MySQL for persistence,
with in-memory cache for fast queries.
"""

from collections import defaultdict
from typing import Any


class ServiceTopology:
    """In-memory directed graph of service dependencies."""

    def __init__(self):
        # adjacency: service -> set of upstream dependents
        self._dependents: dict[str, set[str]] = defaultdict(set)
        # adjacency: service -> set of downstream dependencies
        self._depends_on: dict[str, set[str]] = defaultdict(set)
        # metadata per service
        self._metadata: dict[str, dict] = {}

    def add_dependency(self, service: str, depends_on: str) -> None:
        """Record that `service` depends on `depends_on`."""
        self._depends_on[service].add(depends_on)
        self._dependents[depends_on].add(service)

    def remove_service(self, service: str) -> None:
        """Remove a service from the topology."""
        for dep in self._depends_on.pop(service, set()):
            self._dependents[dep].discard(service)
        for dep in self._dependents.pop(service, set()):
            self._depends_on[dep].discard(service)
        self._metadata.pop(service, None)

    def get_dependents(self, service: str) -> set[str]:
        """Return all services that depend on this service."""
        return self._dependents.get(service, set())

    def get_dependencies(self, service: str) -> set[str]:
        """Return all services this service depends on."""
        return self._depends_on.get(service, set())

    def blast_radius(self, service: str, depth: int = 3) -> dict:
        """Calculate blast radius if `service` goes down.

        Returns {services: [...], depth: int, total_affected: int}
        """
        visited = set()
        queue = [(service, 0)]
        while queue:
            svc, d = queue.pop(0)
            if svc in visited or d > depth:
                continue
            visited.add(svc)
            for dep in self._dependents.get(svc, set()):
                if dep not in visited:
                    queue.append((dep, d + 1))
        visited.discard(service)
        return {
            "service": service,
            "affected_services": sorted(visited),
            "depth": depth,
            "total_affected": len(visited),
        }

    def all_services(self) -> list[str]:
        """Return all known services."""
        svc_set = set(self._depends_on.keys()) | set(self._dependents.keys())
        return sorted(svc_set)

    def to_dict(self) -> dict[str, Any]:
        """Export as JSON-serializable dict for frontend D3/ECharts."""
        nodes = []
        edges = []
        seen = set()
        for svc in self.all_services():
            nodes.append({"id": svc, "label": svc})
            seen.add(svc)
            for dep in self._depends_on.get(svc, set()):
                edges.append({"from": svc, "to": dep})
                if dep not in seen:
                    nodes.append({"id": dep, "label": dep})
                    seen.add(dep)
        return {"nodes": nodes, "edges": edges}


# Singleton
topology = ServiceTopology()


def discover_from_k8s_endpoints(kubectl_output: str) -> None:
    """Parse kubectl get endpoints output and update topology.

    Example input:
      NAMESPACE   NAME               ENDPOINTS
      default     payment-service    10.244.1.5:8080,10.244.2.3:8080
    """
    lines = kubectl_output.strip().split("\n")
    if len(lines) < 2:
        return
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 3:
            namespace = parts[0]
            name = parts[1]
            # Endpoints column contains IPs — each IP:port pair is a pod
            # For now, just register the service
            topology._metadata[name] = {"namespace": namespace}
