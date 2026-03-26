"""Abstract base class for all KI backends."""

from abc import ABC, abstractmethod


class BaseBackend(ABC):
    """Interface that every backend must implement."""

    @abstractmethod
    def check_text(self, prompt: str) -> str:
        """Send a prompt to the KI and return the raw response text.

        Args:
            prompt: The fully formatted prompt including the user text.

        Returns:
            The raw response string from the KI backend.

        Raises:
            ConnectionError: When the backend is unreachable.
            ValueError: When authentication fails (e.g. invalid API key).
            RuntimeError: For any other backend-specific error.
        """

    @abstractmethod
    def test_connection(self) -> bool:
        """Test whether the backend is reachable and configured correctly.

        Returns:
            True if connection is successful, False otherwise.
        """
