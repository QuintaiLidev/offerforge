from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import KnowledgeCard
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate, KnowledgeCardUpdate
from app.services import (
    DuplicateKnowledgeCardError,
    KnowledgeCardNotFoundError,
    KnowledgeCardService,
    ServiceError,
)


def make_card(
    *,
    card_id: int = 1,
    title: str = "Python list comprehension",
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
) -> KnowledgeCard:
    card = KnowledgeCard(
        title=title,
        category=category,
        core_knowledge=f"Core knowledge for {title}",
        question=f"Question about {title}",
        reference_answer=f"Reference answer for {title}",
    )
    card.id = card_id
    return card


def make_card_create(
    *,
    title: str = "Python list comprehension",
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    **overrides: Any,
) -> KnowledgeCardCreate:
    payload: dict[str, Any] = {
        "title": title,
        "category": category,
        "core_knowledge": f"Core knowledge for {title}",
        "question": f"Question about {title}",
        "reference_answer": f"Reference answer for {title}",
    }
    payload.update(overrides)
    return KnowledgeCardCreate(**payload)


def make_repository_mock() -> Mock:
    return Mock(spec=KnowledgeCardRepository)


def make_integrity_error() -> IntegrityError:
    return IntegrityError("statement", {"title": "duplicate"}, Exception("unique"))


def test_create_card_calls_repository_when_no_duplicate() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    data = make_card_create()
    card = make_card()
    repository.exists_by_category_and_title.return_value = False
    repository.create.return_value = card

    result = service.create_card(data)

    assert result == card
    repository.exists_by_category_and_title.assert_called_once_with(
        KnowledgeCategory.PYTHON,
        "Python list comprehension",
    )
    repository.create.assert_called_once_with(data)


def test_create_card_rejects_preexisting_duplicate() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    data = make_card_create()
    repository.exists_by_category_and_title.return_value = True

    with pytest.raises(DuplicateKnowledgeCardError) as exc_info:
        service.create_card(data)

    assert exc_info.value.category is KnowledgeCategory.PYTHON
    assert exc_info.value.title == "Python list comprehension"
    repository.create.assert_not_called()


def test_create_card_converts_integrity_error_and_keeps_cause() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    data = make_card_create()
    integrity_error = make_integrity_error()
    repository.exists_by_category_and_title.return_value = False
    repository.create.side_effect = integrity_error

    with pytest.raises(DuplicateKnowledgeCardError) as exc_info:
        service.create_card(data)

    assert exc_info.value.__cause__ is integrity_error
    assert exc_info.value.category is KnowledgeCategory.PYTHON
    assert exc_info.value.title == "Python list comprehension"


def test_create_card_does_not_swallow_unrelated_exceptions() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    data = make_card_create()
    unrelated_error = RuntimeError("database is unavailable")
    repository.exists_by_category_and_title.return_value = False
    repository.create.side_effect = unrelated_error

    with pytest.raises(RuntimeError) as exc_info:
        service.create_card(data)

    assert exc_info.value is unrelated_error


def test_get_card_returns_existing_card() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=123)
    repository.get_by_id.return_value = card

    result = service.get_card(123)

    assert result == card
    repository.get_by_id.assert_called_once_with(123)


def test_get_card_raises_not_found_with_card_id() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    repository.get_by_id.return_value = None

    with pytest.raises(KnowledgeCardNotFoundError) as exc_info:
        service.get_card(123)

    assert exc_info.value.card_id == 123
    assert str(exc_info.value) == "Knowledge card 123 was not found."


def test_list_cards_passes_filters_and_returns_repository_result() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    returned_items = [make_card(card_id=1), make_card(card_id=2)]
    repository.list.return_value = (returned_items, 10)

    result = service.list_cards(
        offset=5,
        limit=10,
        category=KnowledgeCategory.SQL,
        difficulty=DifficultyLevel.HARD,
        mastery_level=MasteryLevel.FAMILIAR,
        question_type=QuestionType.SQL,
        is_active=True,
        keyword=" join ",
    )

    assert result == (returned_items, 10)
    repository.list.assert_called_once_with(
        offset=5,
        limit=10,
        category=KnowledgeCategory.SQL,
        difficulty=DifficultyLevel.HARD,
        mastery_level=MasteryLevel.FAMILIAR,
        question_type=QuestionType.SQL,
        is_active=True,
        keyword=" join ",
    )


@pytest.mark.parametrize(
    ("offset", "limit"),
    [(-1, 20), (0, 0), (0, -1), (0, 101)],
)
def test_list_cards_rejects_invalid_pagination(
    offset: int,
    limit: int,
) -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)

    with pytest.raises(ValueError):
        service.list_cards(offset=offset, limit=limit)

    repository.list.assert_not_called()


def test_update_card_raises_not_found_when_card_missing() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    repository.get_by_id.return_value = None

    with pytest.raises(KnowledgeCardNotFoundError):
        service.update_card(404, KnowledgeCardUpdate(title="New title"))

    repository.update.assert_not_called()


