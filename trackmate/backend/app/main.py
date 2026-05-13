from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    auth_router,
    chapter_router,
    question_router,
    retention_router,
    schedule_router,
    subject_router,
    test_router,
    notification_router,
    history_router,
    revision_router,
    coach_router

)


from app.services.background_scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrackMate Backend",
    description="TrackMate test generation, scoring, retention, schedule and authentication backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(subject_router.router)
app.include_router(chapter_router.router)
app.include_router(question_router.router)
app.include_router(test_router.router)
app.include_router(retention_router.router)
app.include_router(schedule_router.router)
app.include_router(notification_router.router)
app.include_router(history_router.router)
app.include_router(revision_router.router)
app.include_router(coach_router.router)


@app.get("/")
def home():
    return {
        "message": "TrackMate backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }

@app.on_event("startup")
def startup_event():
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event():
    stop_scheduler()
# python -m uvicorn app.main:app --reload