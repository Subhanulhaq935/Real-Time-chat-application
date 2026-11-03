from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers.api import api_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Real-Time Chat Application API built with FastAPI, WebSockets, and PostgreSQL",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware configuration
cors_origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
cors_origins = [o.rstrip("/") for o in cors_origins if isinstance(o, str) and o.strip()]

# Regex matching all Vercel domains (*.vercel.app) and local development ports
vercel_and_local_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$"

if "*" in cors_origins:
    allow_origin_regex = r".*"
    cors_origins = []
else:
    allow_origin_regex = vercel_and_local_regex

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_router)  # Also expose /health at root for quick checks


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
        "api_v1": settings.API_V1_PREFIX,
    }

