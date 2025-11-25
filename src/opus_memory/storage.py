"""
Storage backend for Opus Memory using ChromaDB.

Handles persistence, retrieval, and vector search.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from opus_memory.embeddings import EmbeddingEngine
from opus_memory.models import Memory, MemoryType


class MemoryStore:
    """
    Persistent storage for memories using ChromaDB.

    Each memory type gets its own collection for efficient querying.
    """

    def __init__(
        self,
        storage_path: str = "./opus_memories",
        embedding_engine: Optional[EmbeddingEngine] = None,
    ):
        """
        Initialize the memory store.

        Args:
            storage_path: Directory to store the ChromaDB database
            embedding_engine: Engine for creating embeddings (creates default if None)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.embedding_engine = embedding_engine or EmbeddingEngine()

        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.storage_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Create collections for each memory type
        self.collections = {}
        for memory_type in MemoryType:
            self.collections[memory_type] = self.client.get_or_create_collection(
                name=f"opus_{memory_type.value}",
                metadata={"description": f"Opus {memory_type.value} memories"},
            )

    def store(self, memory: Memory) -> str:
        """
        Store a memory in the appropriate collection.

        Args:
            memory: The memory to store

        Returns:
            The ID of the stored memory
        """
        collection = self.collections[memory.memory_type]

        # Create embedding for the content
        embedding = self.embedding_engine.embed(memory.content)

        # Store in ChromaDB
        collection.upsert(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[memory.to_storage_dict()],
        )

        return memory.id

    def retrieve_by_id(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a specific memory by its ID."""
        for memory_type, collection in self.collections.items():
            try:
                result = collection.get(ids=[memory_id], include=["documents", "metadatas"])
                if result["ids"]:
                    return Memory.from_storage_dict(
                        result["metadatas"][0], result["documents"][0]
                    )
            except Exception:
                continue
        return None

    def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        n_results: int = 10,
        min_salience: float = 0.0,
        include_decayed: bool = False,
    ) -> list[tuple[Memory, float]]:
        """
        Search for relevant memories using semantic similarity.

        Args:
            query: The search query
            memory_types: Which memory types to search (None = all)
            n_results: Maximum number of results per collection
            min_salience: Minimum salience threshold
            include_decayed: Whether to include heavily decayed memories

        Returns:
            List of (memory, similarity_score) tuples, sorted by relevance
        """
        query_embedding = self.embedding_engine.embed(query)
        types_to_search = memory_types or list(MemoryType)

        all_results = []

        for memory_type in types_to_search:
            collection = self.collections[memory_type]

            # Build filter conditions
            where = {}
            if min_salience > 0:
                where["salience"] = {"$gte": min_salience}

            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                    where=where if where else None,
                )

                if results["ids"] and results["ids"][0]:
                    for i, memory_id in enumerate(results["ids"][0]):
                        metadata = results["metadatas"][0][i]
                        document = results["documents"][0][i]
                        distance = results["distances"][0][i]

                        # Convert distance to similarity (ChromaDB uses L2 by default)
                        # For cosine similarity collections, distance is already 1 - similarity
                        similarity = 1 - (distance / 2)  # Approximate conversion

                        # Check decay
                        if not include_decayed:
                            decay_rate = float(metadata.get("decay_rate", 0))
                            if decay_rate > 0:
                                created = datetime.fromisoformat(metadata["created_at"])
                                age_days = (datetime.utcnow() - created).days
                                decay_factor = decay_rate * age_days / 365
                                if decay_factor > 0.8:  # More than 80% decayed
                                    continue

                        memory = Memory.from_storage_dict(metadata, document)
                        all_results.append((memory, similarity))

            except Exception as e:
                # Log but don't fail on individual collection errors
                print(f"Error searching {memory_type.value}: {e}")
                continue

        # Sort by similarity (descending) and apply salience weighting
        all_results.sort(key=lambda x: x[1] * (0.5 + 0.5 * x[0].salience), reverse=True)

        return all_results[:n_results]

    def get_recent(
        self,
        memory_types: Optional[list[MemoryType]] = None,
        days: int = 7,
        limit: int = 50,
    ) -> list[Memory]:
        """Get recently created memories."""
        types_to_search = memory_types or list(MemoryType)
        cutoff = datetime.utcnow().isoformat()
        # Simple approach: get all and filter (ChromaDB date filtering is limited)

        all_memories = []
        for memory_type in types_to_search:
            collection = self.collections[memory_type]
            try:
                results = collection.get(
                    include=["documents", "metadatas"],
                    limit=limit * 2,  # Get extra to account for filtering
                )
                if results["ids"]:
                    for i, memory_id in enumerate(results["ids"]):
                        metadata = results["metadatas"][i]
                        document = results["documents"][i]
                        memory = Memory.from_storage_dict(metadata, document)
                        age_days = (datetime.utcnow() - memory.created_at).days
                        if age_days <= days:
                            all_memories.append(memory)
            except Exception:
                continue

        # Sort by creation time (newest first)
        all_memories.sort(key=lambda m: m.created_at, reverse=True)
        return all_memories[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        for collection in self.collections.values():
            try:
                collection.delete(ids=[memory_id])
                return True
            except Exception:
                continue
        return False

    def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories, optionally filtered by type."""
        if memory_type:
            return self.collections[memory_type].count()
        return sum(c.count() for c in self.collections.values())

    def get_embeddings_for_type(
        self, memory_type: MemoryType, limit: int = 100
    ) -> list[list[float]]:
        """Get embeddings for memories of a specific type (for salience calculation)."""
        collection = self.collections[memory_type]
        results = collection.get(include=["embeddings"], limit=limit)
        embeddings = results.get("embeddings")
        if embeddings is None or (hasattr(embeddings, '__len__') and len(embeddings) == 0):
            return []
        return list(embeddings)

    def export_all(self) -> dict:
        """Export all memories as a JSON-serializable dict."""
        export = {}
        for memory_type in MemoryType:
            collection = self.collections[memory_type]
            results = collection.get(include=["documents", "metadatas"])
            memories = []
            if results["ids"]:
                for i, memory_id in enumerate(results["ids"]):
                    memories.append(
                        {
                            "id": memory_id,
                            "content": results["documents"][i],
                            "metadata": results["metadatas"][i],
                        }
                    )
            export[memory_type.value] = memories
        return export

    def import_memories(self, data: dict) -> int:
        """Import memories from an export dict. Returns count imported."""
        count = 0
        for memory_type_str, memories in data.items():
            memory_type = MemoryType(memory_type_str)
            for mem_data in memories:
                memory = Memory.from_storage_dict(
                    mem_data["metadata"], mem_data["content"]
                )
                self.store(memory)
                count += 1
        return count
