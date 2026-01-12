"""
Nemori Backend - FastAPI Application Entry Point

Can be run in two modes:
1. Development: python main.py [--reload]
2. Production (bundled): ./nemori-backend --host 127.0.0.1 --port 21978
"""
import argparse
import os
import sys
import time
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router as api_router
from config.settings import settings
from storage.database import Database
from storage.vector_store import VectorStore
from services.llm_service import LLMService
from services.memory_service import MemoryService
from services.screenshot_service import ScreenshotService

# Support for bundled executable - set data directory from environment
if os.environ.get('NEMORI_DATA_DIR'):
    from pathlib import Path
    settings.data_dir = Path(os.environ['NEMORI_DATA_DIR'])


def _init_vector_store_with_retry(max_retries: int = 3) -> None:
    """Initialize VectorStore with retry logic to handle ChromaDB initialization bugs"""
    for attempt in range(max_retries):
        try:
            vector_store = VectorStore.get_instance()
            # Verify it's working by calling count()
            vector_store.count()
            print(f"VectorStore initialized successfully (attempt {attempt + 1})")
            return
        except Exception as e:
            print(f"VectorStore initialization attempt {attempt + 1} failed: {e}")
            # Reset the singleton to allow retry
            VectorStore._instance = None
            if attempt < max_retries - 1:
                time.sleep(0.5)  # Brief delay before retry
            else:
                print("Warning: VectorStore initialization failed after all retries, continuing without vector store")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Starting Nemori Backend...")

    # Initialize database
    db = Database.get_instance()
    await db.initialize()
    print(f"Database initialized at: {db.db_path}")

    # Initialize VectorStore early with retry logic to avoid first-request errors
    # This addresses ChromaDB bug: https://github.com/chroma-core/chroma/issues/5909
    _init_vector_store_with_retry()

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
    """CLI entry point - supports both development and bundled execution"""
    parser = argparse.ArgumentParser(description="Nemori Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=21978, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")

    args = parser.parse_args()

    # Check if running as bundled executable (PyInstaller)
    is_bundled = getattr(sys, 'frozen', False)

    if is_bundled:
        # Running as bundled executable - run app directly
        print(f"Starting Nemori Backend (bundled) on {args.host}:{args.port}")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )
    else:
        # Development mode - use string reference for reload support
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info"
        )


if __name__ == "__main__":
    main()
