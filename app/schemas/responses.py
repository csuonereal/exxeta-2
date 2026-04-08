from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class JudgeDetails(BaseModel):
    status: str
    reasoning: str

class ProcessResponse(BaseModel):
    output: str
    risk_level: str
    route: str
    explanation: str
    judge: JudgeDetails
    srd_count: int

class AuditLogResponse(BaseModel):
    id: int
    timestamp: str
    input_hash: str
    risk_level: str
    route_decision: str
    srd_count: int
    model_used: str
    judge_status: str
    
    model_config = {"from_attributes": True}
