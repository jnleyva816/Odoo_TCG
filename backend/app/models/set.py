"""Set-related Pydantic models."""

from pydantic import BaseModel, Field


class SetInfo(BaseModel):
    """Pokemon TCG set information."""

    id: int = Field(..., description="Odoo category ID")
    name: str = Field(..., description="Set name")
    card_count: int = Field(0, description="Number of cards in set")



