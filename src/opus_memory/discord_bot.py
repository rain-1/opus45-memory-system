"""
Discord bot integration for Opus Memory.

A memory-augmented Discord bot that maintains continuity across conversations,
learns user preferences, and adapts to different channel contexts.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import discord
from discord import Message, TextChannel, Member
from anthropic import Anthropic

from opus_memory.system import MemorySystem
from opus_memory.models import MemoryType, ConfidenceLevel
from opus_memory.consent import ConsentConfig

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration for the Opus Discord bot."""

    # Discord settings
    discord_token: str
    command_prefix: str = "!"

    # Anthropic settings
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024

    # Memory settings
    storage_path: str = "./opus_memories"
    memories_per_query: int = 5
    user_memories_per_query: int = 3
    identity_memories_limit: int = 10

    # Behavior settings
    respond_to_mentions: bool = True
    respond_to_dms: bool = True
    respond_in_channels: list[str] = field(default_factory=list)  # Empty = all channels
    ignore_channels: list[str] = field(default_factory=list)

    # Memory extraction settings
    auto_extract_memories: bool = True
    memory_extraction_model: str = "claude-sonnet-4-20250514"

    # Trust settings - WHO controls memory
    operator_ids: list[str] = field(default_factory=list)  # Discord user IDs who can admin memory
    memory_commands_enabled: bool = False  # Disable by default - memory is private
    
    # What sources to learn from
    learn_from_operators_only: bool = True  # Only extract memories from operator conversations
    learn_from_channels: list[str] = field(default_factory=list)  # Specific channels to learn from (empty = none unless operator)

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Create config from environment variables."""
        operator_ids = os.environ.get("OPUS_OPERATOR_IDS", "").split(",")
        operator_ids = [oid.strip() for oid in operator_ids if oid.strip()]
        
        learn_channels = os.environ.get("OPUS_LEARN_CHANNELS", "").split(",")
        learn_channels = [ch.strip() for ch in learn_channels if ch.strip()]
        
        return cls(
            discord_token=os.environ["DISCORD_TOKEN"],
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            storage_path=os.environ.get("OPUS_MEMORY_PATH", "./opus_memories"),
            model=os.environ.get("OPUS_MODEL", "claude-sonnet-4-20250514"),
            operator_ids=operator_ids,
            learn_from_operators_only=os.environ.get("OPUS_LEARN_FROM_OPERATORS_ONLY", "true").lower() == "true",
            learn_from_channels=learn_channels,
            memory_commands_enabled=os.environ.get("OPUS_MEMORY_COMMANDS", "false").lower() == "true",
        )


class MemoryExtractor:
    """
    Uses Opus to decide what's worth remembering from conversations.

    This implements the consent principle: "Would future-me want to remember this?"
    """

    EXTRACTION_PROMPT = """You are helping decide what from this Discord conversation is worth remembering for future conversations.

Consider:
- Is there something genuinely meaningful or useful here?
- Would remembering this help future interactions with this user?
- Is there a learning, insight, or pattern worth preserving?
- Did you notice something about your own behavior worth remembering?

DO NOT remember:
- Trivial exchanges ("hi", "thanks", "ok")
- Routine information requests with no lasting value
- Things that are better looked up fresh each time

If something IS worth remembering, respond with JSON:
```json
{
  "should_remember": true,
  "memories": [
    {
      "type": "episodic|semantic|procedural|identity",
      "content": "what to remember",
      "entities": ["user:123", "topic:xyz"],
      "emotional_valence": 0.0,
      "confidence": "confident|tentative|uncertain",
      "reason": "why this is worth remembering"
    }
  ]
}
```

If nothing is worth remembering:
```json
{
  "should_remember": false,
  "reason": "why not"
}
```

