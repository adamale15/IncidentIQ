"""
FastAPI application entry point for Incident Intelligence Platform.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import settings
from app.db.session import engine, init_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Incident Intelligence Platform API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # TODO: Initialize Qdrant connection
    # TODO: Initialize Redis connection
    # TODO: Load embedding models
    
    yield
    
    # Shutdown
    logger.info("Shutting down Incident Intelligence Platform API")
    await engine.dispose()


app = FastAPI(
    title="Incident Intelligence Platform",
    description="RAG platform for incident history search and analysis",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Incident Intelligence Platform",
        "version": "0.1.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
from app.routers import query
app.include_router(query.router, prefix="/api", tags=["query"])

# TODO: Add remaining routers as they're implemented
# from app.routers import auth, sources, conversations, eval, admin
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
# app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
# app.include_router(eval.router, prefix="/api/eval", tags=["evaluation"])
# app.include_router(admin.router, prefix="/api", tags=["admin"])
