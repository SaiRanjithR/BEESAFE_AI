import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import sms_webhook, review_queue, conversations, simulated_bot, indicators, enrichment_webhook

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

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


# Startup event to auto-create tables and seed default persona
@app.on_event("startup")
def on_startup():
    db_target = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local/unknown"
    logger.info("Initializing database connection target: %s", db_target)
    try:
        from app.db.database import engine, Base
        import app.db.models  # noqa: F401 - registers models
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified/created successfully.")

        from app.db.seed import seed_database
        seed_database()
        logger.info("Database auto-seeded successfully.")
    except Exception as e:
        logger.error("Database startup initialization error: %s", str(e))


@app.get("/health", tags=["Health"])
async def health_check():
    db_status = "ok"
    try:
        from app.db.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }
