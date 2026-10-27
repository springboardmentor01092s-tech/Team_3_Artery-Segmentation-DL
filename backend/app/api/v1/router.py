from fastapi import APIRouter

from app.api.v1.endpoints import analysis, auth, cases, health, images, notifications, patients, preprocessing, users

api_router = APIRouter()
for endpoint_router in (
    health.router,
    auth.router,
    users.router,
    patients.router,
    cases.router,
    images.router,
    preprocessing.router,
    analysis.router,
    notifications.router,
):
    api_router.include_router(endpoint_router)
