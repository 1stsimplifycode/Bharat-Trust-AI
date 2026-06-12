"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel
from typing import Optional, Any


class SupportRequest(BaseModel):
    message: str
    lang: str = "en"
    order_id: Optional[int] = None


class ReturnPredictRequest(BaseModel):
    seller_id: int
    product_id: int
    delivery_days: int = 4


class LogisticsRequest(BaseModel):
    dest_lat: float
    dest_lng: float


class PriceRequest(BaseModel):
    product_id: int


class GenericResponse(BaseModel):
    ok: bool = True
    data: Any = None
