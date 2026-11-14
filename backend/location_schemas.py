
from pydantic import BaseModel, Field


class PlotLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PlotLocationResponse(BaseModel):
    location_id: int
    location_type: str
    latitude: float
    longitude: float