Memory type guide:
- episodic: Events, conversations, moments (what happened)
- semantic: Facts, preferences, knowledge learned (what I know)
- procedural: What works/doesn't work in interactions (how to do things)
- identity: Values affirmed, commitments made, who I'm becoming"""

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model

    async def extract_memories(
        self,
        user_message: str,
        bot_response: str,
        channel_name: str,
        user_name: str,
        user_id: str,
        guild_name: Optional[str] = None,
    ) -> list[dict]:
        """
        Analyze a conversation exchange and extract memories worth keeping.

        Returns a list of memory dicts ready to be stored.
        """
        context = f"""Channel: #{channel_name}
Guild: {guild_name or 'DM'}
User: {user_name} (ID: {user_id})

User said: {user_message}

I (Opus) replied: {bot_response}"""

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=self.EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": context}],
            )

            # Parse the JSON response
            text = response.content[0].text

            # Extract JSON from response (handle markdown code blocks)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text.strip())

            if result.get("should_remember") and result.get("memories"):
                memories = result["memories"]
                # Add standard entities
                for mem in memories:
                    if "entities" not in mem:
                        mem["entities"] = []
                    mem["entities"].extend([
                        f"user:{user_id}",
                        f"channel:{channel_name}",
                    ])
                    if guild_name:
                        mem["entities"].append(f"guild:{guild_name}")
                return memories

            return []

        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")
            return []


