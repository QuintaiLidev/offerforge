from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.models import KnowledgeCard
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.services.exceptions import (
    AiScoringInvalidResponseError,
    AiScoringTimeoutError,
    AiScoringUnavailableError,
)


def _require_text_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise AiScoringInvalidResponseError(
            f"AI scoring response field '{field_name}' must be a list of strings."
        )
    return value


def parse_ai_score_payload(
    payload: dict[str, Any],
    *,
    provider: str,
) -> AnswerScoreResponse:
    dimension_scores = payload.get("dimension_scores")
    if not isinstance(dimension_scores, dict):
        raise AiScoringInvalidResponseError(
            "AI scoring response must include dimension_scores."
        )

    normalized_scores: dict[str, int] = {}
    for dimension in ANSWER_SCORE_DIMENSIONS:
        value = dimension_scores.get(dimension)
        if not isinstance(value, int) or not 0 <= value <= 10:
            raise AiScoringInvalidResponseError(
                "AI scoring response dimension_scores must include "
                f"integer 0-10 values for '{dimension}'."
            )
        normalized_scores[dimension] = value

    optimized_answer = payload.get("optimized_answer_30s")
    if not isinstance(optimized_answer, str) or not optimized_answer.strip():
        raise AiScoringInvalidResponseError(
            "AI scoring response must include optimized_answer_30s."
        )

    try:
        return AnswerScoreResponse(
            provider=provider,
            total_score=payload.get("total_score"),
            dimension_scores=normalized_scores,
            strengths=_require_text_list(payload, "strengths"),
            problems=_require_text_list(payload, "problems"),
            risk_expressions=_require_text_list(payload, "risk_expressions"),
            suggestions=_require_text_list(payload, "suggestions"),
            optimized_answer_30s=optimized_answer,
            memory_labels=_require_text_list(payload, "memory_labels"),
        )
    except ValidationError as exc:
        raise AiScoringInvalidResponseError(
            "AI scoring response failed schema validation."
        ) from exc


class OpenAIAnswerScoreProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int,
    ) -> None:
        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AuthenticationError,
                BadRequestError,
                OpenAI,
                PermissionDeniedError,
                RateLimitError,
            )
        except ImportError as exc:
            raise AiScoringUnavailableError(
                "OpenAI SDK is not installed for AI scoring."
            ) from exc

        self._authentication_error = AuthenticationError
        self._permission_denied_error = PermissionDeniedError
        self._rate_limit_error = RateLimitError
        self._bad_request_error = BadRequestError
        self._api_connection_error = APIConnectionError
        self._api_status_error = APIStatusError
        self._timeout_error = APITimeoutError
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model

    def score(
        self,
        *,
        card: KnowledgeCard,
        user_answer: str,
    ) -> AnswerScoreResponse:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an interview answer scoring assistant for "
                            "a private test-development practice app. Return "
                            "only valid JSON matching the requested schema."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(card, user_answer),
                    },
                ],
            )
        except self._timeout_error as exc:
            raise AiScoringTimeoutError("AI scoring provider timed out.") from exc
        except self._authentication_error as exc:
            raise AiScoringUnavailableError(
                "AI scoring authentication failed. Check OPENAI_API_KEY."
            ) from exc
        except self._permission_denied_error as exc:
            raise AiScoringUnavailableError(
                "AI scoring permission denied. Check project permissions."
            ) from exc
        except self._rate_limit_error as exc:
            raise AiScoringUnavailableError(
                "AI scoring rate limited or quota exceeded."
            ) from exc
        except self._bad_request_error as exc:
            raise AiScoringUnavailableError(
                "AI scoring request was rejected by provider. Check model and request format."
            ) from exc
        except self._api_connection_error as exc:
            raise AiScoringUnavailableError(
                "AI scoring provider connection failed."
            ) from exc
        except self._api_status_error as exc:
            status_code = getattr(exc, "status_code", "unknown")
            raise AiScoringUnavailableError(
                f"AI scoring provider returned status {status_code}."
            ) from exc
        except Exception as exc:
            raise AiScoringUnavailableError(
                "AI scoring provider request failed."
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise AiScoringInvalidResponseError(
                "AI scoring response did not include message content."
            ) from exc

        if not isinstance(content, str):
            raise AiScoringInvalidResponseError(
                "AI scoring response content must be text JSON."
            )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AiScoringInvalidResponseError(
                "AI scoring response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise AiScoringInvalidResponseError(
                "AI scoring response JSON must be an object."
            )

        return parse_ai_score_payload(payload, provider=self.provider_name)

    def _build_prompt(self, card: KnowledgeCard, user_answer: str) -> str:
        dimensions = ", ".join(ANSWER_SCORE_DIMENSIONS)
        return (
            "Score this interview practice answer. Use integer dimension scores "
            "from 0 to 10 and total_score from 0 to 100.\n"
            f"Required dimensions: {dimensions}.\n"
            "Return JSON with: total_score, dimension_scores, strengths, "
            "problems, risk_expressions, suggestions, optimized_answer_30s, "
            "memory_labels.\n\n"
            f"Card title: {card.title}\n"
            f"Category: {card.category.value if hasattr(card.category, 'value') else card.category}\n"
            f"Question: {card.question}\n"
            f"Core knowledge: {card.core_knowledge}\n"
            f"Reference answer: {card.reference_answer}\n\n"
            f"User answer: {user_answer}"
        )
