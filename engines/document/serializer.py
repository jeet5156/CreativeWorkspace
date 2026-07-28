from __future__ import annotations

from abc import ABC, abstractmethod

from .document import Document


class DocumentReader(ABC):

    @abstractmethod
    def load(self, text: str) -> Document:
        ...


class DocumentWriter(ABC):

    @abstractmethod
    def save(self, document: Document) -> str:
        ...