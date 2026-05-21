from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class EARequest(BaseModel):
    query: str
    data: Optional[Dict[str, Any]] = {}
    agent_override: Optional[str] = None  # Force specific agent: ARB, TIME, MAPPING, MATURITY, INSIGHTS


class EAResponse(BaseModel):
    agent_used: str
    result: Dict[str, Any]
    agents_chain: List[str] = []
