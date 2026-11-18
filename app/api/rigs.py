import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException
from paramiko import AuthenticationException, BadHostKeyException, SSHException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.mining import MiningSettings, RigMiningConfig
from app.models.pool import Pool
from app.models.rig import Rig
from app.schemas.mining import MiningActionRequest, MiningDeployRequest, RigWorkerUpdate
from app.schemas.rig import RigCreate, RigRead
from app.schemas.ssh import SSHProbeRequest
from app.services.ssh import collect_metrics, control_xmrig, deploy_xmrig, probe_host

router = APIRouter(prefix="/rigs", tags=["Rigs"])


def ssh_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthenticationException):
        detail = "SSH authentication failed."
    elif isinstance(exc, BadHostKeyException):
        detail = "SSH host key mismatch. Verify the server identity."
    elif isinstance(exc, SSHException):
        detail = f"SSH connection failed: {exc}"
    elif isinstance(exc, (OSError, TimeoutError)):
        detail = f"Network connection failed: {exc}"
    else:
        detail = str(exc)
    return HTTPException(status_code=502, detail=detail)


def default_worker_id(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-.")
    return (value or "worker")[:100]


async def rig_read_with_worker(rig: Rig, db: AsyncSession) -> dict:
    config = await db.scalar(
        select(RigMiningConfig).where(RigMiningConfig.rig_id == rig.id)
    )
    result = RigRead.model_validate(rig).model_dump()
    result["worker_id"] = config.worker_id if config else default_worker_id(rig.name)
    return result


@router.get("", response_model=list[RigRead])
async def list_rigs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Rig).order_by(Rig.id))
    return [await rig_read_with_worker(rig, db) for rig in result.scalars().all()]


@router.get("/monitor", tags=["Monitoring"])
async def monitor_rigs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Rig).order_by(Rig.id))
    rigs = result.scalars().all()
    semaphore = asyncio.Semaphore(5)

    async def monitor_one(rig: Rig):
        if rig.ssh_auth_method != "key":
            return {
                "rig_id": rig.id,
                "name": rig.name,
                "online": None,
                "status": "manual_auth_required",
            }

        async with semaphore:
            try:
                metrics = await asyncio.to_thread(
                    collect_metrics, rig.host, rig.ssh_port, rig.ssh_username
                )
                return {
                    "rig_id": rig.id,
                    "name": rig.name,
                    "status": "online",
                    **metrics,
                }
            except Exception as exc:
                return {
                    "rig_id": rig.id,
                    "name": rig.name,
                    "online": False,
                    "status": "offline",
                    "error": str(exc),
                }

    return {"rigs": await asyncio.gather(*(monitor_one(rig) for rig in rigs))}


@router.delete("/{rig_id}")
async def delete_rig(
    rig_id: int,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")

    mining_config = await db.scalar(
        select(RigMiningConfig).where(RigMiningConfig.rig_id == rig_id)
    )
    if mining_config is not None:
        await db.delete(mining_config)

    await db.delete(rig)
    await db.commit()

    return {"message": "Rig deleted", "rig_id": rig_id}


@router.post("", response_model=RigRead, status_code=201)
async def create_rig(data: RigCreate, db: AsyncSession = Depends(get_db)):
    if data.pool_id is not None and await db.get(Pool, data.pool_id) is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    rig = Rig(**data.model_dump())
    db.add(rig)
    try:
        await db.flush()
        db.add(RigMiningConfig(rig_id=rig.id, worker_id=default_worker_id(rig.name)))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Rig name, host/SSH port, or Worker ID already exists",
        )
    await db.refresh(rig)
    return await rig_read_with_worker(rig, db)


