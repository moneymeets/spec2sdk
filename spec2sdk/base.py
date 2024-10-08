from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(
        frozen=True,  # make instance immutable and hashable
    )
