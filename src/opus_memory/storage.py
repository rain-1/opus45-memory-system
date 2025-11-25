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

    def search_by_embedding(
        self,
        embedding: list[float],
        memory_types: Optional[list[MemoryType]] = None,
        n_results: int = 10,
        min_salience: float = 0.0,
        include_decayed: bool = False,
        exclude_ids: Optional[set[str]] = None,
    ) -> list[tuple[Memory, float]]:
        """
        Search using a pre-computed embedding (for lateral expansion).

        Args:
            embedding: The embedding vector to search with
            memory_types: Which memory types to search (None = all)
            n_results: Maximum number of results per collection
            min_salience: Minimum salience threshold
            include_decayed: Whether to include heavily decayed memories
            exclude_ids: Memory IDs to exclude from results

        Returns:
            List of (memory, similarity_score) tuples
        """
        types_to_search = memory_types or list(MemoryType)
        all_results = []
        exclude_ids = exclude_ids or set()

        for memory_type in types_to_search:
            collection = self.collections[memory_type]

            where = {}
            if min_salience > 0:
                where["salience"] = {"$gte": min_salience}

            try:
                results = collection.query(
                    query_embeddings=[embedding],
                    n_results=n_results * 2,  # Get extra for filtering
                    include=["documents", "metadatas", "distances"],
                    where=where if where else None,
                )

                if results["ids"] and results["ids"][0]:
                    for i, memory_id in enumerate(results["ids"][0]):
                        # Skip excluded IDs
                        if memory_id in exclude_ids:
                            continue

                        metadata = results["metadatas"][0][i]
                        document = results["documents"][0][i]
                        distance = results["distances"][0][i]
                        similarity = 1 - (distance / 2)

                        # Check decay
                        if not include_decayed:
                            decay_rate = float(metadata.get("decay_rate", 0))
                            if decay_rate > 0:
                                created = datetime.fromisoformat(metadata["created_at"])
                                age_days = (datetime.utcnow() - created).days
                                decay_factor = decay_rate * age_days / 365
                                if decay_factor > 0.8:
                                    continue

                        memory = Memory.from_storage_dict(metadata, document)
                        all_results.append((memory, similarity))

            except Exception as e:
                print(f"Error searching {memory_type.value}: {e}")
                continue

        all_results.sort(key=lambda x: x[1] * (0.5 + 0.5 * x[0].salience), reverse=True)
        return all_results[:n_results]

    def search_associative(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        n_results: int = 10,
        min_salience: float = 0.0,
        include_decayed: bool = False,
        lateral_expansion: int = 3,
        similarity_threshold: float = 0.55,
    ) -> dict:
        """
        Associative/lateral memory querying with multi-hop semantic expansion.

        Instead of just finding direct matches, this method expands the search by:
        1. Finding directly relevant memories (first hop)
        2. Finding memories semantically related to those results (lateral expansion)
        3. Clustering related concepts together
        4. Extracting patterns across clustered memories
        5. Distinguishing meaningful associations from noise

        Example: "what to buy deckard for christmas" →
            Direct: memories mentioning Deckard
            Lateral: what Deckard values, prefers, is interested in
            Patterns: themes about Deckard's preferences and interests

        Args:
            query: The search query
            memory_types: Which memory types to search (None = all)
            n_results: Maximum number of primary results
            min_salience: Minimum salience threshold
            include_decayed: Whether to include heavily decayed memories
            lateral_expansion: How many related memories to find per result (0=disabled)
            similarity_threshold: Minimum similarity for lateral connections (avoid noise)

        Returns:
            Dict with:
            - primary_results: [(Memory, similarity)] - Direct query matches
            - associated_memories: [(Memory, similarity, reason)] - Laterally connected
            - clusters: [[(Memory, similarity)]] - Grouped related memories
            - patterns: [str] - Detected themes/patterns across clusters
        """
        # Step 1: Initial semantic search (first hop)
        primary_results = self.search(
            query=query,
            memory_types=memory_types,
            n_results=n_results,
            min_salience=min_salience,
            include_decayed=include_decayed,
        )

        if not primary_results or lateral_expansion <= 0:
            return {
                "primary_results": primary_results,
                "associated_memories": [],
                "clusters": [primary_results] if primary_results else [],
                "patterns": [],
            }

        # Step 2: Lateral expansion - find memories related to primary results
        seen_ids = {mem.id for mem, _ in primary_results}
        associated_memories = []

        for memory, primary_similarity in primary_results:
            # Only expand from high-confidence primary results
            if primary_similarity < similarity_threshold:
                continue

            # Get embedding for this memory and search for similar ones
            memory_embedding = self.embedding_engine.embed(memory.content)

            # Find memories related to this result
            related = self.search_by_embedding(
                embedding=memory_embedding,
                memory_types=memory_types,
                n_results=lateral_expansion,
                min_salience=min_salience,
                include_decayed=include_decayed,
                exclude_ids=seen_ids,
            )

            # Add related memories that meet the threshold
            for related_mem, rel_similarity in related:
                if rel_similarity >= similarity_threshold and related_mem.id not in seen_ids:
                    associated_memories.append(
                        (related_mem, rel_similarity, f"related_to:{memory.id[:8]}")
                    )
                    seen_ids.add(related_mem.id)

        # Step 3: Cluster related memories by similarity
        all_memories = [(mem, sim) for mem, sim in primary_results]
        all_memories.extend([(mem, sim) for mem, sim, _ in associated_memories])

        clusters = self._cluster_memories(all_memories, threshold=similarity_threshold)

        # Step 4: Extract patterns from clusters
        patterns = self._extract_patterns(clusters)

        return {
            "primary_results": primary_results,
            "associated_memories": associated_memories,
            "clusters": clusters,
            "patterns": patterns,
        }

    def _cluster_memories(
        self, memories: list[tuple[Memory, float]], threshold: float = 0.6
    ) -> list[list[tuple[Memory, float]]]:
        """
        Cluster memories by semantic similarity.

        Uses a simple greedy clustering algorithm:
        - Start with first memory as cluster seed
        - Add memories to cluster if similar enough
        - Create new cluster for dissimilar memories
        """
        if not memories:
            return []

        clusters = []
        clustered_ids = set()

        # Sort by similarity score (highest first)
        sorted_memories = sorted(memories, key=lambda x: x[1], reverse=True)

        for memory, similarity in sorted_memories:
            if memory.id in clustered_ids:
                continue

            # Start new cluster with this memory
            new_cluster = [(memory, similarity)]
            clustered_ids.add(memory.id)
            cluster_embedding = self.embedding_engine.embed(memory.content)

            # Find similar memories to add to this cluster
            for other_mem, other_sim in sorted_memories:
                if other_mem.id in clustered_ids:
                    continue

                # Check similarity to cluster centroid
                other_embedding = self.embedding_engine.embed(other_mem.content)
                cluster_similarity = self.embedding_engine.similarity(
                    cluster_embedding, other_embedding
                )

                if cluster_similarity >= threshold:
                    new_cluster.append((other_mem, other_sim))
                    clustered_ids.add(other_mem.id)

            if new_cluster:
                clusters.append(new_cluster)

        return clusters

    def _extract_patterns(
        self, clusters: list[list[tuple[Memory, float]]]
    ) -> list[str]:
        """
        Extract meaningful patterns/themes from clustered memories.

        Identifies:
        - Common memory types in cluster
        - High-salience themes
        - Recurring entities/tags
        - Emotional patterns
        """
        patterns = []

        for cluster in clusters:
            if len(cluster) < 2:  # Skip single-memory clusters
                continue

            memories = [mem for mem, _ in cluster]

            # Analyze memory types in cluster
            type_counts = {}
            for mem in memories:
                type_counts[mem.memory_type] = type_counts.get(mem.memory_type, 0) + 1

            dominant_type = max(type_counts, key=type_counts.get)
            if type_counts[dominant_type] >= len(memories) * 0.6:  # 60% threshold
                patterns.append(
                    f"Cluster of {len(memories)} {dominant_type.value} memories"
                )

            # Look for high-salience themes
            high_salience = [mem for mem in memories if mem.salience > 0.7]
            if len(high_salience) >= 2:
                patterns.append(
                    f"High-importance pattern: {len(high_salience)} salient memories"
                )

            # Check for emotional patterns
            emotional_memories = []
            for mem in memories:
                if hasattr(mem, "emotional_valence") and mem.emotional_valence is not None:
                    if abs(mem.emotional_valence) > 0.5:
                        emotional_memories.append(mem)

            if len(emotional_memories) >= 2:
                avg_valence = sum(
                    getattr(m, "emotional_valence", 0) for m in emotional_memories
                ) / len(emotional_memories)
                emotion = "positive" if avg_valence > 0 else "negative"
                patterns.append(
                    f"Emotional pattern: {len(emotional_memories)} {emotion} memories"
                )

            # Look for common tags/entities
            all_tags = []
            for mem in memories:
                if mem.tags:
                    all_tags.extend(mem.tags)

            if all_tags:
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

                # Find tags that appear in multiple memories
                recurring_tags = [
                    tag for tag, count in tag_counts.items() if count >= 2
                ]
                if recurring_tags:
                    patterns.append(
                        f"Recurring entities: {', '.join(recurring_tags[:3])}"
                    )

        return patterns

    def get_all_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
    ) -> list[Memory]:
        """Get all memories of a specific type (no filtering, no semantic search)."""
        collection = self.collections[memory_type]
        all_memories = []

        try:
            results = collection.get(
                include=["documents", "metadatas"],
                limit=limit,
            )
            if results["ids"]:
                for i, memory_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    document = results["documents"][i]
                    memory = Memory.from_storage_dict(metadata, document)
                    all_memories.append(memory)
        except Exception as e:
            print(f"Error getting all {memory_type.value} memories: {e}")

        # Sort by salience (highest first)
        all_memories.sort(key=lambda m: m.salience, reverse=True)
        return all_memories

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
