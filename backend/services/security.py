"""Security utilities: sensitive data masking, audit sanitization."""

import re
from typing import Any

from config import settings

# Compiled patterns for sensitive field detection
_SENSITIVE_RE = re.compile(
    "|".join(re.escape(p) for p in settings.sensitive_field_patterns),
    re.IGNORECASE,
)

# Known sensitive value patterns
_VALUE_MASK_PATTERNS = [
    # JWT tokens
    (re.compile(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}'), 'JWT***'),
    # API keys (sk-, key-, token- prefixed)
    (re.compile(r'(?:sk|key|token|api[_-]?key)[=:]\s*["\']?([A-Za-z0-9_-]{20,})["\']?', re.IGNORECASE), lambda m: m.group(0)[:8] + '***'),
    # Passwords in connection strings
    (re.compile(r'(?:password|passwd|pwd)=([^&\s]+)', re.IGNORECASE), 'password=***'),
    # Bearer tokens
    (re.compile(r'Bearer\s+[A-Za-z0-9._-]{20,}'), 'Bearer ***'),
    # Private key markers
    (re.compile(r'-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----.*?-----END\s+(?:RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----', re.DOTALL), '[PRIVATE KEY REDACTED]'),
]


def is_sensitive_key(key: str) -> bool:
    """Return True if the key name looks like a sensitive field."""
    return bool(_SENSITIVE_RE.search(key))


def mask_sensitive_value(value: str) -> str:
    """Mask known sensitive value patterns in a string."""
    result = value
    for pattern, replacement in _VALUE_MASK_PATTERNS:
        result = pattern.sub(replacement if isinstance(replacement, str) else replacement, result)
    return result


def sanitize_dict(data: dict) -> dict:
    """Recursively mask sensitive values in a dictionary."""
    if not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(v) if isinstance(v, dict) else
                mask_sensitive_value(str(v)) if is_sensitive_key(key) else v
                for v in value
            ]
        elif isinstance(value, str):
            if is_sensitive_key(key):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = mask_sensitive_value(value)
        elif is_sensitive_key(key):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    return sanitized


def sanitize_for_audit(content: Any) -> Any:
    """Sanitize content for audit log storage — mask sensitive fields."""
    if isinstance(content, dict):
        return sanitize_dict(content)
    if isinstance(content, str):
        return mask_sensitive_value(content)
    return content
