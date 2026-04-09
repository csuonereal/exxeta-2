from pydantic import BaseModel
from typing import Optional, Dict

class ProcessRequest(BaseModel):
    input_type: str = "text"  # "text", "email", "pdf"
    content: str     
    task: Optional[str] = "Process the attached context intelligently."  # Made optional for chat inference
    model_pref: Optional[str] = "auto" # "auto", "local", "proprietary"
    file_name: Optional[str] = None
    file_data: Optional[str] = None # base64 encoded data

class FeedbackRequest(BaseModel):
    request_id: int
    rating: str
    comments: Optional[str] = None
