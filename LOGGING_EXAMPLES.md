# Discord Bot Logging Examples

This document shows example log output you'll see when running the Discord bot with the new logging improvements.

## Bot Startup

```
2024-01-15 14:30:45 [INFO    ] discord.client: logging in using static token
2024-01-15 14:30:46 [INFO    ] opus_memory.discord_bot: Bot starting with config
2024-01-15 14:30:47 [INFO    ] discord.client: Websocket closed with opcode 1000
2024-01-15 14:30:48 [INFO    ] opus_memory.discord_bot: Opus bot ready!
2024-01-15 14:30:48 [INFO    ] opus_memory.discord_bot:   Operators: 123456789, 987654321
2024-01-15 14:30:48 [INFO    ] opus_memory.discord_bot:   learn_from_operators_only=True
2024-01-15 14:30:48 [INFO    ] opus_memory.discord_bot:   memory_commands_enabled=True
2024-01-15 14:30:48 [INFO    ] opus_memory.discord_bot:   Stats: E=12 S=45 P=8 I=3 Total=68
```

## Regular User Message (No Learning)

```
2024-01-15 14:31:00 [INFO    ] opus_memory.discord_bot: Message from @alice: "hey what's up"
2024-01-15 14:31:01 [INFO    ] opus_memory.discord_bot:   Not learning from non-operator (alice not in operators)
```

## Operator Message (Learning Triggered)

```
2024-01-15 14:31:15 [INFO    ] opus_memory.discord_bot: Message from @operator: "I just implemented a new feature for handling edge cases"
2024-01-15 14:31:15 [INFO    ] opus_memory.discord_bot:   Learning from operator (123456789)
2024-01-15 14:31:17 [INFO    ] opus_memory.discord_bot:   Extracted 3 memories from message
2024-01-15 14:31:17 [INFO    ] opus_memory.discord_bot:   [1] ✓ episodic | Operator implemented edge case handling | From message content
2024-01-15 14:31:17 [INFO    ] opus_memory.discord_bot:   [2] ✓ semantic | Feature handling requires considering edge cases | Learned fact
2024-01-15 14:31:17 [INFO    ] opus_memory.discord_bot:   [3] ✗ procedural | Filtered out | Low salience score (0.32)
2024-01-15 14:31:18 [INFO    ] opus_memory.discord_bot:   Successfully stored 2/3 memories
```

## Command: !memories

```
2024-01-15 14:32:00 [INFO    ] opus_memory.discord_bot: Command: memories []
2024-01-15 14:32:00 [INFO    ] opus_memory.discord_bot:   Memory stats: E=13 S=47 P=8 I=4 Total=72
```

Output in Discord:
```
**Memory Statistics**
- Episodic: 13
- Semantic: 47
- Procedural: 8
- Identity: 4
- **Total: 72**
```

## Command: !remember

```
2024-01-15 14:32:15 [INFO    ] opus_memory.discord_bot: Command: remember ['my', 'interests']
2024-01-15 14:32:15 [INFO    ] opus_memory.discord_bot:   Searching memories for: 'my interests'
2024-01-15 14:32:16 [INFO    ] opus_memory.discord_bot:   Found 4 relevant memories
```

Output in Discord:
```
**Relevant Memories:**

1. **Episodic** (relevance: 0.92)
   You told me you like programming and coffee

2. **Semantic** (relevance: 0.87)
   Your interests include AI, machine learning, and open source

3. **Identity** (relevance: 0.81)
   I value learning and continuous improvement

4. **Semantic** (relevance: 0.76)
   You prefer working on meaningful projects
```

## Command: !learn

```
2024-01-15 14:33:00 [INFO    ] opus_memory.discord_bot: Command: learn ['semantic', 'Python', 'is', 'great', 'for', 'AI']
2024-01-15 14:33:00 [INFO    ] opus_memory.discord_bot:   Teaching memory (semantic): Python is great for AI
2024-01-15 14:33:01 [INFO    ] opus_memory.discord_bot:   ✓ Stored memory f1a2b3c4 (semantic)
```

Output in Discord:
```
✓ Learned (semantic): Python is great for AI...
```

