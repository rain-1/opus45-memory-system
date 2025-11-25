#!/usr/bin/env python3
"""
Run the Opus Memory Discord bot.

Usage:
    python -m opus_memory.run_discord_bot

Or with environment variables:
    DISCORD_TOKEN=xxx ANTHROPIC_API_KEY=xxx python -m opus_memory.run_discord_bot

Configuration via environment variables:
    DISCORD_TOKEN       - Required: Your Discord bot token
    ANTHROPIC_API_KEY   - Required: Your Anthropic API key
    OPUS_MEMORY_PATH    - Optional: Path to store memories (default: ./opus_memories)
    OPUS_MODEL          - Optional: Model to use (default: claude-sonnet-4-20250514)
"""

import os
import sys


def main():
    # Check required environment variables
    if "DISCORD_TOKEN" not in os.environ:
        print("Error: DISCORD_TOKEN environment variable is required")
        print("\nUsage:")
        print("  DISCORD_TOKEN=xxx ANTHROPIC_API_KEY=xxx python -m opus_memory.run_discord_bot")
        sys.exit(1)

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("Error: ANTHROPIC_API_KEY environment variable is required")
        sys.exit(1)

    from opus_memory.discord_bot import run_bot
    run_bot()


if __name__ == "__main__":
    main()
