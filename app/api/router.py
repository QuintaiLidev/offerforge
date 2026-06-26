from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.knowledge_cards import router as knowledge_cards_router

api_router: APIRouter = APIRouter()
api_router.include_router(health_router)
api_router.include_router(knowledge_cards_router)
