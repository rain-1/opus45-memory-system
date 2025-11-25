# GitHub Integration - Self-Improvement Loop

Opus can now create GitHub issues to track problems or improvements it observes, creating a feedback loop where code can be fixed and deployed automatically.

## How It Works

1. **Opus observes** → Uses `!issue` command to file a GitHub issue
2. **Issue created** → GitHub issue tagged with `auto-fix` label 
3. **Cron/webhook triggers** → Claude Code attempts fix (future component)
4. **PR created** → Tests run, human reviews (future component)
5. **Resolution** → Discord notified of fix (future component)

## Setup

### 1. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name: "Opus Memory Bot"
4. Select scopes:
   - `repo` (full control of private/public repos)
   - `workflow` (if you want to trigger CI)
5. Copy the token

### 2. Add to .env

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO_OWNER=rain-1
GITHUB_REPO_NAME=opus45-memory

# Optional - customize labels
GITHUB_AUTO_FIX_LABEL=auto-fix
GITHUB_BOT_USER_LABEL=opus-bot
```

### 3. Verify Setup

The bot logs will show on startup:
```
✓ GitHub integration initialized
```

If it says "GitHub not configured" - check your env vars.

## Using the Feature

### Create an Issue

```
!issue Add memory search filtering | Currently all searches return everything, but we should be able to filter by memory type or time range
```

The command format is: `!issue <title> | <description>`

**Discord response:**
```
✓ Created GitHub issue:
https://github.com/rain-1/opus45-memory/issues/42
```

### What Gets Included

The issue automatically includes:
- Title and description from your command
- `opus-bot` label (identifies issues created by Opus)
- `auto-fix` label (marks for automated attempt)
- Memory context snippet (recent memories that informed the issue)
- Link back to Discord (in comments later)

### Example Issues

Good issues Opus might create:

- **Title:** Improve memory retrieval relevance
  **Description:** Recent searches have returned low-relevance results. We should increase semantic similarity threshold.

- **Title:** Add memory type filtering
  **Description:** Users should be able to search only episodic or semantic memories, not all types mixed together.

- **Title:** Fix identity memory display
  **Description:** `!identity` command returns empty even though we have 3 identity memories stored.

## The Loop (Phase 2)

Once the cron/webhook orchestrator is built:

1. **Hourly cron job** checks for issues with `auto-fix` label
2. **Launches Claude Code** with issue as context
3. **Attempts implementation** → creates PR
4. **Tests run** → validates fix doesn't break anything
5. **Auto-merge if tests pass** OR requires human review
6. **Discord notification** → "Issue #42 fixed! PR merged."

## Security Notes

⚠️ **NEVER COMMIT YOUR GITHUB TOKEN**

- `.env` is in `.gitignore` ✓
- `.env.example` has placeholder values ✓
- Token scopes should be as narrow as possible
- Token can be rotated at any time

If token is compromised:
1. Go to https://github.com/settings/tokens
2. Delete the compromised token
3. Generate a new one
4. Update `.env`

## Troubleshooting

### "GitHub integration not configured"

Check `.env` has:
- `GITHUB_TOKEN` set
- `GITHUB_REPO_OWNER` set
- `GITHUB_REPO_NAME` set

### "Failed to create GitHub issue"

Check logs for:
- Token validity (regenerate if old)
- Repo accessibility (token must have repo access)
- Rate limiting (GitHub has API limits)

### Issue created but no labels

Ensure labels exist on the repo first, or let GitHub auto-create them.

## Architecture

```python
# github_integration.py
GitHubConfig          # Load from environment
    ↓
GitHubIssueCreator   # Manages GitHub API
    ├─ create_issue()
    ├─ list_open_auto_fix_issues()
    └─ update_issue()
    
# discord_bot.py
OpusDiscordBot.__init__()
    ├─ Initializes GitHubIssueCreator if configured
    ├─ Stores as self.github
    
async def _cmd_issue()
    └─ User triggers: !issue <title> | <description>
    └─ Calls self.github.create_issue()
    └─ Returns URL to Discord
```

## Next Steps

1. **Cron orchestrator** - Check for issues, launch Claude Code
2. **PR orchestration** - Create PRs from attempted fixes
3. **Discord feedback loop** - Notify when fixes are ready/merged
4. **Memory-informed fixes** - Use Opus memory as additional context for fixes
