from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500)
    pool_type: str = Field(default="custom", max_length=30)
    enabled: bool = True
    is_default: bool = False


class PoolRead(PoolCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
