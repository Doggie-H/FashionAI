from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class WardrobeItemBase(BaseModel):
    name: str
    category: str
    color: str
    image_url: Optional[str] = None

class WardrobeItemCreate(WardrobeItemBase):
    pass

class WardrobeItem(WardrobeItemBase):
    id: int
    owner_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: str
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    items: List[WardrobeItem] = []
    
    class Config:
        from_attributes = True


class MeasurementProfile(BaseModel):
    height: float = Field(..., ge=120, le=230)
    weight: float = Field(..., ge=30, le=250)
    shoulder: float = Field(..., ge=25, le=80)
    bust: float = Field(..., ge=50, le=180)
    waist: float = Field(..., ge=40, le=180)
    hip: float = Field(..., ge=50, le=200)
    inseam: float = Field(..., ge=45, le=120)
    shoulder_slope: Literal["straight", "sloped"] = "straight"
    chest_profile: Literal["full", "flat"] = "full"
    leg_alignment: Literal["straight", "bowed"] = "straight"