@router.put("/{rig_id}", response_model=RigRead)
async def update_rig(
    rig_id: int,
    data: RigCreate,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")

    if data.pool_id is not None and await db.get(Pool, data.pool_id) is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    for field, value in data.model_dump().items():
        setattr(rig, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Rig name or host/SSH port already exists",
        )

    await db.refresh(rig)
    return await rig_read_with_worker(rig, db)


@router.put("/{rig_id}/worker")
async def update_rig_worker(
    rig_id: int,
    data: RigWorkerUpdate,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")
    config = await db.scalar(
        select(RigMiningConfig).where(RigMiningConfig.rig_id == rig_id)
    )
    if config is None:
        config = RigMiningConfig(rig_id=rig_id, worker_id=data.worker_id)
        db.add(config)
    else:
        config.worker_id = data.worker_id
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Worker ID is already assigned to another rig")
    return {"rig_id": rig_id, "worker_id": data.worker_id}


@router.post("/{rig_id}/probe", tags=["SSH"])
async def probe_rig(
    rig_id: int,
    credentials: SSHProbeRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")
    password = credentials.password.get_secret_value() if credentials and credentials.password else None
    try:
        inventory = await asyncio.to_thread(
            probe_host, rig.host, rig.ssh_port, rig.ssh_username, password
        )
        rig.connection_status = "online"
        if inventory.get("cpu_threads"):
            rig.cpu_threads = inventory["cpu_threads"]
        await db.commit()
        return {"rig_id": rig.id, "name": rig.name, **inventory}
    except Exception as exc:
        rig.connection_status = "offline"
        await db.commit()
        raise ssh_error(exc)


@router.post("/{rig_id}/deploy", tags=["Mining"])
async def deploy_rig(
    rig_id: int,
    request: MiningDeployRequest,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")
    if rig.pool_id is None:
        raise HTTPException(status_code=400, detail="Assign a mining pool before deployment")
    pool = await db.get(Pool, rig.pool_id)
    if pool is None or not pool.enabled:
        raise HTTPException(status_code=400, detail="Assigned pool is missing or disabled")

    settings = await db.get(MiningSettings, 1)
    if settings is None or not settings.wallet_address.strip():
        raise HTTPException(status_code=400, detail="Configure the global Monero wallet first")

    config = await db.scalar(
        select(RigMiningConfig).where(RigMiningConfig.rig_id == rig_id)
    )
    if config is None:
        config = RigMiningConfig(rig_id=rig_id, worker_id=default_worker_id(rig.name))
        db.add(config)
        await db.flush()

    wallet = settings.wallet_address
    worker_id = config.worker_id
    password = request.password.get_secret_value() if request.password else None

    try:
        result = await asyncio.to_thread(
            deploy_xmrig,
            rig.host,
            rig.ssh_port,
            rig.ssh_username,
            wallet,
            worker_id,
            pool.url,
            rig.cpu_limit_percent,
            password,
        )
        rig.connection_status = "online"
        rig.worker_status = "installed"
        await db.commit()
        return {"rig_id": rig.id, "name": rig.name, **result}
    except Exception as exc:
        await db.rollback()
        raise ssh_error(exc)


@router.post("/{rig_id}/action", tags=["Mining"])
async def mining_action(
    rig_id: int,
    request: MiningActionRequest,
    db: AsyncSession = Depends(get_db),
):
    rig = await db.get(Rig, rig_id)
    if rig is None:
        raise HTTPException(status_code=404, detail="Rig not found")
    password = request.password.get_secret_value() if request.password else None
    try:
        result = await asyncio.to_thread(
            control_xmrig,
            rig.host,
            rig.ssh_port,
            rig.ssh_username,
            request.action,
            password,
        )
        if request.action == "start":
            rig.worker_status = "running"
        elif request.action == "stop":
            rig.worker_status = "installed"
        elif request.action == "status":
            rig.worker_status = result["status"]
        elif request.action == "restart":
            rig.worker_status = "running"
        rig.connection_status = "online"
        await db.commit()
        return {"rig_id": rig.id, "name": rig.name, **result}
    except Exception as exc:
        raise ssh_error(exc)
