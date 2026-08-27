import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, SessionLocal, engine
from app.services.outbox_metrics import observe_database_error, refresh_outbox_gauges
from app.routers import admin_outbox, phase_a, phase_b, review_tasks, stylist, taxonomy_learning, vision, wardrobe, workflow


UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# SQLite demo remains self-contained; PostgreSQL deployments must apply Alembic revisions first.
_auto_create_default = "1" if engine.dialect.name == "sqlite" else "0"
if os.getenv("AI_STYLIST_AUTO_CREATE_DB", _auto_create_default).strip().lower() in {"1", "true", "yes", "on"}:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI 3D Stylist API",
    description="Backend for the AI 3D Stylist and Virtual Wardrobe Application",
    version="1.0.0",
)

# Configure CORS so the frontend app can communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to AI 3D Stylist API!"}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AI 3D Stylist Backend"}


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
    authorization: str | None = Header(default=None),
):
    """Expose Prometheus metrics; network policy or METRICS_TOKEN must protect this in production."""
    expected_token = os.getenv("METRICS_TOKEN")
    bearer_token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if expected_token and x_metrics_token != expected_token and bearer_token != expected_token:
        raise HTTPException(status_code=403, detail="Metrics token is invalid")
    db = SessionLocal()
    try:
        refresh_outbox_gauges(db)
    except Exception:
        db.rollback()
        observe_database_error("metrics_scrape")
    finally:
        db.close()
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(wardrobe.router)
app.include_router(vision.router)
app.include_router(stylist.router)
app.include_router(phase_a.router)
app.include_router(phase_b.router)
app.include_router(workflow.router)
app.include_router(admin_outbox.router)
app.include_router(review_tasks.router)
app.include_router(taxonomy_learning.router)

# One absolute root avoids a working-directory mismatch between API, Celery, and manifests.
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

