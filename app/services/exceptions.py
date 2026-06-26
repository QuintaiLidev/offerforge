from __future__ import annotations

from app.models.enums import KnowledgeCategory


class ServiceError(Exception):
    """Base exception for service-layer errors."""


class KnowledgeCardNotFoundError(ServiceError):
    def __init__(self, card_id: int) -> None:
        self.card_id = card_id
        super().__init__(f"Knowledge card {card_id} was not found.")


class DuplicateKnowledgeCardError(ServiceError):
    def __init__(self, category: KnowledgeCategory, title: str) -> None:
        self.category = category
        self.title = title
        super().__init__(
            "A knowledge card titled "
            f"'{title}' already exists in category '{category.value}'."
        )
