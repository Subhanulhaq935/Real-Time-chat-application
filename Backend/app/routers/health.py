from fastapi import APIRouter
from app.core.config import settings
from app.db.session import check_db_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health():
    db_alive = check_db_connection()
    return HealthResponse(
        status="healthy" if db_alive else "degraded",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
        database="connected" if db_alive else "disconnected",
    )

