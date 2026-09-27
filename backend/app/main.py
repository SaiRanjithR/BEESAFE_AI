import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import sms_webhook, review_queue, conversations, simulated_bot, indicators, enrichment_webhook

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="TrapLine API",
    description="TrapLine B2B Fraud Intelligence API",
    version="0.1.0",
)

# Enable CORS for frontend dashboard
# FRONTEND_ORIGIN supports comma-separated origins (e.g., "http://localhost:5173,https://trapline.vercel.app")
allowed_origins = [o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sms_webhook.router)
app.include_router(review_queue.router)
app.include_router(conversations.router)
app.include_router(simulated_bot.router)
app.include_router(indicators.router)
app.include_router(enrichment_webhook.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