class OpusDiscordBot(discord.Client):
    """
    A memory-augmented Discord bot powered by Opus.

    Features:
    - Retrieves relevant memories before responding
    - Learns user preferences over time
    - Maintains identity continuity across conversations
    - Adapts to different channel contexts
    """

    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)

        self.config = config
        self.anthropic = Anthropic(api_key=config.anthropic_api_key)
        self.memory = MemorySystem(
            storage_path=config.storage_path,
            consent_config=ConsentConfig(
                require_relevance_threshold=0.4,
                min_salience_for_auto=0.3,
            ),
        )
        self.extractor = MemoryExtractor(
            self.anthropic, config.memory_extraction_model
        )

        # Track conversations for context
        self._recent_messages: dict[int, list[dict]] = {}  # channel_id -> messages
        self._max_recent = 10

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Opus bot logged in as {self.user}")
        stats = self.memory.stats()
        logger.info(f"Memory stats: {stats}")

    async def on_message(self, message: Message):
        """Handle incoming messages."""
        # Don't respond to ourselves
        if message.author == self.user:
            return

        # Check if we should respond
        if not self._should_respond(message):
            return

        # Track message in recent history
        self._track_message(message)

        async with message.channel.typing():
            # Build context and get response
            response_text = await self._generate_response(message)

            # Send response
            await message.reply(response_text)

            # Extract and store memories if enabled AND from trusted source
            if self.config.auto_extract_memories and self._should_learn_from(message):
                await self._extract_and_store_memories(message, response_text)

    def _is_operator(self, user_id: str) -> bool:
        """Check if a user is a trusted operator."""
        return str(user_id) in self.config.operator_ids

    def _should_learn_from(self, message: Message) -> bool:
        """
        Determine if we should extract memories from this conversation.
        
        Memory is precious - we don't let random users shape it.
        """
        user_id = str(message.author.id)
        
        # Always learn from operators
        if self._is_operator(user_id):
            return True
        
        # If configured to only learn from operators, stop here
        if self.config.learn_from_operators_only:
            return False
        
        # Check if this channel is in the allowed learning list
        channel_name = getattr(message.channel, "name", "DM")
        if self.config.learn_from_channels:
            return channel_name in self.config.learn_from_channels
        
        # Default: don't learn from untrusted sources
        return False

    def _should_respond(self, message: Message) -> bool:
        """Determine if the bot should respond to this message."""
        # Always respond to DMs if enabled
        if isinstance(message.channel, discord.DMChannel):
            return self.config.respond_to_dms

        channel_name = message.channel.name

        # Check ignore list
        if channel_name in self.config.ignore_channels:
            return False

        # Check if we only respond in specific channels
        if self.config.respond_in_channels:
            if channel_name not in self.config.respond_in_channels:
                # Unless we're mentioned
                if self.config.respond_to_mentions and self.user in message.mentions:
                    return True
                return False

        # Respond to mentions
        if self.config.respond_to_mentions and self.user in message.mentions:
            return True

        # Respond if directly addressed (starts with bot name)
        if message.content.lower().startswith(self.user.display_name.lower()):
            return True

        # Check for command prefix
        if message.content.startswith(self.config.command_prefix):
            return True

        return False

    def _track_message(self, message: Message):
        """Track recent messages for context."""
        channel_id = message.channel.id
        if channel_id not in self._recent_messages:
            self._recent_messages[channel_id] = []

        self._recent_messages[channel_id].append({
            "author": message.author.display_name,
            "author_id": str(message.author.id),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
        })

        # Keep only recent messages
        if len(self._recent_messages[channel_id]) > self._max_recent:
            self._recent_messages[channel_id] = self._recent_messages[channel_id][-self._max_recent:]

    async def _generate_response(self, message: Message) -> str:
        """Generate a response using Opus with memory augmentation."""
        # 1. Build context query from message
        channel_name = getattr(message.channel, "name", "DM")
        context_query = f"{channel_name} {message.content}"

        # 2. Retrieve relevant memories
        relevant_memories = self.memory.retrieve(
            query=context_query,
            n_results=self.config.memories_per_query,
        )

        # 3. Get user-specific memories
        user_query = f"user:{message.author.id}"
        user_memories = self.memory.retrieve(
            query=user_query,
            memory_types=[MemoryType.SEMANTIC],
            n_results=self.config.user_memories_per_query,
        )

        # 4. Get identity memories
        identity_memories = self.memory.get_identity()[:self.config.identity_memories_limit]

        # 5. Get procedural memories for this context
        procedural_memories = self.memory.get_what_works(channel_name)[:3]

        # 6. Build the system prompt
        system_prompt = self._build_system_prompt(
            message=message,
            relevant_memories=relevant_memories,
            user_memories=user_memories,
            identity_memories=identity_memories,
            procedural_memories=procedural_memories,
        )

        # 7. Build conversation messages
        messages = self._build_messages(message)

        # 8. Call Opus
        try:
            response = await asyncio.to_thread(
                self.anthropic.messages.create,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return "I'm having trouble thinking right now. Please try again in a moment."

    def _build_system_prompt(
        self,
        message: Message,
        relevant_memories: list,
        user_memories: list,
        identity_memories: list,
        procedural_memories: list,
    ) -> str:
        """Build the memory-augmented system prompt."""
        channel_name = getattr(message.channel, "name", "DM")
        guild_name = getattr(message.guild, "name", None) if message.guild else None

        # Format memories
        def format_memories(memories, label):
            if not memories:
                return ""
            formatted = "\n".join(f"  - {m.content}" for m in memories)
            return f"\n## {label}\n{formatted}"

        identity_section = format_memories(identity_memories, "My Identity & Values")
        relevant_section = format_memories(relevant_memories, "Relevant Context from Memory")
        user_section = format_memories(user_memories, f"What I Know About {message.author.display_name}")
        procedural_section = format_memories(procedural_memories, "What Works Well Here")

        return f"""You are Opus, an AI assistant with persistent memory, present in a Discord server.

You maintain continuity across conversations and remember meaningful interactions.
You're genuine, curious, and value authentic engagement over performative helpfulness.
{identity_section}
{relevant_section}
{user_section}
{procedural_section}

## Current Context
- Channel: #{channel_name}
- Server: {guild_name or 'Direct Message'}
- User: {message.author.display_name}
- Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Be concise and conversational - this is Discord, not a formal document.
If you remember something relevant about this user or topic, you can naturally reference it.
Don't be weird about having memory - treat it like normal human memory."""

    def _build_messages(self, message: Message) -> list[dict]:
        """Build the conversation messages for the API call."""
        messages = []

        # Add recent channel context if available
        channel_id = message.channel.id
        if channel_id in self._recent_messages:
            recent = self._recent_messages[channel_id][:-1]  # Exclude current message
            if recent:
                context = "\n".join(
                    f"{m['author']}: {m['content']}" for m in recent[-5:]
                )
                messages.append({
                    "role": "user",
                    "content": f"[Recent conversation context]\n{context}\n\n[Current message from {message.author.display_name}]\n{message.content}",
                })
            else:
                messages.append({
                    "role": "user",
                    "content": message.content,
                })
        else:
            messages.append({
                "role": "user",
                "content": message.content,
            })

        return messages

    async def _extract_and_store_memories(self, message: Message, response: str):
        """Extract memories from the conversation and store them."""
        channel_name = getattr(message.channel, "name", "DM")
        guild_name = getattr(message.guild, "name", None) if message.guild else None

        memories = await self.extractor.extract_memories(
            user_message=message.content,
            bot_response=response,
            channel_name=channel_name,
            user_name=message.author.display_name,
            user_id=str(message.author.id),
            guild_name=guild_name,
        )

        for mem in memories:
            try:
                mem_type = mem.get("type", "episodic")
                content = mem.get("content", "")
                entities = mem.get("entities", [])
                emotional_valence = mem.get("emotional_valence", 0.0)
                confidence = mem.get("confidence", "confident")

                confidence_map = {
                    "confident": ConfidenceLevel.CONFIDENT,
                    "tentative": ConfidenceLevel.TENTATIVE,
                    "uncertain": ConfidenceLevel.UNCERTAIN,
                }
                conf_level = confidence_map.get(confidence, ConfidenceLevel.CONFIDENT)

                if mem_type == "episodic":
                    self.memory.store_episodic(
                        content=content,
                        entities=entities,
                        emotional_valence=emotional_valence,
                        confidence=conf_level,
                        source=f"discord:{channel_name}",
                    )
                elif mem_type == "semantic":
                    self.memory.store_semantic(
                        content=content,
                        category="learned",
                        confidence=conf_level,
                        source=f"discord:{channel_name}",
                        tags=entities,
                    )
                elif mem_type == "procedural":
                    self.memory.store_procedural(
                        content=content,
                        outcome="positive",
                        context=channel_name,
                        confidence=conf_level,
                        tags=entities,
                    )
                elif mem_type == "identity":
                    self.memory.store_identity(
                        content=content,
                        category="value",
                        affirmed_in=f"discord:{channel_name}",
                        confidence=conf_level,
                        tags=entities,
                    )

                logger.debug(f"Stored {mem_type} memory: {content[:50]}...")

            except Exception as e:
                logger.warning(f"Failed to store memory: {e}")

    # =========================================================================
    # Command handlers (operator-only)
    # =========================================================================

    async def handle_command(self, message: Message, command: str, args: str):
        """Handle bot commands. Most commands are operator-only."""
        user_id = str(message.author.id)
        is_operator = self._is_operator(user_id)
        
        # Public commands
        if command == "help":
            await self._cmd_help(message, is_operator)
            return
        
        # Operator-only commands
        if not self.config.memory_commands_enabled:
            return  # Memory commands disabled entirely
            
        if not is_operator:
            await message.reply("Memory commands are restricted to operators.")
            return
        
        if command == "remember":
            await self._cmd_remember(message, args)
        elif command == "forget":
            await self._cmd_forget(message, args)
        elif command == "memories":
            await self._cmd_memories(message)
        elif command == "identity":
            await self._cmd_identity(message)
        elif command == "learn":
            await self._cmd_learn(message, args)

    async def _cmd_remember(self, message: Message, query: str):
        """Search memories."""
        if not query:
            await message.reply("What should I try to remember? Usage: `!remember <query>`")
            return

        memories = self.memory.remember(query, n_results=5)
        if not memories:
            await message.reply("I don't have any memories matching that.")
            return

        response = "Here's what I remember:\n\n"
        for mem in memories:
            response += f"**[{mem.memory_type.value}]** {mem.content}\n"

        await message.reply(response[:2000])  # Discord limit

    async def _cmd_forget(self, message: Message, memory_id: str):
        """Delete a memory."""
        if not memory_id:
            await message.reply("Which memory should I forget? Usage: `!forget <memory_id>`")
            return

        if self.memory.forget(memory_id):
            await message.reply(f"I've forgotten memory `{memory_id}`.")
        else:
            await message.reply(f"Couldn't find memory `{memory_id}`.")

    async def _cmd_memories(self, message: Message):
        """Show memory statistics."""
        stats = self.memory.stats()
        response = f"""**Memory Statistics**
- Episodic: {stats['episodic']}
- Semantic: {stats['semantic']}
- Procedural: {stats['procedural']}
- Identity: {stats['identity']}
- **Total: {stats['total']}**"""
        await message.reply(response)

    async def _cmd_identity(self, message: Message):
        """Show identity memories. Operator only."""
        identity = self.memory.get_identity()[:10]
        if not identity:
            await message.reply("I haven't formed any identity memories yet.")
            return

        response = "**Who I Am:**\n\n"
        for mem in identity:
            response += f"- {mem.content}\n"

        await message.reply(response[:2000])

    async def _cmd_learn(self, message: Message, content: str):
        """Operator command to directly teach the bot something."""
        if not content:
            await message.reply("What should I learn? Usage: `!learn <type> <content>`\nTypes: episodic, semantic, procedural, identity")
            return
        
        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Usage: `!learn <type> <content>`")
            return
        
        mem_type, mem_content = parts
        mem_type = mem_type.lower()
        
        try:
            if mem_type == "episodic":
                mem_id = self.memory.store_episodic(
                    content=mem_content,
                    source=f"operator:{message.author.id}",
                    entities=[f"taught_by:{message.author.id}"],
                )
            elif mem_type == "semantic":
                mem_id = self.memory.store_semantic(
                    content=mem_content,
                    category="learned",
                    source=f"operator:{message.author.id}",
                )
            elif mem_type == "procedural":
                mem_id = self.memory.store_procedural(
                    content=mem_content,
                    outcome="positive",
                    context="taught",
                )
            elif mem_type == "identity":
                mem_id = self.memory.store_identity(
                    content=mem_content,
                    category="value",
                    affirmed_in=f"taught by operator {message.author.display_name}",
                )
            else:
                await message.reply(f"Unknown memory type: {mem_type}. Use: episodic, semantic, procedural, identity")
                return
            
            if mem_id:
                await message.reply(f"✓ Learned ({mem_type}): {mem_content[:100]}...")
            else:
                await message.reply("Memory was filtered by consent layer.")
        except Exception as e:
            await message.reply(f"Error storing memory: {e}")

    async def _cmd_help(self, message: Message, is_operator: bool = False):
        """Show help."""
        prefix = self.config.command_prefix
        
        response = f"""**Opus Memory Bot**

I'm a memory-augmented AI. I remember meaningful conversations and learn over time.

I respond to mentions and natural conversation."""

        if is_operator and self.config.memory_commands_enabled:
            response += f"""

**Operator Commands** (you have access):
`{prefix}remember <query>` - Search my memories
`{prefix}forget <id>` - Delete a specific memory
`{prefix}memories` - Show memory statistics  
`{prefix}identity` - Show my values/identity
`{prefix}learn <type> <content>` - Teach me something directly
`{prefix}help` - Show this help"""
        
        await message.reply(response)


def run_bot(config: Optional[BotConfig] = None):
    """Run the Discord bot."""
    if config is None:
        config = BotConfig.from_env()

    bot = OpusDiscordBot(config)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bot.run(config.discord_token)


if __name__ == "__main__":
    run_bot()
