from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    chapter_router,
    question_router,
    retention_router,
    schedule_router,
    subject_router,
    test_router,
)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrackMate Backend",
    description="Test generation, scoring, retention, and smart schedule backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(subject_router.router)
app.include_router(chapter_router.router)
app.include_router(question_router.router)
app.include_router(test_router.router)
app.include_router(retention_router.router)
app.include_router(schedule_router.router)


@app.get("/")
def home():
    return {
        "message": "TrackMate backend is running",
        "docs": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
