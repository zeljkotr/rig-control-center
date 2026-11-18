from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.pool import Pool
from app.models.rig import Rig
from app.schemas.pool import PoolCreate, PoolRead

router = APIRouter(prefix="/pools", tags=["Pools"])


@router.get("", response_model=list[PoolRead])
async def list_pools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pool).order_by(Pool.id))
    return result.scalars().all()


@router.post("", response_model=PoolRead, status_code=201)
async def create_pool(data: PoolCreate, db: AsyncSession = Depends(get_db)):
    pool = Pool(**data.model_dump())
    db.add(pool)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Pool name already exists")
    await db.refresh(pool)
    return pool


@router.delete("/{pool_id}")
async def delete_pool(pool_id: int, db: AsyncSession = Depends(get_db)):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    assigned_rig = await db.scalar(
        select(Rig.id).where(Rig.pool_id == pool_id).limit(1)
    )
    if assigned_rig is not None:
        raise HTTPException(
            status_code=409,
            detail="Pool is assigned to a rig. Unassign it before deleting."
        )

    await db.delete(pool)
    await db.commit()
    return {"message": "Pool deleted", "pool_id": pool_id}

@router.put("/{pool_id}", response_model=PoolRead)
async def update_pool(
    pool_id: int,
    data: PoolCreate,
    db: AsyncSession = Depends(get_db),
):
    pool = await db.get(Pool, pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    pool.name = data.name
    pool.url = data.url
    pool.pool_type = data.pool_type
    pool.enabled = data.enabled
    pool.is_default = data.is_default

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Pool name already exists")

    await db.refresh(pool)
    return pool
