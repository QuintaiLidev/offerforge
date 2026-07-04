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


def _optional_text_list(payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _optional_text(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


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
            missing_points=_optional_text_list(payload, "missing_points"),
            complete_answer=_optional_text(payload, "complete_answer"),
            concrete_examples=_optional_text_list(payload, "concrete_examples"),
            interview_answer_60s=_optional_text(payload, "interview_answer_60s"),
            interview_answer_30s=_optional_text(payload, "interview_answer_30s"),
            follow_up_questions=_optional_text_list(payload, "follow_up_questions"),
            next_practice_step=_optional_text(payload, "next_practice_step"),
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
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
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
        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout_seconds,
        }
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers
        self._client = OpenAI(**client_kwargs)
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
                            "You are Answer Arena V0.3, a Chinese interview "
                            "answer coach for a private SDET practice app. "
                            "Return strict JSON only. Do not wrap JSON in "
                            "Markdown or code fences. Give complete, example-first "
                            "coaching, not abstract advice."
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
        category = (
            card.category.value if hasattr(card.category, "value") else str(card.category)
        )
        return (
            "请用中文评分并教练这次面试回答。Use integer dimension scores "
            "from 0 to 10 and total_score from 0 to 100.\n"
            f"Required dimensions: {dimensions}.\n"
            "Return JSON with exactly these semantic fields: total_score, "
            "dimension_scores, strengths, problems, risk_expressions, suggestions, "
            "optimized_answer_30s, memory_labels, missing_points, complete_answer, "
            "concrete_examples, interview_answer_60s, interview_answer_30s, "
            "follow_up_questions, next_practice_step.\n"
            "New coaching fields must follow these rules:\n"
            "- missing_points: list the user's most specific gaps.\n"
            "- complete_answer: give a full reference answer, not an outline. "
            "Technical answers should be at least 150 Chinese characters; project "
            "answers should be at least 180 Chinese characters; HR answers need a "
            "clear structure.\n"
            "- concrete_examples: provide 1-2 concrete examples. Technical topics "
            "must include code, SQL, CSS Selector, XPath, HTTP request, logs, test "
            "cases, pytest example, or CI pipeline where relevant.\n"
            "- interview_answer_60s: a natural one-minute answer the user can say "
            "out loud, following conclusion -> concept -> example -> project link "
            "-> risk boundary -> summary.\n"
            "- interview_answer_30s: concise spoken answer under 120 Chinese "
            "characters when possible.\n"
            "- follow_up_questions: 3 to 5 concrete interviewer follow-up questions.\n"
            "- next_practice_step: one specific next exercise action.\n\n"
            "题型专项规则：\n"
            "1. Python题：必须给 Python 代码例子。\n"
            "2. SQL题：必须给 SQL 示例。\n"
            "3. UI自动化题：必须给 CSS Selector / XPath 示例，例如 "
            "[data-testid=\"login-button\"] 或 //button[text()=\"登录\"]。\n"
            "4. 接口测试题：必须给 HTTP 请求、断言、pytest 示例或测试用例设计。\n"
            "5. 项目题：必须给真实项目表达模板，可结合服务端接口自动化工程 "
            "Python + pytest + requests + YAML + PostgreSQL + GitHub Actions + "
            "Locust，以及 login -> create_user -> get_user -> update_user_status "
            "-> db assert 链路；也可结合 api-test-gen、API 安全测试用例生成器、"
            "OfferForge，但不要编造没有依据的成果。\n"
            "6. HR题：必须给 STAR 结构：S背景、T任务、A行动、R结果。\n"
            "7. 安全测试题：必须给风险、验证方法、边界表达。\n"
            "8. 故障定位题：必须给复现 -> 请求响应 -> 日志 -> 数据库 -> 环境 "
            "-> 缩小范围 -> 验证修复。\n"
            "9. CI/Jenkins题：必须给 Jenkinsfile 或 CI pipeline 示例。\n"
            "10. 性能测试题：必须给场景、指标、瓶颈定位和结果表达。\n\n"
            f"Card title: {card.title}\n"
            f"Category: {category}\n"
            f"Question: {card.question}\n"
            f"Core knowledge: {card.core_knowledge}\n"
            f"Reference answer: {card.reference_answer}\n\n"
            f"User answer: {user_answer}"
        )


class OpenRouterAnswerScoreProvider(OpenAIAnswerScoreProvider):
    provider_name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int,
        site_url: str | None = None,
        app_title: str | None = "OfferForge",
    ) -> None:
        headers: dict[str, str] = {}
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_title:
            headers["X-OpenRouter-Title"] = app_title

        super().__init__(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=self.base_url,
            default_headers=headers or None,
        )
