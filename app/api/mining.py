from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.mining import MiningSettings
from app.schemas.mining import MiningSettingsRead, MiningSettingsUpdate

router = APIRouter(prefix="/mining", tags=["Mining"])


async def get_or_create_settings(db: AsyncSession) -> MiningSettings:
    settings = await db.get(MiningSettings, 1)
    if settings is None:
        settings = MiningSettings(id=1, wallet_address="")
        db.add(settings)
        await db.flush()
    return settings


@router.get("/settings", response_model=MiningSettingsRead)
async def read_settings(db: AsyncSession = Depends(get_db)):
    settings = await get_or_create_settings(db)
    await db.commit()
    return settings


@router.put("/settings", response_model=MiningSettingsRead)
async def update_settings(
    data: MiningSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    wallet = data.wallet_address.strip()
    if not wallet:
        raise HTTPException(status_code=422, detail="Wallet address cannot be empty")
    settings = await get_or_create_settings(db)
    settings.wallet_address = wallet
    await db.commit()
    await db.refresh(settings)
    return settings
