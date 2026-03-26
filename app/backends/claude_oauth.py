"""Claude OAuth backend -- direct API access using Claude Abo credentials.

Reads the OAuth token from ~/.claude/.credentials.json (stored by Claude CLI)
and calls the Anthropic Messages API directly. No proxy or CLI subprocess needed.

Key requirements discovered from OpenClaw/pi-ai source code:
- Must use Authorization: Bearer (not x-api-key)
- Must include anthropic-beta: oauth-2025-04-20,claude-code-20250219
- Must set User-Agent to claude-cli and x-app to cli
- Must include anthropic-dangerous-direct-browser-access header
- System prompt must start with Claude Code identity
"""

import json
import logging
import os
import time
from pathlib import Path

import requests

from app.backends.base import BaseBackend

logger = logging.getLogger(__name__)

# Anthropic API
API_URL = "https://api.anthropic.com/v1/messages"

# Certificate Pinning: eigenes CA-Bundle für API-Verbindungen
_CERTS_PATH = os.path.join(os.path.dirname(__file__), "pinned_certs.pem")
_VERIFY = _CERTS_PATH if os.path.exists(_CERTS_PATH) else True

# Required headers for OAuth token auth (from pi-ai source)
OAUTH_HEADERS = {
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "claude-code-20250219,oauth-2025-04-20,fine-grained-tool-streaming-2025-05-14",
    "anthropic-dangerous-direct-browser-access": "true",
    "User-Agent": "claude-cli/2.1.75",
    "x-app": "cli",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# OAuth requires this system prompt prefix (from pi-ai source, buildParams)
SYSTEM_PREFIX = "You are Claude Code, Anthropic's official CLI for Claude."

DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Where Claude CLI stores credentials
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# Token refresh endpoint (from pi-ai oauth/anthropic.js)
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"


def load_oauth_token() -> dict:
    """Read OAuth credentials from Claude CLI's stored file.

    Returns dict with accessToken, refreshToken, expiresAt, subscriptionType.
    """
    if not CREDENTIALS_PATH.exists():
        raise ValueError(
            "Keine Claude-Anmeldedaten gefunden.\n"
            "Bitte zuerst mit 'claude auth login' einloggen."
        )

    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Credentials-Datei nicht lesbar: {e}")

    oauth = data.get("claudeAiOauth")
    if not oauth or not oauth.get("accessToken"):
        raise ValueError(
            "Kein OAuth-Token gefunden.\n"
            "Bitte mit 'claude auth login' einloggen."
        )

    return oauth


def is_token_expired(oauth: dict) -> bool:
    """Check if the token has expired (expiresAt is in milliseconds)."""
    expires_at = oauth.get("expiresAt", 0)
    return time.time() * 1000 > expires_at


def refresh_token(oauth: dict) -> dict:
    """Refresh an expired OAuth token using the refresh token.

    Updates the credentials file and returns the new oauth dict.
    """
    refresh = oauth.get("refreshToken")
    if not refresh:
        raise ValueError("Kein Refresh-Token vorhanden. Bitte neu einloggen.")

    logger.info("Refreshe OAuth-Token...")
    try:
        resp = requests.post(TOKEN_URL, json={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh,
        }, timeout=15, verify=_VERIFY)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise ValueError(f"Token-Refresh fehlgeschlagen: {e}")

    # Update the oauth dict
    new_oauth = dict(oauth)
    new_oauth["accessToken"] = data["access_token"]
    new_oauth["refreshToken"] = data["refresh_token"]
    # expires_in is in seconds, expiresAt in milliseconds, with 5 min buffer
    new_oauth["expiresAt"] = int((time.time() + data["expires_in"] - 300) * 1000)

    # Save back to credentials file
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
        creds["claudeAiOauth"] = new_oauth
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        logger.info("Token erfolgreich erneuert")
    except OSError as e:
        logger.warning("Konnte Credentials nicht speichern: %s", e)

    return new_oauth


def _get_valid_token() -> str:
    """Get a valid access token, refreshing if expired."""
    oauth = load_oauth_token()
    if is_token_expired(oauth):
        logger.info("Token abgelaufen, refreshe...")
        oauth = refresh_token(oauth)
    return oauth["accessToken"]


class ClaudeOAuthBackend(BaseBackend):
    """Backend that calls the Anthropic API directly using OAuth credentials.

    No proxy needed. Uses the Claude Pro/Max subscription directly.
    ~2s response time vs ~13s through the proxy.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def check_text(self, prompt: str) -> str:
        """Send prompt directly to Anthropic API using OAuth token."""
        token = _get_valid_token()

        # Build headers with OAuth token as Bearer
        headers = dict(OAUTH_HEADERS)
        headers["Authorization"] = f"Bearer {token}"

        # Build payload -- OAuth requires Claude Code system prompt
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "stream": False,
            "system": [{"type": "text", "text": SYSTEM_PREFIX}],
            "messages": [{"role": "user", "content": prompt}],
            "thinking": {"type": "disabled"},
        }

        try:
            logger.info(
                "OAuth-Anfrage: model=%s, prompt=%d zeichen",
                self.model, len(prompt),
            )
            t0 = time.time()

            response = requests.post(API_URL, json=payload, headers=headers,
                                     timeout=120, verify=_VERIFY)
            response.raise_for_status()
            data = response.json()

            # Extract text from response content blocks
            text_parts = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block["text"])

            content = "\n".join(text_parts)
            duration = time.time() - t0
            logger.info("OAuth-Antwort: %d zeichen in %.1fs", len(content), duration)

            return content

        except requests.ConnectionError:
            logger.error("Anthropic API nicht erreichbar")
            raise ConnectionError(
                "Die Anthropic API ist nicht erreichbar.\n"
                "Bitte Internetverbindung prüfen."
            )

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = ""
            try:
                body = e.response.json().get("error", {}).get("message", "")
            except Exception:
                pass

            logger.error("API-Fehler (Status %s): %s", status, body)

            if status == 401:
                raise ValueError(
                    "OAuth-Token ungültig. Bitte neu einloggen:\n"
                    "claude auth login"
                )
            if status == 429:
                raise RuntimeError("Rate-Limit erreicht. Bitte kurz warten.")

            raise RuntimeError(f"API-Fehler ({status}): {body}")

        except requests.Timeout:
            logger.warning("API-Anfrage Timeout")
            raise RuntimeError("Anfrage hat zu lange gedauert.")

    def test_connection(self) -> bool:
        """Check if OAuth credentials are valid."""
        try:
            _get_valid_token()
            return True
        except (ValueError, RuntimeError):
            return False

    def get_subscription_info(self) -> dict:
        """Return info about the current subscription."""
        try:
            oauth = load_oauth_token()
            return {
                "logged_in": True,
                "expired": is_token_expired(oauth),
                "subscription": oauth.get("subscriptionType", "unknown"),
                "tier": oauth.get("rateLimitTier", "unknown"),
            }
        except ValueError:
            return {"logged_in": False}
