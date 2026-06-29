from __future__ import annotations

from app.models.enums import KnowledgeCategory


class ServiceError(Exception):
    """Base exception for service-layer errors."""


class KnowledgeCardNotFoundError(ServiceError):
    def __init__(self, card_id: int) -> None:
        self.card_id = card_id
        super().__init__(f"Knowledge card {card_id} was not found.")


class KnowledgeCardSourceNotFoundError(ServiceError):
    def __init__(self, source_reference: str) -> None:
        self.source_reference = source_reference
        super().__init__(
            f"Knowledge card source '{source_reference}' was not found."
        )


class KnowledgeCardSourceHasAttemptsError(ServiceError):
    def __init__(self, source_reference: str) -> None:
        self.source_reference = source_reference
        super().__init__(
            "Cannot delete source_reference because practice attempts exist "
            "for these cards."
        )


class DuplicateKnowledgeCardError(ServiceError):
    def __init__(
        self,
        category: KnowledgeCategory,
        title: str,
        source_reference: str | None = None,
    ) -> None:
        self.category = category
        self.title = title
        self.source_reference = source_reference
        if source_reference is None:
            message = (
                "A knowledge card titled "
                f"'{title}' already exists in category '{category.value}'."
            )
        else:
            message = (
                "A knowledge card titled "
                f"'{title}' already exists in source_reference "
                f"'{source_reference}' and category '{category.value}'."
            )
        super().__init__(message)
