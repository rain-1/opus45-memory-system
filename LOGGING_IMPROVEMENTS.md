# Discord Bot Logging Improvements

## Summary
Enhanced the Discord bot with comprehensive debug logging to provide visibility into:
- Memory operations (extraction, storage, retrieval)
- Command execution and routing
- Bot initialization and configuration
- Error conditions and edge cases

## Changes Made

### 1. **on_ready() - Bot Initialization Logging**
Shows when the bot starts up and displays:
- Operator configuration (operator IDs, whether operators-only learning is enabled)
- Initial memory statistics (breakdown by memory type)
- Example: `[INFO] Opus bot ready! Operators: 123456789, learn_from_operators_only=True, Stats: E=0 S=0 P=0 I=0`

### 2. **on_message() - Message Processing & Command Routing**
Logs every message event including:
- Which user sent the message
- Whether it should trigger learning (based on operator status)
- Command parsing (prefix detected, command extracted, args passed)
- Learning decision (if applicable)
- Example: `[INFO] Message from @user123: "hello"`
- Example: `[INFO] Command: remember ['my', 'memory']`

### 3. **_cmd_remember() - Memory Search**
Shows search operations:
- Query being searched
- Number of results found
- Example: `[INFO]   Searching memories for: 'my previous memories'`
- Example: `[INFO]   Found 3 relevant memories`

### 4. **_cmd_forget() - Memory Deletion**
Logs deletion attempts:
- Memory ID being forgotten
- Success/failure status
- Example: `[INFO]   ✓ Successfully forgot memory abc123`
- Example: `[WARNING]   ✗ Memory not found: invalid_id`

### 5. **_cmd_memories() - Statistics Display**
Shows memory stats queries:
- Breakdown of all memory types
- Example: `[INFO]   Memory stats: E=5 S=12 P=3 I=2 Total=22`

### 6. **_cmd_identity() - Identity Retrieval**
Logs identity memory operations:
- Number of identity memories retrieved
- Example: `[INFO]   Found 7 identity memories`

### 7. **_cmd_learn() - Direct Teaching**
Shows operator teaching commands:
- Memory type being taught
- Memory content (preview if long)
- Storage success/filtering status
- Example: `[INFO]   Teaching memory (semantic): Learn about quantum computing`
- Example: `[INFO]   ✓ Stored memory abc123 (semantic)`
- Example: `[INFO]   ✗ Memory filtered by consent layer (episodic)`

### 8. **_cmd_help() - Help Display**
Logs help requests:
- Whether user is an operator
- Example: `[INFO]   Showing help (operator=True)`

### 9. **_extract_and_store_memories() - Automatic Memory Extraction**
*Key addition for transparency* - Shows what memories are being automatically learned:
- Number of memories extracted by Opus
- Each memory's type, content preview, and reason
- Whether each memory passed consent filters
- Examples:
  ```
  [INFO]   Extracted 3 memories from message
  [INFO]   [1] ✓ episodic | User likes coffee | From message content
  [INFO]   [2] ✓ semantic | Python is a programming language | Learned fact
  [INFO]   [3] ✗ procedural | Filtered out | Low salience
  ```

### 10. **run_bot() - Startup Configuration**
Enhanced logging format with:
- Timestamp in `YYYY-MM-DD HH:MM:SS` format
- Properly aligned log level indicator `[LEVEL]`
- Example: `2024-01-15 14:30:45 [INFO    ] discord.bot: Connecting to Discord...`

## How to See the Logs

When running the Discord bot:

```bash
cd /home/ubuntu/code/opus45-memory
DISCORD_TOKEN=your_token ANTHROPIC_API_KEY=your_key python src/opus_memory/run_discord_bot.py
```

All logging output will appear in your terminal showing:
- When the bot starts and its configuration
- Every message received and whether it triggers learning
- All command executions with results
- All memory operations (storage, retrieval, deletion)
- Any errors or warnings

## Log Levels Used

- **INFO**: Normal operations (memory stored, command executed, stats retrieved)
- **WARNING**: Unusual but non-fatal (missing memory ID, unknown command type)
- **ERROR**: Failures that need attention (storage exceptions, API errors)
- **DEBUG**: Fine-grained details (can be enabled if needed)

## Benefits

1. **Transparency**: See exactly what the bot is doing in real-time
2. **Debugging**: Easy to diagnose issues or verify behavior
3. **Audit Trail**: Track what memories are being learned and why
4. **Trust**: Operator can verify that only authorized operations are happening
5. **Development**: Quick iteration when implementing new features