## Command: !identity

```
2024-01-15 14:34:00 [INFO    ] opus_memory.discord_bot: Command: identity []
2024-01-15 14:34:00 [INFO    ] opus_memory.discord_bot:   Retrieving identity memories
2024-01-15 14:34:00 [INFO    ] opus_memory.discord_bot:   Found 4 identity memories
```

Output in Discord:
```
**Who I Am:**

- I value learning and growth
- I believe in being helpful and honest
- I like creative problem-solving
- I'm curious about how things work
```

## Command: !forget

```
2024-01-15 14:35:00 [INFO    ] opus_memory.discord_bot: Command: forget ['abc123def456']
2024-01-15 14:35:00 [INFO    ] opus_memory.discord_bot:   Attempting to forget memory: abc123def456
2024-01-15 14:35:00 [INFO    ] opus_memory.discord_bot:   ✓ Successfully forgot memory abc123def456
```

Output in Discord:
```
I've forgotten memory `abc123def456`.
```

## Command: !help

```
2024-01-15 14:36:00 [INFO    ] opus_memory.discord_bot: Command: help []
2024-01-15 14:36:00 [INFO    ] opus_memory.discord_bot:   Showing help (operator=True)
```

Output in Discord:
```
**Opus Memory Bot**

I'm a memory-augmented AI. I remember meaningful conversations and learn over time.

I respond to mentions and natural conversation.

**Operator Commands** (you have access):
`!remember <query>` - Search my memories
`!forget <id>` - Delete a specific memory
`!memories` - Show memory statistics  
`!identity` - Show my values/identity
`!learn <type> <content>` - Teach me something directly
`!help` - Show this help
```

## Error Scenario: Consent Layer Rejection

```
2024-01-15 14:37:00 [INFO    ] opus_memory.discord_bot: Message from @operator: "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua..."
2024-01-15 14:37:00 [INFO    ] opus_memory.discord_bot:   Learning from operator (123456789)
2024-01-15 14:37:01 [INFO    ] opus_memory.discord_bot:   Extracted 1 memories from message
2024-01-15 14:37:01 [INFO    ] opus_memory.discord_bot:   [1] ✗ episodic | Filtered out | Content too long (too much raw text to memorize)
2024-01-15 14:37:01 [INFO    ] opus_memory.discord_bot:   Successfully stored 0/1 memories
```

## Error Scenario: Command Error

```
2024-01-15 14:38:00 [INFO    ] opus_memory.discord_bot: Command: learn ['identity', 'My', 'new', 'value']
2024-01-15 14:38:00 [INFO    ] opus_memory.discord_bot:   Teaching memory (identity): My new value
2024-01-15 14:38:01 [ERROR   ] opus_memory.discord_bot:   Error storing memory: Invalid category for identity memory
```

Output in Discord:
```
Error storing memory: Invalid category for identity memory
```

## Understanding the Log Output

- **[INFO]**: Normal operations - everything is working as expected
- **[WARNING]**: Unexpected but non-blocking - e.g., missing memory ID
- **[ERROR]**: Something failed - the operation didn't complete
- **✓**: Success - the operation completed successfully
- **✗**: Filtered/Rejected - the operation was blocked (usually by consent layer)
- **Found N memories**: Search returned N results from the vector database
- **Extracted N memories**: Opus decided N memories were worth storing
- **Stored X/Y memories**: X memories passed consent filters, Y were extracted

## Performance Notes

- Memory extraction (Opus deciding what to remember) typically takes 1-3 seconds
- Searching memories is usually instant (< 100ms)
- Storing a memory is typically < 100ms
- These operations don't block Discord responses

## Tips for Debugging

1. **Check operator config**: Look for "Operators:" and "learn_from_operators_only=True" at startup
2. **Verify learning is happening**: Look for "Learning from operator" messages when operators speak
3. **See what's being remembered**: Check the memory extraction logs showing which memories passed filters
4. **Understand consent filtering**: Look for "[X] ✗" lines to see what was rejected and why
5. **Monitor commands**: Check command logs to see when commands are executed and what they return
