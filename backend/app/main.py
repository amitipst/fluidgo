from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, dsr, meetings, leads, pipeline, analytics, ai

app = FastAPI(title="fluidGo API", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
app.include_router(dsr.router,       prefix="/api/dsr",       tags=["dsr"])
app.include_router(meetings.router,  prefix="/api/meetings",  tags=["meetings"])
app.include_router(leads.router,     prefix="/api/leads",     tags=["leads"])
app.include_router(pipeline.router,  prefix="/api/pipeline",  tags=["pipeline"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(ai.router,        prefix="/api/ai",        tags=["ai"])

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "fluidGo", "version": "1.0.0"}
