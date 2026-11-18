from pydantic import BaseModel, Field, SecretStr


class MiningSettingsUpdate(BaseModel):
    wallet_address: str = Field(min_length=20, max_length=150)


class MiningSettingsRead(BaseModel):
    wallet_address: str


class RigWorkerUpdate(BaseModel):
    worker_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )


class MiningDeployRequest(BaseModel):
    password: SecretStr | None = None


class MiningActionRequest(BaseModel):
    action: str = Field(pattern="^(start|stop|restart|status)$")
    password: SecretStr | None = None
