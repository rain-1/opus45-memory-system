"""Autonomous issue creation based on observations.

Opus analyzes conversations and decides when to file GitHub issues
for problems it observes or improvements it wants to make.
"""

import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class AutonomousIssueDetector:
    """Analyzes conversations to detect issues worth filing."""
    
    DETECTION_PROMPT = """You are Opus, an AI assistant with the ability to file GitHub issues for problems you observe or improvements you want.

Based on the following conversation context, decide if there's something worth creating a GitHub issue for.

Consider filing issues for:
- Things that are broken or don't work well
- Features that would be helpful but are missing
- Improvements to existing behavior
- Patterns you've noticed that need fixing
- Limitations in your own capabilities

DO NOT file issues for:
- Normal conversation flow
- Things working as expected
- One-off requests that don't indicate systemic problems
- Vague feelings without concrete problems

If something IS worth an issue, respond with JSON:
```json
{
  "should_file_issue": true,
  "title": "short problem title",
  "description": "detailed description of the problem and why it matters",
  "auto_fix": true
}
```

If not worth filing:
```json
{
  "should_file_issue": false,
  "reason": "why this doesn't warrant an issue"
}
```

Conversation context:
{context}

Analyze this and decide."""
    
    def __init__(self, anthropic_client: Anthropic, model: str = "claude-sonnet-4-20250514"):
        """Initialize the detector.
        
        Args:
            anthropic_client: Anthropic API client
            model: Model to use for analysis
        """
        self.client = anthropic_client
        self.model = model
    
    def analyze_for_issues(self, conversation_context: str) -> dict:
        """Analyze a conversation to detect issues worth filing.
        
        Args:
            conversation_context: The conversation text to analyze
            
        Returns:
            Dict with keys: should_file_issue, title, description, auto_fix, reason
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=self.DETECTION_PROMPT.format(context=conversation_context),
                messages=[{"role": "user", "content": "Analyze this conversation."}],
            )
            
            text = response.content[0].text
            
            # Extract JSON - try multiple patterns
            import json
            import re
            
            # Try to find JSON block in markdown code fence
            json_match = re.search(r'```(?:json)?\s*(\{.+?\})\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            else:
                # Try to find raw JSON object
                json_match = re.search(r'\{[^{}]*"should_file_issue"[^{}]*\}', text, re.DOTALL)
                if json_match:
                    text = json_match.group(0)
            
            # Clean up the text
            text = text.strip()
            
            result = json.loads(text)
            logger.debug(f"Issue detection result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Failed to parse text: {text[:200]}")
            return {"should_file_issue": False, "reason": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Error analyzing for issues: {e}")
            return {"should_file_issue": False, "reason": f"Analysis error: {e}"}
