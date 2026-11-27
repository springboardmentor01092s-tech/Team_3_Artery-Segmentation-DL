from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Artery Segmentation and Stenosis Detection API",
    version="0.1.0",
    description="Synchronous, owner-scoped segmentation inference is available through an isolated ML runtime. Outputs are not clinically validated.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router, prefix="/api/v1")
