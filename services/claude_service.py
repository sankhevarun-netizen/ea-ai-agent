import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


MODEL = "claude-sonnet-4-6"


def call_claude(system_prompt: str, user_message: str) -> str:
    """Single-turn Claude call. Returns the text content string."""
    try:
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        return f'{{"error": "Claude call failed: {str(e)}"}}'


def call_claude_with_history(system_prompt: str, messages: list) -> str:
    """Multi-turn Claude call with message history. Returns text content string."""
    try:
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        return f'{{"error": "Claude call failed: {str(e)}"}}'
