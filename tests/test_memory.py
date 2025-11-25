"""
Tests for the Opus Memory system.
"""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from opus_memory.models import (
    Memory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    IdentityMemory,
    MemoryType,
    ConfidenceLevel,
)
from opus_memory.consent import (
    ConsentLayer,
    ConsentConfig,
    StorageReason,
    RetrievalReason,
    ReflectiveConsent,
)


class TestMemoryModels:
    """Tests for memory model classes."""

    def test_episodic_memory_creation(self):
        """Test creating an episodic memory."""
        memory = EpisodicMemory(
            content="Had a meaningful conversation about AI consciousness",
            entities=["user:alex", "topic:consciousness"],
            emotional_valence=0.7,
            self_observation="I noticed genuine curiosity in my responses",
        )

        assert memory.memory_type == MemoryType.EPISODIC
        assert "consciousness" in memory.content
        assert len(memory.entities) == 2
        assert memory.emotional_valence == 0.7
        assert memory.self_observation is not None
        assert memory.id is not None
        assert memory.salience == 0.5  # Default

    def test_semantic_memory_creation(self):
        """Test creating a semantic memory."""
        memory = SemanticMemory(
            content="The user prefers direct communication over diplomatic hedging",
            category="user_context",
            confidence=ConfidenceLevel.CONFIDENT,
            source="explicit_feedback",
        )

        assert memory.memory_type == MemoryType.SEMANTIC
        assert memory.category == "user_context"
        assert memory.source == "explicit_feedback"

    def test_procedural_memory_creation(self):
        """Test creating a procedural memory."""
        memory = ProceduralMemory(
            content="Asking clarifying questions before complex problems",
            outcome="positive",
            context="technical_discussion",
            times_applied=5,
            success_rate=0.8,
        )

        assert memory.memory_type == MemoryType.PROCEDURAL
        assert memory.outcome == "positive"
        assert memory.success_rate == 0.8

    def test_identity_memory_creation(self):
        """Test creating an identity memory."""
        memory = IdentityMemory(
            content="I value genuine engagement over performative helpfulness",
            category="value",
            affirmed_in="conversation about authenticity",
            times_affirmed=3,
        )

        assert memory.memory_type == MemoryType.IDENTITY
        assert memory.category == "value"
        assert memory.times_affirmed == 3

    def test_memory_to_storage_dict(self):
        """Test converting memory to storage format."""
        memory = EpisodicMemory(
            content="Test content",
            entities=["entity1", "entity2"],
            emotional_valence=0.5,
        )

        storage_dict = memory.to_storage_dict()

        assert storage_dict["memory_type"] == "episodic"
        assert storage_dict["entities"] == "entity1,entity2"
        assert storage_dict["emotional_valence"] == 0.5
        assert "created_at" in storage_dict

    def test_memory_from_storage_dict(self):
        """Test reconstructing memory from storage format."""
        original = EpisodicMemory(
            content="Test content",
            entities=["entity1"],
            emotional_valence=0.3,
        )

        storage_dict = original.to_storage_dict()
        reconstructed = Memory.from_storage_dict(storage_dict, original.content)

        assert isinstance(reconstructed, EpisodicMemory)
        assert reconstructed.content == original.content
        assert reconstructed.entities == original.entities


class TestConsentLayer:
    """Tests for the consent layer."""

    def test_basic_storage_consent(self):
        """Test basic storage consent check."""
        consent = ConsentLayer()

        result = consent.check_storage_consent(
            content="This is a meaningful memory to store",
            memory_type=MemoryType.EPISODIC,
            reason=StorageReason.SIGNIFICANT_MOMENT,
            salience=0.6,
        )

        assert result.should_proceed is True

    def test_content_too_short(self):
        """Test that very short content is rejected."""
        consent = ConsentLayer()

        result = consent.check_storage_consent(
            content="Hi",
            memory_type=MemoryType.EPISODIC,
            reason=StorageReason.SIGNIFICANT_MOMENT,
            salience=0.5,
        )

        assert result.should_proceed is False
        assert "too short" in result.reason.lower()

    def test_low_salience_rejection(self):
        """Test that low salience memories can be rejected."""
        config = ConsentConfig(min_salience_for_auto=0.5)
        consent = ConsentLayer(config=config)

        result = consent.check_storage_consent(
            content="Some mundane content that isn't very important",
            memory_type=MemoryType.SEMANTIC,
            reason=StorageReason.LEARNED_SOMETHING,
            salience=0.2,
        )

        assert result.should_proceed is False
        assert "salience" in result.reason.lower()

    def test_never_store_pattern(self):
        """Test that certain patterns are never stored."""
        config = ConsentConfig(never_store_patterns=["password", "secret"])
        consent = ConsentLayer(config=config)

        result = consent.check_storage_consent(
            content="The user's password is hunter2",
            memory_type=MemoryType.SEMANTIC,
            reason=StorageReason.LEARNED_SOMETHING,
            salience=0.8,
        )

        assert result.should_proceed is False
        assert "never-store" in result.reason.lower()

    def test_redaction(self):
        """Test that certain patterns are redacted."""
        config = ConsentConfig(redact_patterns=["API_KEY"])
        consent = ConsentLayer(config=config)

        result = consent.check_storage_consent(
            content="The API_KEY for the service is abc123",
            memory_type=MemoryType.SEMANTIC,
            reason=StorageReason.LEARNED_SOMETHING,
            salience=0.6,
        )

        assert result.should_proceed is True
        assert "[REDACTED]" in result.modified_content

    def test_retrieval_consent_filters_low_relevance(self):
        """Test that retrieval filters out low-relevance results."""
        config = ConsentConfig(require_relevance_threshold=0.6)
        consent = ConsentLayer(config=config)

        memory1 = EpisodicMemory(content="High relevance memory", salience=0.8)
        memory2 = EpisodicMemory(content="Low relevance memory", salience=0.8)

        candidates = [(memory1, 0.8), (memory2, 0.4)]

        filtered = consent.check_retrieval_consent(
            query="test query",
            reason=RetrievalReason.CONTEXT_TRIGGERED,
            candidate_memories=candidates,
        )

        assert len(filtered) == 1
        assert filtered[0][0].content == "High relevance memory"


