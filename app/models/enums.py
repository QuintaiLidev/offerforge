from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SQLAlchemyEnum


class KnowledgeCategory(str, Enum):
    PYTHON = "python"
    SQL = "sql"
    HTTP_API_TESTING = "http_api_testing"
    PYTEST = "pytest"
    XPATH_CSS_SELECTOR = "xpath_css_selector"
    SELENIUM = "selenium"
    LINUX_GIT_CI = "linux_git_ci"
    PROJECT_EXPLANATION = "project_explanation"
    SELF_INTRODUCTION = "self_introduction"
    REAL_BUSINESS_CASE = "real_business_case"
    HR_INTERVIEW = "hr_interview"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MasteryLevel(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    FAMILIAR = "familiar"
    PROFICIENT = "proficient"
    MASTERED = "mastered"


class QuestionType(str, Enum):
    KNOWLEDGE = "knowledge"
    PYTHON_CODE = "python_code"
    SQL = "sql"
    XPATH = "xpath"
    SUBJECTIVE = "subjective"


class PracticeRating(str, Enum):
    DONT_KNOW = "dont_know"
    WITH_HINT = "with_hint"
    CORRECT_SLOW = "correct_slow"
    CORRECT_EXPLAIN = "correct_explain"
    TRANSFER = "transfer"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


def mapped_enum(enum_class: type[Enum], name: str) -> SQLAlchemyEnum:
    return SQLAlchemyEnum(
        enum_class,
        values_callable=enum_values,
        native_enum=False,
        validate_strings=True,
        create_constraint=True,
        name=name,
    )
