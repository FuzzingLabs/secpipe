"""TODO."""

from pydantic import BaseModel


class Base(BaseModel):
    """TODO."""

    model_config = {
        "from_attributes": True,
    }
