from pydantic import BaseModel, SecretStr


class SSHProbeRequest(BaseModel):
    password: SecretStr | None = None
