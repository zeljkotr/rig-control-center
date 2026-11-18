from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Rig(Base):
    __tablename__ = "rigs"
    __table_args__ = (
        UniqueConstraint("host", "ssh_port", name="uq_rig_host_port"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    host: Mapped[str] = mapped_column(String(255), index=True)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    ssh_username: Mapped[str] = mapped_column(String(100))
    ssh_auth_method: Mapped[str] = mapped_column(String(20), default="key")

    cpu_threads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpu_limit_percent: Mapped[int] = mapped_column(Integer, default=75)

    pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("pools.id"), nullable=True
    )

    worker_status: Mapped[str] = mapped_column(String(30), default="not_deployed")
    connection_status: Mapped[str] = mapped_column(String(30), default="unknown")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