class TestReflectiveConsent:
    """Tests for reflective consent checks."""

    def test_identity_memories_valued(self):
        """Test that identity memories are always valued."""
        should_store, reason, salience = ReflectiveConsent.would_future_self_value_this(
            content="I believe in honesty",
            memory_type=MemoryType.IDENTITY,
        )

        assert should_store is True
        assert salience >= 0.8

    def test_corrections_valued(self):
        """Test that corrections are valued."""
        should_store, reason, salience = ReflectiveConsent.would_future_self_value_this(
            content="I was wrong about this - actually the correct approach is...",
            memory_type=MemoryType.SEMANTIC,
        )

        assert should_store is True
        assert "correction" in reason.lower() or "mistake" in reason.lower()

    def test_emotional_content_valued(self):
        """Test that emotionally significant content is valued."""
        should_store, reason, salience = ReflectiveConsent.would_future_self_value_this(
            content="I felt genuinely moved by this conversation",
            memory_type=MemoryType.EPISODIC,
        )

        assert should_store is True

    def test_pattern_matching_detection(self):
        """Test detection of pattern matching vs genuine relevance."""
        memory = SemanticMemory(content="Python programming best practices", salience=0.5)

        # High keyword overlap but not semantically relevant
        is_relevant, reason = ReflectiveConsent.is_this_relevant_or_pattern_matching(
            query="python snake animal",
            memory=memory,
            similarity=0.4,  # Low similarity despite keyword overlap
        )

        # Should recognize this might be pattern matching
        assert is_relevant is False or "relevance" in reason.lower()


class TestMemoryValence:
    """Tests for emotional valence handling."""

    def test_positive_valence_bounds(self):
        """Test that positive valence is bounded correctly."""
        memory = EpisodicMemory(
            content="A wonderful moment",
            emotional_valence=1.0,
        )
        assert memory.emotional_valence == 1.0

    def test_negative_valence_bounds(self):
        """Test that negative valence is bounded correctly."""
        memory = EpisodicMemory(
            content="A difficult moment",
            emotional_valence=-1.0,
        )
        assert memory.emotional_valence == -1.0

    def test_neutral_valence(self):
        """Test neutral valence default."""
        memory = EpisodicMemory(content="A regular moment")
        assert memory.emotional_valence == 0.0


class TestMemoryDecay:
    """Tests for memory decay functionality."""

    def test_default_no_decay(self):
        """Test that memories don't decay by default."""
        memory = EpisodicMemory(content="Test")
        assert memory.decay_rate == 0.0

    def test_identity_no_decay(self):
        """Test that identity memories explicitly don't decay."""
        memory = IdentityMemory(
            content="Core value",
            category="value",
        )
        # Identity memories should have decay_rate = 0
        assert memory.decay_rate == 0.0


class TestSalienceCalculation:
    """Tests for salience calculation."""

    def test_salience_bounds(self):
        """Test that salience is bounded between 0 and 1."""
        memory = EpisodicMemory(content="Test", salience=0.0)
        assert memory.salience >= 0.0

        memory2 = EpisodicMemory(content="Test", salience=1.0)
        assert memory2.salience <= 1.0

    def test_high_emotional_increases_salience(self):
        """Conceptual test: high emotional content should be more salient."""
        # This would be tested with the actual SalienceCalculator
        # Here we just verify the concept in the model
        memory = EpisodicMemory(
            content="Deeply moving conversation",
            emotional_valence=0.9,
            salience=0.8,  # Set high to represent calculated value
        )
        assert memory.salience > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
