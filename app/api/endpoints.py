from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.engine import get_db
from app.db.models import AuditLog, Feedback
from app.schemas.requests import ProcessRequest, FeedbackRequest
from app.schemas.responses import ProcessResponse, AuditLogResponse, JudgeDetails
from app.services.orchestrator import OrchestratorService

router = APIRouter()
orchestrator = OrchestratorService()

@router.post("/process", response_model=ProcessResponse)
async def process_task(request: ProcessRequest, db: Session = Depends(get_db)):
    try:
        # Run the full orchestrator pipeline
        result = await orchestrator.run_pipeline(request)
        
        # Asynchronously or synchronously insert to Audit Log DB
        new_log = AuditLog(
            input_hash=result["input_hash"],
            risk_level=result["risk_level"],
            route_decision=result["route"],
            explanation=result["explanation"],
            srd_count=result["srd_count"],
            model_used=result["model_used"],
            judge_status=result["judge"].get("status", "UNKNOWN")
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        
        # Format response
        return ProcessResponse(
            output=result["output"],
            risk_level=result["risk_level"],
            route=result["route"],
            explanation=result["explanation"],
            judge=JudgeDetails(**result["judge"]),
            srd_count=result["srd_count"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    try:
        fb = Feedback(
            audit_log_id=request.request_id,
            rating=request.rating,
            comments=request.comments
        )
        db.add(fb)
        db.commit()
        return {"status": "Feedback recorded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs", response_model=list[AuditLogResponse])
async def get_logs(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return logs
