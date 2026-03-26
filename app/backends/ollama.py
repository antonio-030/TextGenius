"""Ollama backend for local KI inference."""

import logging
import time
from typing import Optional

import requests

from app.backends.base import BaseBackend

logger = logging.getLogger(__name__)


class OllamaBackend(BaseBackend):
    """Backend using a local Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        # URL-Validierung: nur http/https erlaubt
        url = base_url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Ungültige Ollama URL: {url} (nur http/https erlaubt)")
        self.base_url = url
        self.model = model

    def check_text(self, prompt: str) -> str:
        """Send prompt to Ollama and return the response text.

        Uses /api/generate with stream=false for a single JSON response.
        The response text is in the 'response' field.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            logger.info("Ollama-Anfrage: model=%s, prompt=%d zeichen", self.model, len(prompt))
            t0 = time.time()

            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()

            duration = time.time() - t0
            text = data.get("response", "")
            logger.info("Ollama-Antwort: %d zeichen in %.1fs", len(text), duration)

            return text

        except requests.ConnectionError:
            logger.error("Ollama nicht erreichbar unter %s", self.base_url)
            raise ConnectionError(
                f"Ollama ist nicht erreichbar unter {self.base_url}.\n"
                "Bitte stellen Sie sicher, dass Ollama gestartet ist."
            )

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"

            # 404 = Model not found (most common user error)
            if status == 404:
                available = self.list_models()
                model_hint = ", ".join(available) if available else "keine gefunden"
                logger.error(
                    "Modell '%s' nicht gefunden. Verfügbare Modelle: %s",
                    self.model, model_hint,
                )
                raise RuntimeError(
                    f"Modell '{self.model}' ist nicht installiert.\n"
                    f"Verfügbare Modelle: {model_hint}\n\n"
                    f"Installieren mit: ollama pull {self.model}"
                )

            logger.error("Ollama HTTP-Fehler (Status %s)", status)
            raise RuntimeError(
                f"Ollama hat einen Fehler gemeldet (Status {status})."
            )

        except requests.Timeout:
            logger.warning("Ollama-Anfrage hat das Timeout überschritten")
            raise RuntimeError(
                "Die Anfrage an Ollama hat zu lange gedauert.\n"
                "Bitte versuchen Sie es erneut."
            )

    def list_models(self) -> list[str]:
        """Query Ollama for all locally installed models.

        Returns a list of model names (without :latest tag).
        Returns an empty list if Ollama is not reachable.
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            models_data = response.json().get("models", [])

            # Extract model names, strip the ':latest' tag
            names = []
            for model in models_data:
                name = model.get("name", "")
                short_name = name.split(":")[0] if name else ""
                if short_name:
                    names.append(short_name)

            logger.info("Ollama: %d Modelle gefunden: %s", len(names), names)
            return names

        except requests.ConnectionError:
            logger.warning("Ollama nicht erreichbar -- kann Modelle nicht abfragen")
            return []
        except (requests.HTTPError, requests.Timeout) as e:
            logger.warning("Fehler beim Abfragen der Modelle: %s", type(e).__name__)
            return []

    def test_connection(self) -> bool:
        """Check if Ollama is running and reachable."""
        models = self.list_models()
        return len(models) > 0 or self._ping()

    def _ping(self) -> bool:
        """Simple ping to check if Ollama server responds."""
        try:
            response = requests.get(self.base_url, timeout=5)
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False
