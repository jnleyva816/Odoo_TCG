"""Label-related Pydantic models."""

from pydantic import BaseModel, Field


class LabelRequest(BaseModel):
    """Request to print a label."""

    product_id: int = Field(..., description="Odoo product ID")
    quantity: int = Field(1, ge=1, le=100, description="Number of labels to print")


class LabelResponse(BaseModel):
    """Label print response."""

    success: bool = Field(..., description="Whether print was successful")
    message: str = Field(..., description="Status message")
    pdf_base64: str | None = Field(None, description="Base64 encoded PDF for preview")

