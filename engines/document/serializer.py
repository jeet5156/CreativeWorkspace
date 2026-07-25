from __future__ import annotations

from abc import ABC, abstractmethod

from .document import Document


class DocumentReader(ABC):
    """Base class for all document readers."""

    @abstractmethod
    def load(self, text: str) -> Document:
        pass


class DocumentWriter(ABC):
    """Base class for all document writers."""

    @abstractmethod
    def save(self, document: Document) -> str:
        pass