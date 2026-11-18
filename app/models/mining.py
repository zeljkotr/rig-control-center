from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MiningSettings(Base):
    __tablename__ = "mining_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    wallet_address: Mapped[str] = mapped_column(String(150), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RigMiningConfig(Base):
    __tablename__ = "rig_mining_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rig_id: Mapped[int] = mapped_column(
        ForeignKey("rigs.id", ondelete="CASCADE"), unique=True, index=True
    )
    worker_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
