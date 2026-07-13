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

# VWB-30 (#14): credentials embedded in a URL's userinfo — `scheme://user:password@host`
# (e.g. a broker URL `mqtt://admin:t6uxESDN@192.168.110.250`) carry no keyword marker, so
# the assignment regex above misses them. Mask the password segment, keep the user + host.
_SECRET_URL_RE = re.compile(r"(?i)(\b[a-z][a-z0-9+.\-]*://[^/\s:@]+:)([^/\s@]+)(@)")


def _mask_all(obj: Any) -> Any:
    """Everything under a credential-shaped key is sensitive: keep the structure (so a
    report still shows *shape*) but mask every scalar leaf."""
    if isinstance(obj, dict):
        return {k: _mask_all(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_mask_all(v) for v in obj]
    return MASK


def redact_mapping(obj: Any) -> Any:
    """Deep-copy ``obj`` with credential-shaped keys' values masked.

    VWB-30 (#13): a matching key holding a *container* used to recurse normally, which
    leaked any secret leaf that didn't itself have a credential-shaped key (e.g.
    ``{"credentials": {"primary": "SECRET"}}`` — ``primary`` doesn't match, so it slipped
    through). Now a credential-shaped key masks its *whole* value — scalars directly, and
    containers via :func:`_mask_all` (structure kept, every leaf masked). Non-credential
    keys recurse as before. Masking too much is safe; leaking is not."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEY_RE.search(str(k)):
                out[k] = _mask_all(v) if isinstance(v, (dict, list, tuple)) else MASK
            else:
                out[k] = redact_mapping(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_mapping(v) for v in obj]
    return obj


def redact_text(text: str) -> str:
    """Mask credential-shaped assignments and URL-embedded credentials in free text /
    log lines (VWB-30 #14 adds the URL-userinfo form)."""
    text = _SECRET_TEXT_RE.sub(lambda m: m.group(1) + MASK, text)
    return _SECRET_URL_RE.sub(lambda m: m.group(1) + MASK + m.group(3), text)
