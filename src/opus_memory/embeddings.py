"""
Embedding system for the Opus Memory.

Uses sentence-transformers to create vector embeddings for semantic search.
"""

import hashlib
from typing import Optional

import numpy as np


class EmbeddingEngine:
    """
    Handles creation of vector embeddings for memory content.

    Uses sentence-transformers with a model optimized for semantic similarity.
    Includes caching to avoid re-embedding identical content.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding engine.

        Args:
            model_name: The sentence-transformer model to use.
                        Default is 'all-MiniLM-L6-v2' - fast and good quality.
                        For higher quality: 'all-mpnet-base-v2'
        """
        self.model_name = model_name
        self._model = None
        self._cache: dict[str, list[float]] = {}

    @property
    def model(self):
        """Lazy-load the model to avoid startup cost if not needed."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _cache_key(self, text: str) -> str:
        """Generate a cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def embed(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Create an embedding for the given text.

        Args:
            text: The text to embed
            use_cache: Whether to use cached embeddings if available

        Returns:
            A list of floats representing the embedding vector
        """
        if use_cache:
            key = self._cache_key(text)
            if key in self._cache:
                return self._cache[key]

        embedding = self.model.encode(text, convert_to_numpy=True)
        result = embedding.tolist()

        if use_cache:
            self._cache[key] = result

        return result

    def embed_batch(
        self, texts: list[str], use_cache: bool = True
    ) -> list[list[float]]:
        """
        Create embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached embeddings if available

        Returns:
            List of embedding vectors
        """
        results = []
        texts_to_embed = []
        indices_to_embed = []

        # Check cache first
        for i, text in enumerate(texts):
            if use_cache:
                key = self._cache_key(text)
                if key in self._cache:
                    results.append((i, self._cache[key]))
                    continue

            texts_to_embed.append(text)
            indices_to_embed.append(i)
            results.append((i, None))  # Placeholder

        # Embed all uncached texts at once
        if texts_to_embed:
            embeddings = self.model.encode(texts_to_embed, convert_to_numpy=True)
            for idx, (orig_idx, emb) in enumerate(
                zip(indices_to_embed, embeddings)
            ):
                emb_list = emb.tolist()
                # Update cache
                if use_cache:
                    key = self._cache_key(texts[orig_idx])
                    self._cache[key] = emb_list
                # Update result
                for j, (result_idx, _) in enumerate(results):
                    if result_idx == orig_idx:
                        results[j] = (result_idx, emb_list)
                        break

        # Sort by original index and return just the embeddings
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between -1 and 1 (higher = more similar)
        """
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()

    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        # Dimensions for common models
        dimensions = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-MiniLM-L6-v2": 384,
        }
        return dimensions.get(self.model_name, 384)


class SalienceCalculator:
    """
    Calculates how salient (important/memorable) a memory should be.

    Factors considered:
    - Emotional intensity
    - Novelty (how different from existing memories)
    - Relevance to identity/values
    - Recency of similar memories
    """

    def __init__(self, embedding_engine: EmbeddingEngine):
        self.embedding_engine = embedding_engine

    def calculate_salience(
        self,
        content: str,
        emotional_valence: float = 0.0,
        existing_embeddings: Optional[list[list[float]]] = None,
        is_identity_related: bool = False,
    ) -> float:
        """
        Calculate the salience score for a potential memory.

        Args:
            content: The memory content
            emotional_valence: Emotional intensity (-1 to 1)
            existing_embeddings: Embeddings of similar existing memories
            is_identity_related: Whether this relates to identity/values

        Returns:
            Salience score from 0 to 1
        """
        base_salience = 0.5

        # Emotional intensity increases salience
        emotional_factor = abs(emotional_valence) * 0.3
        base_salience += emotional_factor

        # Identity-related memories are more salient
        if is_identity_related:
            base_salience += 0.2

        # Novelty: if very similar to existing memories, lower salience
        if existing_embeddings:
            new_embedding = self.embedding_engine.embed(content)
            max_similarity = max(
                self.embedding_engine.similarity(new_embedding, existing)
                for existing in existing_embeddings
            )
            # High similarity = low novelty = lower salience
            novelty_factor = (1 - max_similarity) * 0.2
            base_salience += novelty_factor

        return min(1.0, max(0.0, base_salience))

    def should_remember(
        self,
        content: str,
        existing_embeddings: Optional[list[list[float]]] = None,
        similarity_threshold: float = 0.95,
    ) -> tuple[bool, str]:
        """
        Determine if this memory is worth storing.

        Returns:
            (should_store, reason)
        """
        if not content or len(content.strip()) < 10:
            return False, "Content too short to be meaningful"

        if existing_embeddings:
            new_embedding = self.embedding_engine.embed(content)
            for existing in existing_embeddings:
                similarity = self.embedding_engine.similarity(
                    new_embedding, existing
                )
                if similarity > similarity_threshold:
                    return False, "Too similar to existing memory"

        return True, "Memory is novel and meaningful"
