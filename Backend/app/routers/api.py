from fastapi import APIRouter
from app.routers import health, auth, users, contacts, chats

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(contacts.router)
api_router.include_router(chats.router)

