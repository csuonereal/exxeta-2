from sqlalchemy import Column, Integer, String, DateTime, Float, Text
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Hashes and Tracking
    input_hash = Column(String, index=True, nullable=False)
    
    # Risk and Routing
    risk_level = Column(String, nullable=False)  # MINIMAL, LIMITED, HIGH, PROHIBITED
    route_decision = Column(String, nullable=False)  # LOCAL, API, HYBRID
    explanation = Column(Text, nullable=True)
    
    # SRD Count (don't store the actual SRD)
    srd_count = Column(Integer, default=0)
    
    # Model details
    model_used = Column(String, nullable=True)
    
    # Outcome
    judge_status = Column(String, nullable=True)  # APPROVED, FLAGGED, BLOCKED
    
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    audit_log_id = Column(Integer, nullable=True) # Join to audit log if needed
    rating = Column(String, nullable=False) # e.g. THUMBS_UP, THUMBS_DOWN
    comments = Column(Text, nullable=True)
