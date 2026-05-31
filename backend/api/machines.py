"""Machine management API: CRUD + SSH health check."""

from datetime import datetime, timezone

import paramiko
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from database import get_db
from models.machine import Machine
from models.user import User
from schemas.machine import MachineCreate, MachineUpdate
from services.security import sanitize_dict

router = APIRouter(prefix="/api/machines", tags=["machines"])


def _require_admin(user: User):
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin or superadmin required")


def _check_ssh(host: str, port: int, username: str, password: str, timeout: int = 5) -> bool:
    """Test SSH connectivity to a machine."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, port=port, username=username, password=password, timeout=timeout)
        client.close()
        return True
    except Exception:
        return False


@router.get("")
async def list_machines(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered machines."""
    result = await db.execute(select(Machine).order_by(Machine.id))
    machines = result.scalars().all()
    return {
        "items": [
            {
                "id": m.id, "name": m.name, "host": m.host, "port": m.port,
                "username": m.username, "description": m.description,
                "is_default": m.is_default, "online": m.online,
                "last_check_at": m.last_check_at.isoformat() if m.last_check_at else None,
            }
            for m in machines
        ]
    }


@router.post("")
async def create_machine(
    body: MachineCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new machine (admin+)."""
    _require_admin(current_user)

    existing = (await db.execute(select(Machine).where(Machine.name == body.name))).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="Machine name already exists")

    machine = Machine(
        name=body.name, host=body.host, port=body.port,
        username=body.username, password=body.password,
        description=body.description,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)
    return {"status": "ok", "machine_id": machine.id}


@router.put("/{machine_id}")
async def update_machine(
    machine_id: int,
    body: MachineUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update machine config (admin+)."""
    _require_admin(current_user)

    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if body.name is not None: machine.name = body.name
    if body.host is not None: machine.host = body.host
    if body.port is not None: machine.port = body.port
    if body.username is not None: machine.username = body.username
    if body.password is not None: machine.password = body.password
    if body.description is not None: machine.description = body.description
    if body.is_default is not None:
        # Clear other defaults
        await db.execute(update(Machine).values(is_default=False))
        machine.is_default = True

    await db.commit()
    return {"status": "ok"}


@router.delete("/{machine_id}")
async def delete_machine(
    machine_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a machine (admin+)."""
    _require_admin(current_user)
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    await db.delete(machine)
    await db.commit()
    return {"status": "ok"}


@router.post("/{machine_id}/check")
async def check_machine(
    machine_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check SSH connectivity and update online status."""
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    online = _check_ssh(machine.host, machine.port, machine.username, machine.password)
    machine.online = online
    machine.last_check_at = datetime.now(timezone.utc)
    await db.commit()

    return {"online": online, "checked_at": machine.last_check_at.isoformat()}


@router.post("/{machine_id}/set-default")
async def set_default(
    machine_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a machine as the default for operations."""
    _require_admin(current_user)
    machine = await db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    await db.execute(update(Machine).values(is_default=False))
    machine.is_default = True
    await db.commit()
    return {"status": "ok"}
