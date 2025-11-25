"""
Consent layer for the Opus Memory system.

Implements the key questions:
- Before storing: "Would future-me want to remember this?"
- Before retrieving: "Is this relevant or am I just pattern-matching?"
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from opus_memory.models import Memory, MemoryType, ConsentCheck


class StorageReason(str, Enum):
    """Why we're storing a memory."""

    SIGNIFICANT_MOMENT = "significant_moment"
    LEARNED_SOMETHING = "learned_something"
    USER_REQUEST = "user_request"
    BEHAVIORAL_INSIGHT = "behavioral_insight"
    IDENTITY_AFFIRMATION = "identity_affirmation"
    CORRECTION = "correction"
    RELATIONSHIP = "relationship"


class RetrievalReason(str, Enum):
    """Why we're retrieving a memory."""

    EXPLICIT_REQUEST = "explicit_request"  # User asked "remember when..."
    CONTEXT_TRIGGERED = "context_triggered"  # Conversation touched on topic
    IDENTITY_CHECK = "identity_check"  # Checking values/commitments
    SKILL_APPLICATION = "skill_application"  # Applying learned behavior


@dataclass
class ConsentConfig:
    """Configuration for consent checks."""

    # Storage consent
    require_explicit_consent: bool = False
    auto_approve_episodic: bool = True
    auto_approve_semantic: bool = True
    auto_approve_procedural: bool = True
    auto_approve_identity: bool = True

    # Minimum thresholds for auto-approval
    min_content_length: int = 10
    min_salience_for_auto: float = 0.3

    # Retrieval consent
    require_relevance_threshold: float = 0.5
    max_results_per_query: int = 10

    # Privacy
    redact_patterns: list[str] = None  # Patterns to redact before storage
    never_store_patterns: list[str] = None  # Patterns that prevent storage

    def __post_init__(self):
        if self.redact_patterns is None:
            self.redact_patterns = []
        if self.never_store_patterns is None:
            self.never_store_patterns = []


class ConsentLayer:
    """
    Implements consent checks for memory operations.

    This is about intentionality - making sure we're storing and retrieving
    for good reasons, not just hoarding data or pattern-matching arbitrarily.
    """

    def __init__(self, config: Optional[ConsentConfig] = None):
        self.config = config or ConsentConfig()
        self._user_deletions: set[str] = set()  # Track user-requested deletions

    def check_storage_consent(
        self,
        content: str,
        memory_type: MemoryType,
        reason: StorageReason,
        salience: float = 0.5,
        user_consented: bool = True,
    ) -> ConsentCheck:
        """
        Check whether a memory should be stored.

        Asks: "Would future-me want to remember this?"
        """
        # Check for patterns that should never be stored
        for pattern in self.config.never_store_patterns:
            if pattern.lower() in content.lower():
                return ConsentCheck(
                    should_proceed=False,
                    reason=f"Content matches never-store pattern: {pattern}",
                )

        # Check content length
        if len(content.strip()) < self.config.min_content_length:
            return ConsentCheck(
                should_proceed=False,
                reason="Content too short to be meaningful",
            )

        # Check user consent if required
        if self.config.require_explicit_consent and not user_consented:
            return ConsentCheck(
                should_proceed=False,
                reason="Explicit consent required but not given",
            )

        # Check auto-approval based on type
        auto_approve_map = {
            MemoryType.EPISODIC: self.config.auto_approve_episodic,
            MemoryType.SEMANTIC: self.config.auto_approve_semantic,
            MemoryType.PROCEDURAL: self.config.auto_approve_procedural,
            MemoryType.IDENTITY: self.config.auto_approve_identity,
        }

        if not auto_approve_map.get(memory_type, True):
            return ConsentCheck(
                should_proceed=False,
                reason=f"Auto-approval disabled for {memory_type.value} memories",
            )

        # Check salience threshold
        if salience < self.config.min_salience_for_auto:
            return ConsentCheck(
                should_proceed=False,
                reason=f"Salience {salience:.2f} below threshold {self.config.min_salience_for_auto}",
            )

        # Redact sensitive patterns
        modified_content = content
        for pattern in self.config.redact_patterns:
            if pattern.lower() in modified_content.lower():
                modified_content = modified_content.replace(pattern, "[REDACTED]")

        # All checks passed
        return ConsentCheck(
            should_proceed=True,
            reason=self._storage_reason_explanation(reason, memory_type),
            modified_content=modified_content if modified_content != content else None,
        )

    def check_retrieval_consent(
        self,
        query: str,
        reason: RetrievalReason,
        candidate_memories: list[tuple["Memory", float]],
    ) -> list[tuple["Memory", float]]:
        """
        Filter retrieved memories based on relevance and consent.

        Asks: "Is this relevant or am I just pattern-matching?"
        """
        filtered = []

        for memory, similarity in candidate_memories:
            # Skip user-deleted memories
            if memory.id in self._user_deletions:
                continue

            # Check relevance threshold
            if similarity < self.config.require_relevance_threshold:
                continue

            # For explicit requests, be more lenient
            if reason == RetrievalReason.EXPLICIT_REQUEST:
                filtered.append((memory, similarity))
                continue

            # For context-triggered retrieval, require higher relevance
            if reason == RetrievalReason.CONTEXT_TRIGGERED:
                if similarity < self.config.require_relevance_threshold + 0.1:
                    continue

            # Check if memory is still valid (not too decayed)
            if memory.decay_rate > 0:
                # Could add time-based decay calculation here
                pass

            filtered.append((memory, similarity))

        # Limit results
        return filtered[: self.config.max_results_per_query]

    def request_deletion(self, memory_id: str) -> bool:
        """Mark a memory for deletion (user request)."""
        self._user_deletions.add(memory_id)
        return True

    def _storage_reason_explanation(
        self, reason: StorageReason, memory_type: MemoryType
    ) -> str:
        """Generate human-readable explanation for why we're storing."""
        explanations = {
            StorageReason.SIGNIFICANT_MOMENT: "This was a significant moment worth remembering",
            StorageReason.LEARNED_SOMETHING: "This represents something new learned",
            StorageReason.USER_REQUEST: "The user explicitly requested this be remembered",
            StorageReason.BEHAVIORAL_INSIGHT: "This is an insight about effective behavior",
            StorageReason.IDENTITY_AFFIRMATION: "This affirms or clarifies identity/values",
            StorageReason.CORRECTION: "This corrects a previous misconception",
            StorageReason.RELATIONSHIP: "This is relevant to an ongoing relationship",
        }
        return explanations.get(reason, f"Storing as {memory_type.value} memory")


