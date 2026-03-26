"""Claude API backend using the official Anthropic SDK."""

import logging
import time

import anthropic

from app.backends.base import BaseBackend

logger = logging.getLogger(__name__)

# Default model to use
DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeBackend(BaseBackend):
    """Backend that sends requests directly to the Anthropic API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    def check_text(self, prompt: str) -> str:
        """Send prompt to Claude API and return the response text."""
        try:
            logger.info("Claude API-Anfrage: model=%s, prompt=%d zeichen", self.model, len(prompt))
            t0 = time.time()

            message = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            if not message.content:
                raise RuntimeError("Claude API hat keine Antwort gegeben.")
            text = message.content[0].text

            duration = time.time() - t0
            logger.info("Claude API-Antwort: %d zeichen in %.1fs", len(text), duration)

            return text

        except anthropic.AuthenticationError:
            logger.error("Claude API: Ungültiger API-Key")
            raise ValueError(
                "Der Claude API-Key ist ungültig.\n"
                "Bitte prüfen Sie den Key in den Einstellungen."
            )

        except anthropic.RateLimitError:
            logger.warning("Claude API: Rate-Limit erreicht")
            raise RuntimeError(
                "Claude API Rate-Limit erreicht.\n"
                "Bitte warten Sie einen Moment und versuchen Sie es erneut."
            )

        except anthropic.APIConnectionError:
            logger.error("Claude API nicht erreichbar")
            raise ConnectionError(
                "Die Claude API ist nicht erreichbar.\n"
                "Bitte prüfen Sie Ihre Internetverbindung."
            )

        except anthropic.APIError as e:
            logger.error("Claude API-Fehler: %s", e.message)
            raise RuntimeError(f"Claude API-Fehler: {e.message}")

    def test_connection(self) -> bool:
        """Test if the API key is valid by sending a minimal request."""
        try:
            self._client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False
