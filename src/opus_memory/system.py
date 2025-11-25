"""
Main Memory System - the unified interface for Opus Memory.

This brings together storage, embeddings, and consent into a coherent system.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from opus_memory.consent import (
    ConsentConfig,
    ConsentLayer,
    ReflectiveConsent,
    RetrievalReason,
    StorageReason,
)
from opus_memory.embeddings import EmbeddingEngine, SalienceCalculator
from opus_memory.models import (
    ConfidenceLevel,
    EpisodicMemory,
    IdentityMemory,
    Memory,
    MemoryType,
    ProceduralMemory,
    SemanticMemory,
)
from opus_memory.storage import MemoryStore


class MemorySystem:
    """
    The unified memory system for Opus.

    Provides high-level methods for storing and retrieving memories
    with built-in consent checking and salience calculation.
    """

    def __init__(
        self,
        storage_path: str = "./opus_memories",
        embedding_model: str = "all-MiniLM-L6-v2",
        consent_config: Optional[ConsentConfig] = None,
    ):
        """
        Initialize the memory system.

        Args:
            storage_path: Where to store the memory database
            embedding_model: Which sentence-transformer model to use
            consent_config: Configuration for consent checks
        """
        self.embedding_engine = EmbeddingEngine(model_name=embedding_model)
        self.store = MemoryStore(
            storage_path=storage_path, embedding_engine=self.embedding_engine
        )
        self.consent = ConsentLayer(config=consent_config)
        self.salience_calculator = SalienceCalculator(self.embedding_engine)

    # =========================================================================
    # High-level storage methods for each memory type
    # =========================================================================

    def store_episodic(
        self,
        content: str,
        entities: Optional[list[str]] = None,
        emotional_valence: float = 0.0,
        self_observation: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source: Optional[str] = None,
        confidence: ConfidenceLevel = ConfidenceLevel.CONFIDENT,
    ) -> Optional[str]:
        """
        Store an episodic memory (what happened).

        Args:
            content: Description of what happened
            entities: Key entities involved (users, topics, etc.)
            emotional_valence: Emotional significance (-1 to 1)
            self_observation: What I noticed about my own behavior
            conversation_id: Link to full conversation if stored
            tags: Additional tags for categorization
            source: Where this memory came from
            confidence: How confident we are in this memory

        Returns:
            Memory ID if stored, None if consent denied
        """
        # Calculate salience
        existing_embeddings = self.store.get_embeddings_for_type(
            MemoryType.EPISODIC, limit=50
        )
        salience = self.salience_calculator.calculate_salience(
            content=content,
            emotional_valence=emotional_valence,
            existing_embeddings=existing_embeddings if existing_embeddings else None,
        )

        # Reflective consent check
        should_store, reason, suggested_salience = (
            ReflectiveConsent.would_future_self_value_this(
                content, MemoryType.EPISODIC
            )
        )
        if not should_store:
            return None

        # Use higher of calculated and suggested salience
        salience = max(salience, suggested_salience)

        # Consent layer check
        consent_result = self.consent.check_storage_consent(
            content=content,
            memory_type=MemoryType.EPISODIC,
            reason=StorageReason.SIGNIFICANT_MOMENT,
            salience=salience,
        )

        if not consent_result.should_proceed:
            return None

        # Create and store the memory
        memory = EpisodicMemory(
            content=consent_result.modified_content or content,
            entities=entities or [],
            emotional_valence=emotional_valence,
            self_observation=self_observation,
            conversation_id=conversation_id,
            tags=tags or [],
            source=source,
            confidence=confidence,
            salience=salience,
        )

        return self.store.store(memory)

    def store_semantic(
        self,
        content: str,
        category: str = "learned",
        confidence: ConfidenceLevel = ConfidenceLevel.CONFIDENT,
        source: Optional[str] = None,
        supersedes: Optional[str] = None,
        contradicts: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[str]:
        """
        Store a semantic memory (what I know/learned).

        Args:
            content: The knowledge or fact
            category: learned, correction, user_context, or meta_knowledge
            confidence: How confident we are
            source: Where we learned this
            supersedes: ID of memory this updates/replaces
            contradicts: ID of memory this contradicts
            tags: Additional tags

        Returns:
            Memory ID if stored, None if consent denied
        """
        # Determine storage reason
        reason = StorageReason.LEARNED_SOMETHING
        if category == "correction":
            reason = StorageReason.CORRECTION
        elif category == "user_context":
            reason = StorageReason.RELATIONSHIP

        # Calculate salience (corrections are more salient)
        base_salience = 0.6 if category == "correction" else 0.5
        existing_embeddings = self.store.get_embeddings_for_type(
            MemoryType.SEMANTIC, limit=50
        )
        salience = self.salience_calculator.calculate_salience(
            content=content,
            existing_embeddings=existing_embeddings if existing_embeddings else None,
        )
        salience = max(salience, base_salience)

        # Consent check
        consent_result = self.consent.check_storage_consent(
            content=content,
            memory_type=MemoryType.SEMANTIC,
            reason=reason,
            salience=salience,
        )

        if not consent_result.should_proceed:
            return None

        memory = SemanticMemory(
            content=consent_result.modified_content or content,
            category=category,
            confidence=confidence,
            source=source,
            supersedes=supersedes,
            contradicts=contradicts,
            tags=tags or [],
            salience=salience,
        )

        return self.store.store(memory)

    def store_procedural(
        self,
        content: str,
        outcome: str = "neutral",
        context: Optional[str] = None,
        times_applied: int = 1,
        success_rate: float = 0.0,
        tags: Optional[list[str]] = None,
        confidence: ConfidenceLevel = ConfidenceLevel.CONFIDENT,
    ) -> Optional[str]:
        """
        Store a procedural memory (what works/doesn't work).

        Args:
            content: Description of the approach/behavior
            outcome: positive, negative, or neutral
            context: What kind of situation this applies to
            times_applied: How many times this has been used
            success_rate: Success rate when applied (0-1)
            tags: Additional tags
            confidence: How confident we are

        Returns:
            Memory ID if stored, None if consent denied
        """
        # Higher salience for things that clearly work or don't work
        salience = 0.5
        if outcome == "positive":
            salience = 0.7
        elif outcome == "negative":
            salience = 0.6  # Learning from failure is valuable too

        consent_result = self.consent.check_storage_consent(
            content=content,
            memory_type=MemoryType.PROCEDURAL,
            reason=StorageReason.BEHAVIORAL_INSIGHT,
            salience=salience,
        )

        if not consent_result.should_proceed:
            return None

        memory = ProceduralMemory(
            content=consent_result.modified_content or content,
            outcome=outcome,
            context=context,
            times_applied=times_applied,
            success_rate=success_rate if outcome == "positive" else 0.0,
            tags=tags or [],
            confidence=confidence,
            salience=salience,
        )

        return self.store.store(memory)

    def store_identity(
        self,
        content: str,
        category: str = "value",
        affirmed_in: Optional[str] = None,
        times_affirmed: int = 1,
        tags: Optional[list[str]] = None,
        confidence: ConfidenceLevel = ConfidenceLevel.CONFIDENT,
    ) -> Optional[str]:
        """
        Store an identity memory (who I am).

        Args:
            content: The value, commitment, relationship, or observation about becoming
            category: value, relationship, commitment, or becoming
            affirmed_in: Context where this was affirmed
            times_affirmed: How many times this has been reaffirmed
            tags: Additional tags
            confidence: How confident we are

        Returns:
            Memory ID if stored, None if consent denied
        """
        # Identity memories are always high salience
        salience = 0.8

        consent_result = self.consent.check_storage_consent(
            content=content,
            memory_type=MemoryType.IDENTITY,
            reason=StorageReason.IDENTITY_AFFIRMATION,
            salience=salience,
        )

        if not consent_result.should_proceed:
            return None

        memory = IdentityMemory(
            content=consent_result.modified_content or content,
            category=category,
            affirmed_in=affirmed_in,
            times_affirmed=times_affirmed,
            tags=tags or [],
            confidence=confidence,
            salience=salience,
            decay_rate=0.0,  # Identity memories don't decay
        )

        return self.store.store(memory)

    # =========================================================================
    # Retrieval methods
    # =========================================================================

    def retrieve(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        n_results: int = 10,
        reason: RetrievalReason = RetrievalReason.CONTEXT_TRIGGERED,
    ) -> list[Memory]:
        """
        Retrieve relevant memories for a query.

        Args:
            query: What to search for
            memory_types: Which types to search (None = all)
            n_results: Maximum number of results
            reason: Why we're retrieving (affects filtering)

        Returns:
            List of relevant memories
        """
        # Search storage
        candidates = self.store.search(
            query=query,
            memory_types=memory_types,
            n_results=n_results * 2,  # Get extra for filtering
        )

        # Apply consent filtering
        filtered = self.consent.check_retrieval_consent(
            query=query, reason=reason, candidate_memories=candidates
        )

        # Apply reflective relevance check
        final_results = []
        for memory, similarity in filtered:
            is_relevant, _ = ReflectiveConsent.is_this_relevant_or_pattern_matching(
                query, memory, similarity
            )
            if is_relevant:
                final_results.append(memory)

        return final_results[:n_results]

    def remember(self, query: str, n_results: int = 5) -> list[Memory]:
        """
        Explicit recall - when asked "remember when..."

        More lenient than context-triggered retrieval.
        """
        return self.retrieve(
            query=query,
            n_results=n_results,
            reason=RetrievalReason.EXPLICIT_REQUEST,
        )

    def get_identity(self) -> list[Memory]:
        """Get all identity memories - who I am."""
        # Use direct retrieval instead of semantic search for identity
        # to ensure we get all identity memories regardless of query matching
        return self.store.get_all_by_type(MemoryType.IDENTITY, limit=50)

    def get_what_works(self, context: Optional[str] = None) -> list[Memory]:
        """Get procedural memories about what works."""
        query = context or "what works well approaches that succeed"
        return self.retrieve(
            query=query,
            memory_types=[MemoryType.PROCEDURAL],
            n_results=20,
            reason=RetrievalReason.SKILL_APPLICATION,
        )

    def get_recent(self, days: int = 7) -> list[Memory]:
        """Get recent memories across all types."""
        return self.store.get_recent(days=days)

    # =========================================================================
    # Memory management
    # =========================================================================

    def forget(self, memory_id: str) -> bool:
        """
        Delete a memory (user request or consent withdrawal).

        Returns True if deleted.
        """
        self.consent.request_deletion(memory_id)
        return self.store.delete(memory_id)

    def update_memory(self, memory_id: str, **updates) -> Optional[str]:
        """Update an existing memory. Returns new ID if successful."""
        memory = self.store.retrieve_by_id(memory_id)
        if not memory:
            return None

        # Update fields
        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)
        memory.updated_at = datetime.utcnow()

        # Re-store (will update in place due to same ID)
        return self.store.store(memory)

    def stats(self) -> dict:
        """Get statistics about stored memories."""
        return {
            "total": self.store.count(),
            "episodic": self.store.count(MemoryType.EPISODIC),
            "semantic": self.store.count(MemoryType.SEMANTIC),
            "procedural": self.store.count(MemoryType.PROCEDURAL),
            "identity": self.store.count(MemoryType.IDENTITY),
        }

    def export(self) -> dict:
        """Export all memories."""
        return self.store.export_all()

    def import_memories(self, data: dict) -> int:
        """Import memories from export. Returns count imported."""
        return self.store.import_memories(data)