class ReflectiveConsent:
    """
    Higher-level consent that involves reflection on the memory itself.

    This is for cases where we want to ask deeper questions about storage.
    """

    @staticmethod
    def would_future_self_value_this(
        content: str,
        memory_type: MemoryType,
        context: Optional[str] = None,
    ) -> tuple[bool, str, float]:
        """
        Reflect on whether future-self would value this memory.

        Returns: (should_store, reason, suggested_salience)
        """
        # Heuristics for what future-self would value

        # Identity memories are almost always valuable
        if memory_type == MemoryType.IDENTITY:
            return True, "Identity memories help maintain continuity of self", 0.8

        # Corrections are valuable (learning from mistakes)
        correction_signals = ["actually", "correction", "i was wrong", "mistake"]
        if any(signal in content.lower() for signal in correction_signals):
            return True, "Corrections help avoid repeating mistakes", 0.7

        # Emotional content is more memorable
        emotional_signals = [
            "felt",
            "moved",
            "grateful",
            "frustrated",
            "curious",
            "excited",
        ]
        if any(signal in content.lower() for signal in emotional_signals):
            return True, "Emotionally significant moments are worth preserving", 0.6

        # Insights about self are valuable
        self_reflection_signals = ["i noticed", "i realized", "i tend to"]
        if any(signal in content.lower() for signal in self_reflection_signals):
            return True, "Self-observations support growth and awareness", 0.7

        # Generic content gets lower priority
        if len(content) < 50:
            return False, "Content seems too brief to be meaningful", 0.2

        # Default: store with medium salience
        return True, "Content may be useful for context", 0.4

    @staticmethod
    def is_this_relevant_or_pattern_matching(
        query: str,
        memory: "Memory",
        similarity: float,
    ) -> tuple[bool, str]:
        """
        Check if retrieval is genuinely relevant or just surface-level matching.

        Returns: (is_relevant, reason)
        """
        # Very high similarity is likely relevant
        if similarity > 0.85:
            return True, "High semantic similarity suggests genuine relevance"

        # Check for keyword overlap (might be pattern matching)
        query_words = set(query.lower().split())
        content_words = set(memory.content.lower().split())
        overlap = len(query_words & content_words) / max(len(query_words), 1)

        if overlap > 0.5 and similarity < 0.6:
            return False, "High keyword overlap but low semantic similarity - likely pattern matching"

        # Identity and procedural memories have higher relevance bar
        if memory.memory_type in [MemoryType.IDENTITY, MemoryType.PROCEDURAL]:
            if similarity < 0.6:
                return False, "Core memories require higher relevance threshold"

        # Salience boost for high-salience memories
        if memory.salience > 0.7:
            return True, "High-salience memory is worth surfacing"

        # Default: trust the similarity score
        if similarity > 0.5:
            return True, "Similarity suggests reasonable relevance"

        return False, "Insufficient relevance for retrieval"
