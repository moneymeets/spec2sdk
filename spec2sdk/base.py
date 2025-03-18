from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # make instance immutable and hashable
        strict=True,  # strict validation is applied to all fields to avoid coercing values
    )
