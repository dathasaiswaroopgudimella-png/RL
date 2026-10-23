"""OpsArena Security & Sanitization Utilities.

Provides regex-based secret scrubbing and output bounds enforcement.
Ensures no credentials, API keys, or sensitive auth tokens leak into agent context
or public logs.
"""
import re

# Compiled secret patterns
API_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{16,}", re.IGNORECASE)
# Matches key=val or key: val while avoiding re-redacting already redacted placeholders
GENERIC_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|secret|token|api[_\-]?key|access[_\-]?key|private[_\-]?key)\b\s*[:=]\s*['\"]?(?!\[REDACTED)[^\s,;'\"\]]+['\"]?"
)

MAX_OUTPUT_CHARS = 4000
CUT_MARKER = f"\n[output cut at {MAX_OUTPUT_CHARS} characters]"


def scrub_secrets(text: str) -> str:
    """Redacts known credential patterns from strings."""
    if not isinstance(text, str):
        return text

    # Redact OpenAI/LiteLLM/Anthropic style API keys
    text = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)

    # Redact Bearer tokens
    text = BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)

    # Redact key=value or key: value credential assignments
    text = GENERIC_SECRET_PATTERN.sub(r"\1=[REDACTED_SECRET]", text)

    return text


def clip_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Clips text strictly to max_chars including truncation marker."""
    if not isinstance(text, str):
        text = str(text)

    # First scrub any secrets
    scrubbed = scrub_secrets(text)

    if len(scrubbed) <= max_chars:
        return scrubbed

    marker = f"\n[output cut at {max_chars} characters]"
    allowed_len = max(0, max_chars - len(marker))
    return scrubbed[:allowed_len] + marker
