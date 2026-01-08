"""
Nemori Backend - FastAPI Application Entry Point
"""
import argparse
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router as api_router
from config.settings import settings
from storage.database import Database
from services.llm_service import LLMService
from services.memory_service import MemoryService
from services.screenshot_service import ScreenshotService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Starting Nemori Backend...")

    # Initialize database
    db = Database.get_instance()
    await db.initialize()
    print(f"Database initialized at: {db.db_path}")

    # Initialize services
    llm_service = LLMService.get_instance()
    await llm_service.load_from_database()  # Load API key from database
    MemoryService.get_instance()
    ScreenshotService.get_instance()
    print("Services initialized")

    yield

    # Shutdown
    print("Shutting down Nemori Backend...")
    await db.close()


app = FastAPI(
    title="Nemori Backend",
    description="AI-powered personal memory assistant backend service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for Electron renderer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local desktop app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-Id", "X-Session-Id"],  # Expose custom headers to frontend
)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Nemori Backend",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    db = Database.get_instance()
    llm = LLMService.get_instance()

    return {
        "status": "healthy",
        "database": "connected" if db.is_connected() else "disconnected",
        "llm_configured": llm.is_configured(),
    }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Nemori Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=21978, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
