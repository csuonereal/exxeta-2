from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.engine import SessionLocal # Using SessionLocal directly for background commit
from app.db.models import AuditLog, Feedback
from app.schemas.requests import ProcessRequest, FeedbackRequest
from app.schemas.responses import ProcessResponse, AuditLogResponse, JudgeDetails
from app.services.orchestrator import OrchestratorService
import json

router = APIRouter()
orchestrator = OrchestratorService()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/process")
async def process_task(request: ProcessRequest):
    async def sse_event_generator():
        try:
            async for chunk in orchestrator.run_pipeline_stream(request):
                yield chunk
                # Intercept the 'complete' chunk to log into DB asynchronously
                if chunk.startswith("data: {\"step\": \"complete\""):
                    payload = json.loads(chunk[len("data: "):])
                    # Save DB log safely
                    db = SessionLocal()
                    try:
                        new_log = AuditLog(
                            input_hash=payload["input_hash"],
                            risk_level=payload["risk_level"],
                            route_decision=payload["route"],
                            explanation=payload["explanation"],
                            srd_count=payload["srd_count"],
                            model_used=payload["model_used"],
                            judge_status=payload["judge"].get("status", "UNKNOWN")
                        )
                        db.add(new_log)
                        db.commit()
                        db.refresh(new_log)
                    except Exception as e:
                        print(f"Error saving audit log: {e}")
                    finally:
                        db.close()
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Yield error event
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


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
