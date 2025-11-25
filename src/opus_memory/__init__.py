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
from opus_memory.consent import ConsentConfig, ConsentLayer

__version__ = "0.1.0"
__all__ = [
    "MemorySystem",
    "Memory",
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "IdentityMemory",
    "MemoryType",
    "ConsentConfig",
    "ConsentLayer",
]

# Optional Discord bot import
try:
    from opus_memory.discord_bot import OpusDiscordBot, BotConfig, run_bot
    __all__.extend(["OpusDiscordBot", "BotConfig", "run_bot"])
except ImportError:
    # discord.py not installed
    pass