def test_update_card_updates_plain_fields_without_duplicate_check() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card()
    updated = make_card(title="Python list comprehension")
    updated.difficulty = DifficultyLevel.HARD
    repository.get_by_id.return_value = card
    repository.update.return_value = updated
    data = KnowledgeCardUpdate(difficulty=DifficultyLevel.HARD)

    result = service.update_card(card.id, data)

    assert result == updated
    repository.exists_by_category_and_title.assert_not_called()
    repository.update.assert_called_once_with(card, data)


def test_update_card_checks_duplicate_when_title_changes() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=7, title="Old title")
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = False
    repository.update.return_value = card
    data = KnowledgeCardUpdate(title="New title")

    service.update_card(card.id, data)

    repository.exists_by_category_and_title.assert_called_once_with(
        KnowledgeCategory.PYTHON,
        "New title",
        exclude_id=7,
    )


def test_update_card_checks_duplicate_when_category_changes() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=8, title="Same title", category=KnowledgeCategory.PYTHON)
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = False
    repository.update.return_value = card
    data = KnowledgeCardUpdate(category=KnowledgeCategory.SQL)

    service.update_card(card.id, data)

    repository.exists_by_category_and_title.assert_called_once_with(
        KnowledgeCategory.SQL,
        "Same title",
        exclude_id=8,
    )


def test_update_card_checks_duplicate_with_final_title_and_category() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=9, title="Old title", category=KnowledgeCategory.PYTHON)
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = False
    repository.update.return_value = card
    data = KnowledgeCardUpdate(
        title="Final title",
        category=KnowledgeCategory.SQL,
    )

    service.update_card(card.id, data)

    repository.exists_by_category_and_title.assert_called_once_with(
        KnowledgeCategory.SQL,
        "Final title",
        exclude_id=9,
    )


def test_update_card_rejects_duplicate_and_does_not_update() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=10)
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = True

    with pytest.raises(DuplicateKnowledgeCardError) as exc_info:
        service.update_card(card.id, KnowledgeCardUpdate(title="Existing title"))

    assert exc_info.value.category is KnowledgeCategory.PYTHON
    assert exc_info.value.title == "Existing title"
    repository.update.assert_not_called()


def test_update_card_does_not_misjudge_current_title_as_duplicate() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=11, title="Same title")
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = False
    repository.update.return_value = card
    data = KnowledgeCardUpdate(title="Same title")

    result = service.update_card(card.id, data)

    assert result == card
    repository.exists_by_category_and_title.assert_called_once_with(
        KnowledgeCategory.PYTHON,
        "Same title",
        exclude_id=11,
    )
    repository.update.assert_called_once_with(card, data)


def test_update_card_converts_integrity_error_and_keeps_cause() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=12)
    integrity_error = make_integrity_error()
    repository.get_by_id.return_value = card
    repository.exists_by_category_and_title.return_value = False
    repository.update.side_effect = integrity_error
    data = KnowledgeCardUpdate(title="Race duplicate")

    with pytest.raises(DuplicateKnowledgeCardError) as exc_info:
        service.update_card(card.id, data)

    assert exc_info.value.__cause__ is integrity_error
    assert exc_info.value.category is KnowledgeCategory.PYTHON
    assert exc_info.value.title == "Race duplicate"


def test_update_card_does_not_swallow_unrelated_exceptions() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=13)
    unrelated_error = RuntimeError("write failed")
    repository.get_by_id.return_value = card
    repository.update.side_effect = unrelated_error

    with pytest.raises(RuntimeError) as exc_info:
        service.update_card(card.id, KnowledgeCardUpdate(difficulty=DifficultyLevel.HARD))

    assert exc_info.value is unrelated_error


def test_delete_card_calls_repository_delete_when_card_exists() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    card = make_card(card_id=14)
    repository.get_by_id.return_value = card

    service.delete_card(14)

    repository.delete.assert_called_once_with(card)


def test_delete_card_raises_not_found_and_does_not_delete() -> None:
    repository = make_repository_mock()
    service = KnowledgeCardService(repository)
    repository.get_by_id.return_value = None

    with pytest.raises(KnowledgeCardNotFoundError) as exc_info:
        service.delete_card(404)

    assert exc_info.value.card_id == 404
    repository.delete.assert_not_called()


def test_service_exceptions_keep_context_and_clear_messages() -> None:
    not_found = KnowledgeCardNotFoundError(123)
    duplicate = DuplicateKnowledgeCardError(
        KnowledgeCategory.PYTHON,
        "Python list comprehension",
    )

    assert isinstance(not_found, ServiceError)
    assert not_found.card_id == 123
    assert str(not_found) == "Knowledge card 123 was not found."
    assert isinstance(duplicate, ServiceError)
    assert duplicate.category is KnowledgeCategory.PYTHON
    assert duplicate.title == "Python list comprehension"
    assert (
        str(duplicate)
        == "A knowledge card titled 'Python list comprehension' "
        "already exists in category 'python'."
    )
    assert not hasattr(not_found, "status_code")
    assert not hasattr(duplicate, "status_code")
