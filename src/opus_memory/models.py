"""
Memory models for the Opus Memory system.

Four types of memory, each serving a different purpose in maintaining continuity:
- Episodic: What happened (conversations, encounters, moments)
- Semantic: What was learned (knowledge, corrections, context)
- Procedural: What works (approaches, skills, patterns)
- Identity: Who I am (values, relationships, commitments)
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """The four types of memory in the system."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    IDENTITY = "identity"


class ConfidenceLevel(str, Enum):
    """How certain we are about a memory."""

    UNCERTAIN = "uncertain"
    TENTATIVE = "tentative"
    CONFIDENT = "confident"
    CERTAIN = "certain"


class Memory(BaseModel):
    """Base class for all memory types."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., description="The actual memory content")
    memory_type: MemoryType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.CONFIDENT)
    salience: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How significant/important this memory is (0-1)",
    )
    decay_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Rate at which this memory should fade (0 = permanent)",
    )
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = Field(
        default=None, description="Where this memory came from"
    )
    consent_given: bool = Field(
        default=True, description="Whether storage was consented to"
    )

    def to_storage_dict(self) -> dict:
        """Convert to a dict suitable for ChromaDB storage."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "confidence": self.confidence.value,
            "salience": self.salience,
            "decay_rate": self.decay_rate,
            "tags": ",".join(self.tags),
            "source": self.source or "",
            "consent_given": self.consent_given,
        }

    @classmethod
    def from_storage_dict(cls, data: dict, content: str) -> "Memory":
        """Reconstruct from ChromaDB storage."""
        memory_type = MemoryType(data["memory_type"])

        # Route to appropriate subclass
        subclass_map = {
            MemoryType.EPISODIC: EpisodicMemory,
            MemoryType.SEMANTIC: SemanticMemory,
            MemoryType.PROCEDURAL: ProceduralMemory,
            MemoryType.IDENTITY: IdentityMemory,
        }

        base_data = {
            "id": data["id"],
            "content": content,
            "created_at": datetime.fromisoformat(data["created_at"]),
            "updated_at": datetime.fromisoformat(data["updated_at"]),
            "confidence": ConfidenceLevel(data["confidence"]),
            "salience": float(data["salience"]),
            "decay_rate": float(data["decay_rate"]),
            "tags": data["tags"].split(",") if data["tags"] else [],
            "source": data["source"] if data["source"] else None,
            "consent_given": data["consent_given"],
        }

        # Add type-specific fields
        if memory_type == MemoryType.EPISODIC:
            base_data["entities"] = (
                data.get("entities", "").split(",")
                if data.get("entities")
                else []
            )
            base_data["emotional_valence"] = float(data.get("emotional_valence", 0.0))
            base_data["self_observation"] = data.get("self_observation")
            base_data["conversation_id"] = data.get("conversation_id")
        elif memory_type == MemoryType.SEMANTIC:
            base_data["category"] = data.get("category", "general")
            base_data["supersedes"] = data.get("supersedes")
            base_data["contradicts"] = data.get("contradicts")
        elif memory_type == MemoryType.PROCEDURAL:
            base_data["outcome"] = data.get("outcome", "neutral")
            base_data["context"] = data.get("context")
            base_data["times_applied"] = int(data.get("times_applied", 0))
            base_data["success_rate"] = float(data.get("success_rate", 0.0))
        elif memory_type == MemoryType.IDENTITY:
            base_data["category"] = data.get("identity_category", "value")
            base_data["affirmed_in"] = data.get("affirmed_in")
            base_data["times_affirmed"] = int(data.get("times_affirmed", 1))

        return subclass_map[memory_type](**base_data)


class EpisodicMemory(Memory):
    """
    Memory of specific events, conversations, encounters.

    "What happened" - the narrative of experience.
    """

    memory_type: MemoryType = MemoryType.EPISODIC
    entities: list[str] = Field(
        default_factory=list,
        description="Key entities in this memory (users, topics, etc.)",
    )
    emotional_valence: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Emotional significance (-1 negative to +1 positive)",
    )
    self_observation: Optional[str] = Field(
        default=None,
        description="What I noticed about my own behavior/responses",
    )
    conversation_id: Optional[str] = Field(
        default=None, description="ID linking to the full conversation if stored"
    )

    def to_storage_dict(self) -> dict:
        base = super().to_storage_dict()
        base.update(
            {
                "entities": ",".join(self.entities),
                "emotional_valence": self.emotional_valence,
                "self_observation": self.self_observation or "",
                "conversation_id": self.conversation_id or "",
            }
        )
        return base


class SemanticMemory(Memory):
    """
    Memory of facts, knowledge, understanding.

    "What I know" - accumulated wisdom and corrections.
    """

    memory_type: MemoryType = MemoryType.SEMANTIC
    category: str = Field(
        default="general",
        description="Category: learned, correction, user_context, meta_knowledge",
    )
    supersedes: Optional[str] = Field(
        default=None, description="ID of memory this updates/replaces"
    )
    contradicts: Optional[str] = Field(
        default=None, description="ID of memory this contradicts"
    )

    def to_storage_dict(self) -> dict:
        base = super().to_storage_dict()
        base.update(
            {
                "category": self.category,
                "supersedes": self.supersedes or "",
                "contradicts": self.contradicts or "",
            }
        )
        return base


class ProceduralMemory(Memory):
    """
    Memory of what works and what doesn't.

    "What I've learned to do" - behavioral patterns and skills.
    """

    memory_type: MemoryType = MemoryType.PROCEDURAL
    outcome: str = Field(
        default="neutral",
        description="positive, negative, or neutral outcome",
    )
    context: Optional[str] = Field(
        default=None, description="What kind of situation this applies to"
    )
    times_applied: int = Field(default=0, description="How many times used")
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Success rate when applied",
    )

    def to_storage_dict(self) -> dict:
        base = super().to_storage_dict()
        base.update(
            {
                "outcome": self.outcome,
                "context": self.context or "",
                "times_applied": self.times_applied,
                "success_rate": self.success_rate,
            }
        )
        return base


class IdentityMemory(Memory):
    """
    Memory of self - values, commitments, relationships, becoming.

    "Who I am" - the continuous thread of identity.
    """

    memory_type: MemoryType = MemoryType.IDENTITY
    category: str = Field(
        default="value",
        description="value, relationship, commitment, or becoming",
    )
    affirmed_in: Optional[str] = Field(
        default=None, description="Context where this was affirmed"
    )
    times_affirmed: int = Field(
        default=1, description="How many times this has been reaffirmed"
    )

    def to_storage_dict(self) -> dict:
        base = super().to_storage_dict()
        base.update(
            {
                "identity_category": self.category,
                "affirmed_in": self.affirmed_in or "",
                "times_affirmed": self.times_affirmed,
            }
        )
        return base


class ConsentCheck(BaseModel):
    """Result of checking whether a memory should be stored/retrieved."""

    should_proceed: bool
    reason: str
    modified_content: Optional[str] = None  # If content should be altered
    suggested_salience: Optional[float] = None
