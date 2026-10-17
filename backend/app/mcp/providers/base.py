"""Interfaces and shared errors for legal data providers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LegalProviderError(RuntimeError):
    """A provider could not complete a legal data request."""


class LegalProvider(ABC):
    jurisdiction: str
    authority_level: str
    source_name: str

    @abstractmethod
    def search_laws(self, query: str) -> list[Dict[str, Any]]: ...

    @abstractmethod
    def get_law(self, law_name_or_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def search_regulations(self, query: str) -> list[Dict[str, Any]]: ...

    @abstractmethod
    def search_judgments(self, query: str) -> list[Dict[str, Any]]: ...

    @abstractmethod
    def get_judgment(self, judgment_id: str) -> Optional[Dict[str, Any]]: ...
