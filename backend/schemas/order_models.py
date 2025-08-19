"""Order related pydantic models with stricter types.

- Use Enum for fulfillment type to prevent invalid values.
- Use datetime for the optional time field so ISO strings are parsed.
"""
from enum import Enum
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class FulfillmentType(str, Enum):
    pickup = "pickup"
    delivery = "delivery"

class OrderCreate(BaseModel):
    item: str
    quantity: int
    time: Optional[datetime]
    fulfillment: FulfillmentType

class OrderResponse(BaseModel):
    success: bool
    message: str
