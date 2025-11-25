"""GitHub integration for creating self-improvement issues.

Allows the Discord bot to file issues on GitHub that describe problems
or improvements Opus has identified, creating a feedback loop where
Claude Code can attempt fixes.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from github import Github, GithubException

logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    """Configuration for GitHub integration."""
    
    token: str  # GitHub personal access token
    repo_owner: str  # Repository owner (username or org)
    repo_name: str  # Repository name
    auto_fix_label: str = "auto-fix"  # Label to mark issues for automated attempts
    bot_user_label: str = "opus-bot"  # Label to identify issues created by Opus
    
    @classmethod
    def from_env(cls) -> "GitHubConfig":
        """Load configuration from environment variables."""
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        
        repo_owner = os.environ.get("GITHUB_REPO_OWNER")
        if not repo_owner:
            raise ValueError("GITHUB_REPO_OWNER environment variable is required")
        
        repo_name = os.environ.get("GITHUB_REPO_NAME")
        if not repo_name:
            raise ValueError("GITHUB_REPO_NAME environment variable is required")
        
        auto_fix_label = os.environ.get("GITHUB_AUTO_FIX_LABEL", "auto-fix")
        bot_user_label = os.environ.get("GITHUB_BOT_USER_LABEL", "opus-bot")
        
        return cls(
            token=token,
            repo_owner=repo_owner,
            repo_name=repo_name,
            auto_fix_label=auto_fix_label,
            bot_user_label=bot_user_label,
        )


class GitHubIssueCreator:
    """Creates GitHub issues from Discord observations."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize GitHub integration.
        
        Args:
            config: GitHub configuration
        """
        self.config = config
        self.github = Github(config.token)
        
        try:
            self.repo = self.github.get_user(config.repo_owner).get_repo(config.repo_name)
            logger.info(f"✓ Connected to GitHub: {config.repo_owner}/{config.repo_name}")
        except GithubException as e:
            logger.error(f"Failed to connect to GitHub repo: {e}")
            raise
    
    def create_issue(
        self,
        title: str,
        description: str,
        auto_fix: bool = False,
        memory_context: Optional[str] = None,
    ) -> Optional[str]:
        """Create a GitHub issue from a Discord observation.
        
        Args:
            title: Issue title
            description: Issue description
            auto_fix: Whether to tag this for automated fix attempts
            memory_context: Optional memory context that informed this issue
            
        Returns:
            Issue URL if successful, None if failed
        """
        try:
            # Build the full body with context
            body = description
            
            if memory_context:
                body += f"\n\n## Memory Context\n```\n{memory_context}\n```"
            
            body += "\n\n---\n*Created by Opus Discord Bot for self-improvement*"
            
            # Prepare labels
            labels = [self.config.bot_user_label]
            if auto_fix:
                labels.append(self.config.auto_fix_label)
            
            # Create the issue
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels,
            )
            
            logger.info(f"✓ Created GitHub issue #{issue.number}: {title}")
            return issue.html_url
            
        except GithubException as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating GitHub issue: {e}")
            return None
    
    def list_open_auto_fix_issues(self) -> list[dict]:
        """List all open issues tagged for auto-fix.
        
        Returns:
            List of issue info dicts with keys: number, title, url, body
        """
        try:
            issues = self.repo.get_issues(
                state="open",
                labels=[self.config.auto_fix_label],
            )
            
            result = []
            for issue in issues:
                result.append({
                    "number": issue.number,
                    "title": issue.title,
                    "url": issue.html_url,
                    "body": issue.body,
                })
            
            return result
            
        except GithubException as e:
            logger.error(f"Failed to list GitHub issues: {e}")
            return []
    
    def update_issue(
        self,
        issue_number: int,
        state: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """Update an issue (close it, add comment, etc).
        
        Args:
            issue_number: GitHub issue number
            state: New state ("open" or "closed")
            comment: Comment to add
            
        Returns:
            True if successful
        """
        try:
            issue = self.repo.get_issue(issue_number)
            
            if state:
                issue.edit(state=state)
                logger.info(f"✓ Updated issue #{issue_number} state to {state}")
            
            if comment:
                issue.create_comment(comment)
                logger.info(f"✓ Added comment to issue #{issue_number}")
            
            return True
            
        except GithubException as e:
            logger.error(f"Failed to update GitHub issue: {e}")
            return False
