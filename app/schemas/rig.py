from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=100)
    ssh_auth_method: str = Field(default="key", pattern="^(key|password)$")
    cpu_threads: int | None = Field(default=None, ge=1)
    cpu_limit_percent: int = Field(default=75, ge=1, le=100)
    pool_id: int | None = None


class RigRead(RigCreate):
    id: int
    worker_id: str | None = None
    worker_status: str
    connection_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
