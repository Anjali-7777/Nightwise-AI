from typing import Literal, Optional
from pydantic import BaseModel, Field

class ParsedUserQuery(BaseModel):
    origin: str = Field(description="Starting place, landmark, or saved location (e.g. 'office', 'MG Road', 'Indiranagar')")
    destination: str = Field(description="Destination landmark or saved location (e.g. 'home', 'Koramangala')")
    mode: Literal["walking", "driving"] = Field(default="walking", description="Travel mode")
    departure_time: str = Field(default="now", description="Time of departure, e.g. '2:00 AM', 'now', '23:30'")
    confidence: float = Field(default=1.0, description="Extraction confidence score")
    raw_query: Optional[str] = None

class AgentChatRequest(BaseModel):
    message: str = Field(description="Natural language query from user")
    saved_places: Optional[dict[str, str]] = Field(default=None, description="Optional user saved places like {'home': 'Indiranagar', 'office': 'Church Street'}")

class StructuredRouteRequest(BaseModel):
    origin: str
    destination: str
    mode: Literal["walking", "driving"] = "walking"
    departure_time: Optional[str] = "now"

class AgentChatResponse(BaseModel):
    parsed: ParsedUserQuery
    routes: list[dict]
    recommendation: Optional[str] = None
    safest_route_id: Optional[str] = None
    fastest_route_id: Optional[str] = None
    trade_off_summary: str
    trace: list[str]
    disclaimer: str
    origin: Optional[dict] = None
    destination: Optional[dict] = None
    data_confidence: Optional[str] = None
    confidence_warning: Optional[str] = None
    trade_off: Optional[dict] = None
    corridor_places: Optional[list[dict]] = None
    corridor_cameras: Optional[list[dict]] = None
