from pydantic import BaseModel, Field
from typing import Optional


class AuditRequest(BaseModel):
    business_name: str
    city: str
    facebook_url: Optional[str] = None  # optional, defaults to None


class AuditReport(BaseModel):
    business_name: str
    facebook_presence_detected: bool
    vibe_analysis: str
    key_offerings: list[str] = []
    customer_pain_points: list[str] = []
    digital_presence_gaps: list[str] = []
    sentiment_summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    model_used: str