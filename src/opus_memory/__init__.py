"""
Opus Memory - A persistent memory system for AI continuity.

Designed for remembering what matters while avoiding hoarding or surveillance.
"""

from opus_memory.system import MemorySystem
from opus_memory.models import (
    Memory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    IdentityMemory,
    MemoryType,
)

__version__ = "0.1.0"
__all__ = [
    "MemorySystem",
    "Memory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "IdentityMemory",
    "MemoryType",
]
