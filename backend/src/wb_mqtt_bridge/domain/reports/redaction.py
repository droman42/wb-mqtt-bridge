"""Redaction pass (problem_reports_bridge.md B-5), applied to configs and log
excerpts before anything leaves the process. The reports repo is private, so
room/device names stay; only credential-shaped values are masked (the MQTT
broker password in system.json is the known hot item)."""

import re
from typing import Any

MASK = "***"

# A mapping key whose VALUE must be masked. Matches token/password/secret/
# credential anywhere in the key, plus bare "key"/"api_key"-style endings —
# deliberately over-broad (masking too much is safe; leaking is not).
_SECRET_KEY_RE = re.compile(r"(?i)(token|passw|secret|credential|api[-_]?key|(^|_)key(s)?$|auth)")

# Text-form leaks in logs: `Authorization: Bearer x`, `PASSWORD=x`, `token: x` —
# masked to end of line (a Bearer value is two tokens).
_SECRET_TEXT_RE = re.compile(
    r"(?i)((?:authorization|token|passw\w*|secret|credential|api[-_]?key)\S*\s*[=:]\s*)(.+)$",
    re.MULTILINE,
)


def redact_mapping(obj: Any) -> Any:
    """Deep-copy ``obj`` with credential-shaped keys' SCALAR values masked.
    A matching key holding a container (e.g. an ``auth`` dict) recurses instead —
    its username/host stay diagnostic, only the credential leaves get masked."""
    if isinstance(obj, dict):
        return {
            k: (
                redact_mapping(v)
                if isinstance(v, (dict, list, tuple)) or not _SECRET_KEY_RE.search(str(k))
                else MASK
            )
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact_mapping(v) for v in obj]
    return obj


def redact_text(text: str) -> str:
    """Mask credential-shaped assignments quoted in free text / log lines."""
    return _SECRET_TEXT_RE.sub(lambda m: m.group(1) + MASK, text)
