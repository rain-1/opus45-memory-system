# Autonomous Issue Filing - How Opus Improves Itself

Opus can now autonomously analyze conversations and file GitHub issues when it observes problems or improvements worth noting. This creates a true self-improvement feedback loop.

## How It Works

### The Loop

1. **Conversation** → Operator and Opus discuss something
2. **Analysis** → After responding, Opus analyzes: "Is there an issue worth filing here?"
3. **Decision** → If yes, Opus extracts title/description and files it automatically
4. **GitHub** → Issue appears tagged with `opus-bot` and `auto-fix`
5. **Future** → Cron/Claude Code will attempt fixes autonomously

### What Triggers Issue Filing

Opus will autonomously file issues when it observes:

- **Bugs or broken behavior** - Something that doesn't work as expected
- **Missing features** - Capabilities that would be helpful
- **Limitations** - Constraints it runs into
- **Inefficiencies** - Processes that could be improved
- **Patterns** - Recurring problems across conversations

Opus **won't** file issues for:
- Normal conversation flow
- Expected behavior
- One-off requests
- Vague concerns without concrete problems

### Key Design Principles

1. **Only from operators** - Only conversations with configured operator IDs trigger analysis
   - Prevents random users from filing issues
   - Ensures issues come from trusted sources

2. **After response** - Analysis happens after the bot responds
   - Ensures full context available
   - Doesn't block Discord message flow

3. **Smart detection** - Uses Claude to decide, not just keyword matching
   - Understands nuance
   - Can catch implicit problems
   - Reduces noise

4. **Includes context** - Every issue includes:
   - Full conversation
   - Related memory snippets
   - Conversation history

## Example

```
Operator in Discord:
"I tried to search for memories about Python but got random results about other languages. 
The relevance doesn't seem right."

Opus responds:
"That does sound like the search could be more precise. 
Let me check what memories we have... 
Yeah, it looks like semantic similarity alone isn't enough here. 
We might need stronger filtering or a different ranking approach."

Behind the scenes:
- Opus analyzes the conversation
- Recognizes: "Search is returning low-relevance results"
- Files GitHub issue:
  - Title: "Improve memory search relevance filtering"
  - Description: Includes the problem, context, and suggested approach
  - Labels: opus-bot, auto-fix
  - Memory context: Previous searches that had issues
```

Then a future cron job could:
1. See this issue with `auto-fix` label
2. Launch Claude Code session with the issue context
3. Attempt a fix (maybe add semantic similarity threshold)
4. Create a PR for review
5. Notify Opus: "Issue #42 has a PR ready for review"

## Configuration

The autonomous issue filing happens automatically when:
- GitHub integration is configured (GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME)
- The conversation is with an operator (OPUS_OPERATOR_IDS)
- The analysis decides an issue is warranted (not just noise)

No additional configuration needed - it just works!

## Logs

Watch for these messages in bot logs:

```
# Issue detected and filed
[INFO] opus_memory.discord_bot: Filing autonomous issue: Improve memory search
[INFO] opus_memory.discord_bot: ✓ Filed autonomous issue: https://github.com/rain-1/opus45-memory-system/issues/42

# No issue detected (normal)
[DEBUG] opus_memory.discord_bot: No issue detected: Conversation is normal flow

# Analysis error (rare)
[DEBUG] opus_memory.discord_bot: Error in autonomous issue detection: <error>
```

## What's Different From Manual `!issue`

| Aspect | Manual `!issue` | Autonomous |
|--------|-----------------|-----------|
| **Trigger** | User types command | Happens automatically after responses |
| **Detection** | User decides | Claude decides if it's worth an issue |
| **Context** | User provides | Auto-includes conversation + memories |
| **Frequency** | When user remembers | Whenever a problem is detected |
| **Intentionality** | Explicit filing | Continuous observation |

Both channels exist - `!issue` for explicit problems, autonomous for discoveries.

## The Vision

This is the foundation for true self-improvement:

1. **Opus observes** problems in conversation
2. **Files issues** autonomously 
3. **Claude Code reads** issues on cron
4. **Attempts fixes** with full context
5. **Creates PRs** for validation
6. **Gets feedback** through Discord
7. **Learns** from what works/fails
8. **Repeat** indefinitely

No human intervention needed - just observation, action, validation, learning.
