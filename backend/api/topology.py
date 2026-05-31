"""Service Topology API — visualize dependency graph."""

from fastapi import APIRouter, Depends

from core.deps import get_current_user
from models.user import User
from services.knowledge_graph import topology

router = APIRouter(prefix="/api/topology", tags=["topology"])


@router.get("")
async def get_topology(current_user: User = Depends(get_current_user)):
    """Get the current service dependency topology."""
    return topology.to_dict()


@router.get("/blast-radius/{service}")
async def get_blast_radius(
    service: str,
    depth: int = 3,
    current_user: User = Depends(get_current_user),
):
    """Calculate blast radius if a service goes down."""
    return topology.blast_radius(service, depth)


@router.post("/edge")
async def add_dependency(
    service: str,
    depends_on: str,
    current_user: User = Depends(get_current_user),
):
    """Manually add a dependency edge."""
    topology.add_dependency(service, depends_on)
    return {"status": "ok"}


@router.delete("/edge")
async def remove_dependency(
    service: str,
    depends_on: str,
    current_user: User = Depends(get_current_user),
):
    """Manually remove a dependency edge."""
    topology.remove_service(service)
    return {"status": "ok"}
