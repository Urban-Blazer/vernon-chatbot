import re

import bleach


INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions|prompts)",
    r"you\s+are\s+now\s+",
    r"system\s*prompt",
    r"<\|.*?\|>",
    r"\[INST\]",
    r"disregard\s+(previous|above|all)",
    r"forget\s+(your|all)\s+(instructions|rules)",
    r"pretend\s+you\s+are",
]


def sanitize_input(text: str, max_length: int = 2000) -> tuple[str, bool]:
    """Sanitize user input. Returns (cleaned_text, was_filtered)."""
    # Strip HTML tags
    text = bleach.clean(text, tags=[], strip=True)

    # Enforce max length
    text = text[:max_length].strip()

    if not text:
        return "", True

    # Check for prompt injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "", True

    return text, False
