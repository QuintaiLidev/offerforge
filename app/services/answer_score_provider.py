from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import ValidationError

from app.models import KnowledgeCard
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.services.candidate_profile import CANDIDATE_ANSWER_RULES, CANDIDATE_PROFILE
from app.services.exceptions import (
    AiScoringInvalidResponseError,
    AiScoringTimeoutError,
    AiScoringUnavailableError,
)

ScoringDepth = Literal["quick", "deep"]


TEXT_KEYS = ("text", "content", "value", "answer", "description")
QUESTION_KEYS = ("question", "q")
ANSWER_KEYS = ("answer", "a")


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _first_text_value(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in value:
            text = _coerce_text(value[key])
            if text:
                return text
    return ""


def _coerce_qa_text(value: dict[str, Any]) -> str:
    question = _first_text_value(value, QUESTION_KEYS)
    answer = _first_text_value(value, ANSWER_KEYS)
    if question and answer:
        return f"Q：{question}\nA：{answer}"
    if question:
        return f"Q：{question}"
    if answer:
        return f"A：{answer}"
    return ""


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(
            text for item in value if (text := _coerce_text(item))
        ).strip()
    if isinstance(value, dict):
        qa_text = _coerce_qa_text(value)
        if qa_text:
            return qa_text
        for key in TEXT_KEYS:
            if key in value:
                text = _coerce_text(value[key])
                if text:
                    return text
        return _dump_json(value)
    return str(value).strip()


def _coerce_text_list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [
            text for item in value if (text := _coerce_text(item))
        ]
    if isinstance(value, dict):
        if "value" in value:
            nested = value["value"]
            if isinstance(nested, list):
                return _coerce_text_list_value(nested)
            text = _coerce_text(nested)
            return [text] if text else []
        text = _coerce_text(value)
        return [text] if text else []
    text = _coerce_text(value)
    return [text] if text else []


def _coerce_text_list(payload: dict[str, Any], field_name: str) -> list[str]:
    return _coerce_text_list_value(payload.get(field_name))


def _coerce_text_field(payload: dict[str, Any], field_name: str) -> str:
    return _coerce_text(payload.get(field_name))


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return max(minimum, min(maximum, int(round(number))))


def parse_ai_score_payload(
    payload: dict[str, Any],
    *,
    provider: str,
) -> AnswerScoreResponse:
    dimension_scores = payload.get("dimension_scores")
    if not isinstance(dimension_scores, dict):
        dimension_scores = {}

    normalized_scores: dict[str, int] = {}
    for dimension in ANSWER_SCORE_DIMENSIONS:
        normalized_scores[dimension] = _coerce_int(
            dimension_scores.get(dimension),
            default=0,
            minimum=0,
            maximum=10,
        )

    try:
        return AnswerScoreResponse(
            provider=provider,
            total_score=_coerce_int(
                payload.get("total_score"),
                default=0,
                minimum=0,
                maximum=100,
            ),
            dimension_scores=normalized_scores,
            strengths=_coerce_text_list(payload, "strengths"),
            problems=_coerce_text_list(payload, "problems"),
            risk_expressions=_coerce_text_list(payload, "risk_expressions"),
            suggestions=_coerce_text_list(payload, "suggestions"),
            optimized_answer_30s=_coerce_text_field(payload, "optimized_answer_30s"),
            memory_labels=_coerce_text_list(payload, "memory_labels"),
            missing_points=_coerce_text_list(payload, "missing_points"),
            complete_answer=_coerce_text_field(payload, "complete_answer"),
            concrete_examples=_coerce_text_list(payload, "concrete_examples"),
            interview_answer_60s=_coerce_text_field(payload, "interview_answer_60s"),
            interview_answer_30s=_coerce_text_field(payload, "interview_answer_30s"),
            follow_up_questions=_coerce_text_list(payload, "follow_up_questions"),
            follow_up_qas=_coerce_text_list(payload, "follow_up_qas"),
            next_practice_step=_coerce_text_field(payload, "next_practice_step"),
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
        depth: ScoringDepth = "quick",
    ) -> AnswerScoreResponse:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Answer Arena V0.4, a candidate-aware Chinese interview "
                            "answer coach for a private SDET practice app. "
                            "Return strict JSON only. Do not wrap JSON in "
                            "Markdown or code fences. Give complete, example-first "
                            "coaching, not abstract advice. Always respect the candidate "
                            "profile and do not package the user as a Java backend or "
                            "algorithm expert."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(
                            card,
                            user_answer,
                            depth=depth,
                        ),
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

    def _build_prompt(
        self,
        card: KnowledgeCard,
        user_answer: str,
        *,
        depth: ScoringDepth = "quick",
    ) -> str:
        dimensions = ", ".join(ANSWER_SCORE_DIMENSIONS)
        category = (
            card.category.value if hasattr(card.category, "value") else str(card.category)
        )
        if depth == "deep":
            depth_rules = (
                "Depth: ai_deep / 深度教练。\n"
                "Keep V0.3 full coaching ability.\n"
                "- complete_answer: 180-350 Chinese characters.\n"
                "- concrete_examples: 1-2 key examples with code, SQL, selector, HTTP, pytest, project template, or STAR where relevant.\n"
                "- interview_answer_60s: 180-260 Chinese characters.\n"
                "- interview_answer_30s: 80-120 Chinese characters.\n"
                "- follow_up_questions: exactly 3.\n"
                "- follow_up_qas: exactly 3, each with Q and A; answer length 60-120 Chinese characters.\n"
                "- next_practice_step: one specific next action.\n"
            )
        else:
            depth_rules = (
                "Depth: ai_quick / AI快评。\n"
                "Output should be fast, short, concrete, and suitable for daily drilling.\n"
                "- complete_answer: empty or within 120-180 Chinese characters.\n"
                "- concrete_examples: exactly 1 key example.\n"
                "- interview_answer_60s: empty or brief.\n"
                "- interview_answer_30s: 80-120 Chinese characters.\n"
                "- follow_up_questions: derive from follow_up_qas if useful.\n"
                "- follow_up_qas: exactly 2, each with Q and A; answer length 60-120 Chinese characters.\n"
                "- Do not produce a long report.\n"
            )
        return (
            "请用中文评分并教练这次面试回答。Use integer dimension scores "
            "from 0 to 10 and total_score from 0 to 100.\n"
            f"Required dimensions: {dimensions}.\n"
            f"{CANDIDATE_PROFILE}\n\n"
            f"{CANDIDATE_ANSWER_RULES}\n\n"
            f"{depth_rules}\n"
            "Return JSON with exactly these semantic fields: total_score, "
            "dimension_scores, strengths, problems, risk_expressions, suggestions, "
            "optimized_answer_30s, memory_labels, missing_points, complete_answer, "
            "concrete_examples, interview_answer_60s, interview_answer_30s, "
            "follow_up_questions, follow_up_qas, next_practice_step.\n"
            "Use string arrays for strengths, problems, risk_expressions, "
            "suggestions, memory_labels, missing_points, concrete_examples, "
            "follow_up_questions, and follow_up_qas.\n"
            "New coaching fields must follow these rules:\n"
            "- missing_points: list the user's most specific gaps.\n"
            "- complete_answer: give a direct answer when requested by depth rules, not an outline.\n"
            "- concrete_examples: provide key concrete examples. Technical topics "
            "must include code, SQL, CSS Selector, XPath, HTTP request, logs, test "
            "cases, pytest example, or CI pipeline where relevant.\n"
            "- interview_answer_60s: a natural answer the user can say out loud.\n"
            "- interview_answer_30s: concise spoken answer, ideally 80-120 Chinese characters.\n"
            "- follow_up_questions: concrete interviewer follow-up questions.\n"
            "- follow_up_qas: strings. Each string must contain one Q and "
            "one A. Format: Q：question\\nA：short Chinese answer. The "
            "answer must be specific and directly speakable.\n"
            "- next_practice_step: one specific next exercise action.\n\n"
            "偏开发题候选人画像处理：\n"
            "When the topic is Java backend, multithreading, JVM, Spring, algorithm, "
            "or deep framework internals, do not package the user as a Java backend "
            "developer. Use this structure: 1) basic correct concept, 2) honest "
            "candidate boundary, 3) test-development angle, 4) speakable version. "
            "The answer must include 测试开发视角 such as concurrent API testing, "
            "load testing, data consistency, debugging, automation framework, logs, "
            "database assertions, or CI.\n\n"
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
