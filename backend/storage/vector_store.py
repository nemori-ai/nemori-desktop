"""
Vector Store using ChromaDB for semantic search
"""
import asyncio
from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings


class VectorStore:
    """ChromaDB-based vector store for memory embeddings"""

    _instance: Optional["VectorStore"] = None

    def __init__(self):
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None

    @classmethod
    def get_instance(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize ChromaDB client and collection"""
        # Create persistent client
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
        )

    def add_embedding(
        self,
        id: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        document: str
    ) -> None:
        """Add a single embedding to the collection"""
        self._collection.add(
            ids=[id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document]
        )

    def add_embeddings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str]
    ) -> None:
        """Add multiple embeddings to the collection"""
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the collection for similar embeddings"""
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"]
        )

    def query_by_text(
        self,
        text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query using text (requires embedding function to be set)"""
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
        """Update an existing embedding"""
        self._collection.update(
            ids=[id],
            embeddings=[embedding] if embedding else None,
            metadatas=[metadata] if metadata else None,
            documents=[document] if document else None
        )

    def delete(self, ids: List[str]) -> None:
        """Delete embeddings by IDs"""
        self._collection.delete(ids=ids)

    def count(self) -> int:
        """Get the number of embeddings in the collection"""
        return self._collection.count()

    def reset(self) -> None:
        """Reset the collection (delete all embeddings)"""
        self._client.delete_collection(settings.chroma_collection)
        self._collection = self._client.create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"}
        )
