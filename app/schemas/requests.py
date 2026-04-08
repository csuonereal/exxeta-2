from pydantic import BaseModel
from typing import Optional, Dict

class ProcessRequest(BaseModel):
    input_type: str  # "text", "email", "pdf"
    content: str     # For text/email it's the string. For PDF it might be base64. MVP will handle standard text for simplicity.
    task: str        # e.g., "summarize", "analyze"
    model_pref: Optional[str] = "auto" # "auto", "local", "proprietary"

class FeedbackRequest(BaseModel):
    request_id: int
    rating: str
    comments: Optional[str] = None
