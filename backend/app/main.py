from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.services.logger import logger
from app.routes.document import router as document_router
from app.routes.chat import router as chat_router
from app.services.rag_service import rag_service

app = FastAPI(
    title="Healthcare AI Chatbot API",
    description="A FastAPI backend supporting RAG chatbot with safety guardrails",
    version="1.0.0"
)

# Setup CORS middleware
# CORS_ORIGINS is configured via the CORS_ORIGINS environment variable on Render.
# In production, set it to your actual Vercel frontend URL(s), e.g.:
#   CORS_ORIGINS=["https://your-project.vercel.app"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
)

# Include document ingestion and retrieval endpoints
app.include_router(document_router)
app.include_router(chat_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Healthcare AI Chatbot Backend...")
    logger.info(f"CORS origins configured: {settings.CORS_ORIGINS}")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    if settings.CORS_ORIGINS == ["*"]:
        logger.warning("WARNING: CORS is set to wildcard (*). Set CORS_ORIGINS to your Vercel URL in production.")
    try:
        logger.info("Pre-loading medical document chunks into memory...")
        rag_service._load_chunks()
        logger.info("Successfully loaded medical document chunks.")
    except Exception as e:
        logger.error(f"Failed to pre-load medical document chunks: {e}")


@app.get("/")
async def root():
    return {
        "message": "Welcome to the Healthcare AI Chatbot API.",
        "status": "healthy",
        "docs_url": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint to verify backend status."""
    logger.debug("Health check endpoint hit")
    return {
        "status": "healthy",
        "service": "healthcare-chatbot-backend",
        "gemini_api_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE"),
        "cors_origins": settings.CORS_ORIGINS,
    }
