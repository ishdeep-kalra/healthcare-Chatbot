from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.services.logger import logger
from app.routes.document import router as document_router
from app.routes.chat import router as chat_router

app = FastAPI(
    title="Healthcare AI Chatbot API",
    description="A FastAPI backend supporting RAG chatbot with safety guardrails",
    version="1.0.0"
)

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include document ingestion and retrieval endpoints
app.include_router(document_router)
app.include_router(chat_router)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing Healthcare AI Chatbot Backend...")
    logger.info(f"CORS origins configured: {settings.CORS_ORIGINS}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")

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
        "gemini_api_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE")
    }

