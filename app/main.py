from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.db.engine import create_db_and_tables
from app.api.endpoints import router as api_router

app = FastAPI(
    title="Compliance-Aware AI Orchestration Middleware",
    description="Middleware for safe and compliant AI use with routing, SRD detection, and judge verification.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    print("Starting up and creating database tables...")
    create_db_and_tables()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}") # In production, use structured logging
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc) if app.debug else "Masked for security."}
    )

from fastapi.staticfiles import StaticFiles
import os

# Ensure static dir exists before mounting
os.makedirs("static", exist_ok=True)

@app.get("/health")
async def health_check():
    return {"status": "ok", "middleware": "active"}

app.include_router(api_router)

# Mount static folder AFTER all other routes so they aren't overridden
app.mount("/", StaticFiles(directory="static", html=True), name="static")
