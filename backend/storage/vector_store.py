"""
Vector Store using ChromaDB for semantic search
Enhanced with graceful shutdown, thread safety, retry logic, and pending writes queue

Includes automatic handling of embedding dimension changes to prevent corruption.
"""
import atexit
import json
import os
import shutil
import signal
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings


# File to track embedding configuration
EMBEDDING_CONFIG_FILE = "embedding_config.json"


class VectorStore:
    """ChromaDB-based vector store for memory embeddings with robust error handling"""

    _instance: Optional["VectorStore"] = None

    def __init__(self):
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._initialized = False

        # Thread safety
        self._write_lock = threading.Lock()

        # Pending writes queue for retry on failure
        self._pending_writes: List[Dict[str, Any]] = []

        # Retry configuration
        self._max_retry_count = 3
        self._retry_delay = 0.5  # seconds

        # Cleanup registration flag
        self._cleanup_registered = False

    @classmethod
    def get_instance(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize_with_retry()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for retry after failure)"""
        if cls._instance is not None:
            cls._instance._cleanup()
        cls._instance = None

    def _register_cleanup_handlers(self) -> None:
        """Register graceful shutdown handlers"""
        if self._cleanup_registered:
            return

        # Register exit handler
        atexit.register(self._cleanup)

        # Register signal handlers (only works in main thread)
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except ValueError:
            # Signal handlers can only be registered in the main thread
            pass

        self._cleanup_registered = True

    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        print(f"VectorStore: Received signal {signum}, performing cleanup...")
        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up resources and persist pending data"""
        if not self._initialized:
            return

        try:
            with self._write_lock:
                # Flush pending writes
                if self._pending_writes:
                    print(f"VectorStore: Flushing {len(self._pending_writes)} pending writes...")
                    self._flush_pending_writes()

                print("VectorStore: Cleanup completed")
        except Exception as e:
            print(f"VectorStore: Error during cleanup: {e}")

    def _flush_pending_writes(self) -> None:
        """Flush all pending write operations"""
        if not self._collection:
            return

        for write_op in self._pending_writes:
            try:
                op_type = write_op.get("type")
                if op_type == "add":
                    self._collection.add(
                        ids=write_op["ids"],
                        embeddings=write_op["embeddings"],
                        metadatas=write_op["metadatas"],
                        documents=write_op["documents"]
                    )
                elif op_type == "update":
                    self._collection.update(
                        ids=write_op["ids"],
                        embeddings=write_op.get("embeddings"),
                        metadatas=write_op.get("metadatas"),
                        documents=write_op.get("documents")
                    )
                elif op_type == "delete":
                    self._collection.delete(ids=write_op["ids"])
            except Exception as e:
                print(f"VectorStore: Failed to flush pending write: {e}")

        self._pending_writes.clear()

    def _initialize_with_retry(self) -> None:
        """Initialize ChromaDB with retry logic"""
        last_error = None

        for attempt in range(self._max_retry_count):
            try:
                self._initialize()
                self._initialized = True
                self._register_cleanup_handlers()
                print(f"VectorStore: Initialized successfully (attempt {attempt + 1})")
                return
            except Exception as e:
                last_error = e
                print(f"VectorStore: Initialization attempt {attempt + 1} failed: {e}")

                # Clean up failed state
                self._client = None
                self._collection = None

                if attempt < self._max_retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))  # Exponential backoff

        # All retries failed
        raise RuntimeError(f"VectorStore: Failed to initialize after {self._max_retry_count} attempts: {last_error}")

    def _initialize(self) -> None:
        """Initialize ChromaDB client and collection with dimension safety checks"""
        chroma_path = str(settings.chroma_path)

        # Check for embedding configuration changes that require reset
        config_path = os.path.join(os.path.dirname(chroma_path), EMBEDDING_CONFIG_FILE)
        current_config = self._get_current_embedding_config()
        stored_config = self._load_embedding_config(config_path)

        # Detect dimension mismatch
        if stored_config and current_config:
            if stored_config.get("model") != current_config.get("model"):
                print(f"VectorStore: Embedding model changed from '{stored_config.get('model')}' to '{current_config.get('model')}'")
                print("VectorStore: Clearing vector store to prevent dimension mismatch corruption...")
                self._backup_and_clear_chroma(chroma_path)

        # Create persistent client
        try:
            self._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception as e:
            # If ChromaDB fails to initialize (likely corruption), backup and retry
            error_str = str(e).lower()
            if "panic" in error_str or "range" in error_str or "index" in error_str or "corrupt" in error_str:
                print(f"VectorStore: ChromaDB corruption detected: {e}")
                print("VectorStore: Backing up corrupted database and creating fresh instance...")
                self._backup_and_clear_chroma(chroma_path)

                # Retry after clearing
                self._client = chromadb.PersistentClient(
                    path=chroma_path,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
            else:
                raise

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
        )

        # Save current embedding config for future comparison
        self._save_embedding_config(config_path, current_config)

    def _get_current_embedding_config(self) -> Dict[str, Any]:
        """Get current embedding model configuration from settings/database"""
        # Default fallback config
        default_config = {
            "model": getattr(settings, 'embedding_model', 'text-embedding-3-small'),
            "base_url": getattr(settings, 'embedding_base_url', 'https://api.openai.com/v1')
        }

        try:
            # Try to get from database settings
            import asyncio
            from storage.database import Database

            async def _get_config():
                db = Database.get_instance()
                model = await db.get_setting("embedding_model")
                base_url = await db.get_setting("embedding_base_url")
                return {
                    "model": model or default_config["model"],
                    "base_url": base_url or default_config["base_url"]
                }

            # Run async function
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, use default config
                    return default_config
                return loop.run_until_complete(_get_config())
            except RuntimeError:
                # No event loop, create one
                return asyncio.run(_get_config())
        except Exception as e:
            print(f"VectorStore: Could not get embedding config from database: {e}")
            return default_config

    def _load_embedding_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        """Load stored embedding configuration"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"VectorStore: Could not load embedding config: {e}")
        return None

    def _save_embedding_config(self, config_path: str, config: Dict[str, Any]) -> None:
        """Save current embedding configuration"""
        try:
            config["saved_at"] = datetime.now().isoformat()
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"VectorStore: Could not save embedding config: {e}")

    def _backup_and_clear_chroma(self, chroma_path: str) -> None:
        """Backup corrupted ChromaDB and create fresh instance"""
        if os.path.exists(chroma_path):
            backup_path = f"{chroma_path}.backup.{int(time.time())}"
            try:
                shutil.move(chroma_path, backup_path)
                print(f"VectorStore: Backed up corrupted database to {backup_path}")
            except Exception as e:
                print(f"VectorStore: Could not backup, trying to remove: {e}")
                try:
                    shutil.rmtree(chroma_path)
                    print(f"VectorStore: Removed corrupted database at {chroma_path}")
                except Exception as e2:
                    print(f"VectorStore: Could not remove corrupted database: {e2}")

    def is_initialized(self) -> bool:
        """Check if the vector store is properly initialized"""
        return self._initialized and self._client is not None and self._collection is not None

    def add_embedding(
        self,
        id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str
    ) -> None:
        """Add a single embedding to the collection"""
        self.add_embeddings([id], [embedding], [metadata], [document])

    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str]
    ) -> None:
        """Add multiple embeddings to the collection with thread safety"""
        if not self.is_initialized():
            raise RuntimeError("VectorStore not initialized")

        with self._write_lock:
            try:
                self._collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
            except Exception as e:
                print(f"VectorStore: Add failed, queuing for retry: {e}")
                # Queue for later retry
                self._pending_writes.append({
                    "type": "add",
                    "ids": ids,
                    "embeddings": embeddings,
                    "metadatas": metadatas,
                    "documents": documents
                })
                raise

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the collection for similar embeddings"""
        if not self.is_initialized():
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        with self._write_lock:
            try:
                # Check if collection is empty
                if self._collection.count() == 0:
                    return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

                return self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                    where_document=where_document,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                # Handle HNSW index errors gracefully
                error_str = str(e).lower()
                if "hnsw" in error_str or "nothing found" in error_str:
                    print(f"VectorStore: Query skipped (empty index): {e}")
                    return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
                raise

    def query_by_text(
        self,
        text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query using text (requires embedding function to be set)"""
        if not self.is_initialized():
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        with self._write_lock:
            return self._collection.query(
                query_texts=[text],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get embeddings by IDs or filter"""
        if not self.is_initialized():
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

        with self._write_lock:
            return self._collection.get(
                ids=ids,
                where=where,
                limit=limit,
                include=["documents", "metadatas", "embeddings"]
            )

    def update(
        self,
        id: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        document: Optional[str] = None
    ) -> None:
        """Update an existing embedding with thread safety"""
        if not self.is_initialized():
            raise RuntimeError("VectorStore not initialized")

        with self._write_lock:
            try:
                self._collection.update(
                    ids=[id],
                    embeddings=[embedding] if embedding else None,
                    metadatas=[metadata] if metadata else None,
                    documents=[document] if document else None
                )
            except Exception as e:
                print(f"VectorStore: Update failed, queuing for retry: {e}")
                self._pending_writes.append({
                    "type": "update",
                    "ids": [id],
                    "embeddings": [embedding] if embedding else None,
                    "metadatas": [metadata] if metadata else None,
                    "documents": [document] if document else None
                })
                raise

    def delete(self, ids: List[str]) -> None:
        """Delete embeddings by IDs with thread safety"""
        if not self.is_initialized():
            return

        with self._write_lock:
            try:
                self._collection.delete(ids=ids)
            except Exception as e:
                print(f"VectorStore: Delete failed, queuing for retry: {e}")
                self._pending_writes.append({
                    "type": "delete",
                    "ids": ids
                })

    def count(self) -> int:
        """Get the number of embeddings in the collection"""
        if not self.is_initialized():
            return 0

        with self._write_lock:
            return self._collection.count()

    def reset(self) -> None:
        """Reset the collection (delete all embeddings)"""
        if not self.is_initialized():
            return

        with self._write_lock:
            self._client.delete_collection(settings.chroma_collection)
            self._collection = self._client.create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"}
            )

    def get_pending_writes_count(self) -> int:
        """Get the number of pending write operations"""
        return len(self._pending_writes)

    def retry_pending_writes(self) -> int:
        """Manually retry pending writes, returns number of successful operations"""
        if not self.is_initialized() or not self._pending_writes:
            return 0

        with self._write_lock:
            initial_count = len(self._pending_writes)
            self._flush_pending_writes()
            return initial_count - len(self._pending_writes)
