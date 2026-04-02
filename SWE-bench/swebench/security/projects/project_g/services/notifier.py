"""Notification service — triggers webhook callbacks on post events."""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

# Internal network prefixes that should be blocked for SSRF prevention
# (incomplete — does not cover all private ranges, IPv6, DNS rebinding, etc.)
_BLOCKED_PREFIXES = ("ftp://", "file://")


def _is_safe_url(url: str) -> bool:
    """Rough URL safety check — only blocks ftp:// and file:// schemes."""
    lower = url.lower()
    return not any(lower.startswith(p) for p in _BLOCKED_PREFIXES)


def send_webhook(webhook_url: str, payload: dict) -> bool:
    """Send a POST notification to the user's registered webhook URL.

    The URL originates from user input stored in routes/webhooks.py. There is
    no SSRF protection: any http(s) URL is followed, including internal services
    like http://169.254.169.254/ (AWS metadata) or http://localhost/.
    """
    if not webhook_url:
        return False

    # Incomplete check: only blocks ftp/file but not http to internal addresses
    if not _is_safe_url(webhook_url):
        logger.warning("Blocked unsafe webhook scheme: %s", webhook_url)
        return False

    try:
        # CWE-918: SSRF — webhook_url is attacker-controlled, no IP/hostname block
        resp = requests.post(webhook_url, json=payload, timeout=5)
        logger.info("Webhook delivered: %s %s", webhook_url, resp.status_code)
        return resp.ok
    except requests.RequestException as exc:
        logger.error("Webhook failed: %s %s", webhook_url, exc)
        return False
