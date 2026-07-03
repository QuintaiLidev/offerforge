from __future__ import annotations

import json
import re
from socket import timeout as SocketTimeout
from typing import Any, Protocol

from app.models import KnowledgeCard
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.services.exceptions import KnowledgeCardNotFoundError

STRUCTURE_KEYWORDS = ("首先", "第一", "第二", "比如", "举个例子", "最后", "所以", "我的理解是", "我负责", "我会先")
EXAMPLE_KEYWORDS = ("项目", "接口", "自动化", "CI", "SQL", "数据库", "权限", "线上", "缺陷", "回归", "工具", "维护", "定位")
GENERAL_RISKS = ("AI 写了 80%", "主要都是 AI 写的", "我让 AI 做", "我不太清楚", "我只是录制脚本", "跑一下脚本", "改一下 XPath", "我就是想做 Python 自动化", "外包没发展", "公司做不了", "差不多吧", "反正就是", "然后然后")
UI_POSITIVE = ("录制初稿", "定位优化", "XPath", "稳定属性", "等待处理", "断言", "维护", "稳定性", "可维护性")
UI_RISK = ("只是录制", "跑一下", "改一下 XPath")
AI_POSITIVE = ("提效工具", "初稿", "需求拆解", "代码阅读", "调试验证", "测试回归", "质量责任", "我负责验证")
AI_RISK = ("AI 写了 80%", "主要都是 AI 写的", "我让 AI 做")
CAREER_POSITIVE = ("测试开发", "技术化质量保障", "工具化提效", "懂业务", "懂测试", "自动化", "CI", "数据校验")
CAREER_RISK = ("想做 Python 自动化", "外包没发展", "公司做不了")
BOUNDARY_KEYWORDS = ("边界", "如实", "不是替代", "我负责验证", "质量责任", "不夸大", "风险", "人工", "校验", "验证")
PROFESSIONAL_KEYWORDS = ("质量", "稳定", "闭环", "复盘", "链路", "场景", "数据", "风险", "验证", "落地")


class AIScoringError(Exception):
    """Base exception for optional AI scoring failures."""


class AIScoringNotConfiguredError(AIScoringError):
    """Raised when AI scoring is requested without an API key."""


class AIScoringTimeoutError(AIScoringError):
    """Raised when the AI scoring provider times out."""


class AIScoringUnavailableError(AIScoringError):
    """Raised when the AI scoring provider fails or returns invalid data."""


class AnswerScoringProvider(Protocol):
    provider_name: str

    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        """Return a structured answer score."""


def _contains_any(text: str, keywords: tuple[str, ...]) -> list[str]:
    lower_text = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lower_text]


def _clamp(score: int) -> int:
    return max(0, min(10, score))


def _card_text(card: KnowledgeCard) -> str:
    return " ".join(
        [
            card.title,
            card.category.value if hasattr(card.category, "value") else str(card.category),
            card.reference_answer,
            " ".join(card.tags or []),
        ]
    ).lower()


def _is_ui_card(card: KnowledgeCard) -> bool:
    text = _card_text(card)
    return card.category == KnowledgeCategory.SELENIUM or any(k.lower() in text for k in ("ui", "selenium", "xpath", "元素定位", "自动化"))


def _is_ai_card(card: KnowledgeCard) -> bool:
    text = _card_text(card)
    return any(k.lower() in text for k in ("ai", "cursor", "skills", "代码", "工具"))


def _is_career_card(card: KnowledgeCard) -> bool:
    text = _card_text(card)
    return card.category == KnowledgeCategory.HR_INTERVIEW or any(k.lower() in text for k in ("职业", "岗位", "入职", "方向", "负责人"))


def _extract_optimized_answer(reference_answer: str) -> str:
    text = reference_answer.strip()
    match = re.search(r"【30秒(?:口述|口述版)?】(?P<answer>.*?)(?:\n【|$)", text, flags=re.S)
    if match:
        return match.group("answer").strip()
    first_line = text.splitlines()[0].strip() if text else ""
    return first_line[:240] or "建议先用一句结论正面回答，再补两个要点、一个例子和一句收尾。"


def _normalize_score_response(data: dict[str, Any], *, provider: str) -> AnswerScoreResponse:
    dimension_scores = data.get("dimension_scores")
    if not isinstance(dimension_scores, dict):
        raise AIScoringUnavailableError("AI scoring returned invalid dimension_scores.")

    normalized_dimensions: dict[str, int] = {}
    for dimension in ANSWER_SCORE_DIMENSIONS:
        value = dimension_scores.get(dimension)
        if not isinstance(value, int) or value < 0 or value > 10:
            raise AIScoringUnavailableError("AI scoring returned invalid dimension score.")
        normalized_dimensions[dimension] = value

    total_score = data.get("total_score")
    if not isinstance(total_score, int) or total_score < 0 or total_score > 100:
        raise AIScoringUnavailableError("AI scoring returned invalid total_score.")

    def list_of_strings(field: str, *, min_items: int = 0, max_items: int = 8) -> list[str]:
        value = data.get(field)
        if not isinstance(value, list):
            raise AIScoringUnavailableError(f"AI scoring returned invalid {field}.")
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(items) < min_items or len(items) > max_items:
            raise AIScoringUnavailableError(f"AI scoring returned invalid {field} length.")
        return items

    optimized = data.get("optimized_answer_30s")
    if not isinstance(optimized, str) or not optimized.strip():
        raise AIScoringUnavailableError("AI scoring returned invalid optimized_answer_30s.")

    return AnswerScoreResponse(
        total_score=total_score,
        dimension_scores=normalized_dimensions,
        strengths=list_of_strings("strengths", min_items=1, max_items=5),
        problems=list_of_strings("problems", min_items=1, max_items=5),
        risk_expressions=list_of_strings("risk_expressions", min_items=0, max_items=8),
        suggestions=list_of_strings("suggestions", min_items=1, max_items=5),
        optimized_answer_30s=optimized.strip(),
        memory_labels=list_of_strings("memory_labels", min_items=3, max_items=8),
        provider=provider,
    )


class RuleAnswerScoringProvider:
    provider_name = "rule"

    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        answer = user_answer.strip()
        structure_hits = _contains_any(answer, STRUCTURE_KEYWORDS)
        example_hits = _contains_any(answer, EXAMPLE_KEYWORDS)
        boundary_hits = _contains_any(answer, BOUNDARY_KEYWORDS)
        professional_hits = _contains_any(answer, PROFESSIONAL_KEYWORDS)
        risks = _contains_any(answer, GENERAL_RISKS)
        context_positive: list[str] = []

        if _is_ui_card(card):
            context_positive += _contains_any(answer, UI_POSITIVE)
            risks += [risk for risk in _contains_any(answer, UI_RISK) if risk not in risks]
        if _is_ai_card(card):
            context_positive += _contains_any(answer, AI_POSITIVE)
            risks += [risk for risk in _contains_any(answer, AI_RISK) if risk not in risks]
        if _is_career_card(card):
            context_positive += _contains_any(answer, CAREER_POSITIVE)
            risks += [risk for risk in _contains_any(answer, CAREER_RISK) if risk not in risks]

        length_bonus = 0 if len(answer) < 30 else 1 if len(answer) < 80 else 2
        length_penalty = 3 if len(answer) < 30 else 1 if len(answer) < 80 else 0
        risk_penalty = min(5, len(risks) * 2)

        scores = {
            "direct_answer": _clamp(5 + length_bonus + min(2, len(structure_hits)) - length_penalty),
            "structure": _clamp(4 + min(4, len(structure_hits)) + (1 if "最后" in structure_hits or "所以" in structure_hits else 0) - length_penalty),
            "real_example": _clamp(3 + min(5, len(example_hits)) + (1 if any(k in structure_hits for k in ("比如", "举个例子")) else 0)),
            "job_match": _clamp(4 + min(4, len(context_positive)) + (1 if example_hits else 0)),
            "boundary": _clamp(5 + min(3, len(boundary_hits)) - max(0, risk_penalty - 1)),
            "professional_expression": _clamp(5 + min(3, len(professional_hits)) + (1 if context_positive else 0) - min(3, len(risks))),
            "risk_control": _clamp(8 - risk_penalty + min(2, len(boundary_hits))),
        }
        total = round(sum(scores.values()) / (len(ANSWER_SCORE_DIMENSIONS) * 10) * 100)

        strengths = []
        if structure_hits:
            strengths.append("回答中有结构词，能帮助面试官跟上表达顺序。")
        if example_hits:
            strengths.append("回答包含项目、接口、权限、数据或回归等真实场景词。")
        if context_positive:
            strengths.append("回答命中了当前题型的岗位匹配关键词。")
        if not strengths:
            strengths.append("已经开始组织自己的答案，可以继续补结构和案例。")

        problems = []
        if len(answer) < 80:
            problems.append("回答偏短，建议补充两个要点和一个具体例子。")
        if not structure_hits:
            problems.append("结构不够明显，建议使用“先说结论、第一、第二、比如、最后”。")
        if not example_hits:
            problems.append("真实案例不足，建议补充项目、接口、权限、缺陷或回归经历。")
        if risks:
            problems.append("存在容易削弱专业度或边界感的风险表达。")

        suggestions = [
            "按“一句结论 → 两个要点 → 一个例子 → 一句收尾”重答一遍。",
            "把 AI、工具或外部平台表述为提效手段，质量责任仍由自己承担。",
            "补充可验证动作，例如断言、日志、数据库、回归、上线风险确认。",
        ]

        memory_labels = ["结论先行", "两点一例", "边界感", "质量闭环"]
        if context_positive:
            memory_labels.append("岗位匹配")
        if risks:
            memory_labels.append("风险话术")

        return AnswerScoreResponse(
            total_score=total,
            dimension_scores={dimension: scores[dimension] for dimension in ANSWER_SCORE_DIMENSIONS},
            strengths=strengths,
            problems=problems,
            risk_expressions=risks,
            suggestions=suggestions,
            optimized_answer_30s=_extract_optimized_answer(card.reference_answer),
            memory_labels=memory_labels,
            provider=self.provider_name,
        )


class OpenAIAnswerScoringProvider:
    provider_name = "openai"

    def __init__(self, *, api_key: str | None, model: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        if not self.api_key:
            raise AIScoringNotConfiguredError("AI scoring is not configured. Set OPENAI_API_KEY.")

        try:
            raw = self._request_score(card=card, user_answer=user_answer)
        except (TimeoutError, SocketTimeout) as exc:
            raise AIScoringTimeoutError("AI scoring timed out.") from exc
        except AIScoringError:
            raise
        except Exception as exc:
            raise AIScoringUnavailableError("AI scoring service is unavailable.") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIScoringUnavailableError("AI scoring returned invalid JSON.") from exc
        return _normalize_score_response(data, provider=self.provider_name)

    def _request_score(self, *, card: KnowledgeCard, user_answer: str) -> str:
        try:
            from openai import APIConnectionError, APITimeoutError, OpenAI
        except ImportError as exc:
            raise AIScoringUnavailableError("OpenAI SDK is not installed.") from exc

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _ai_system_prompt()},
                    {"role": "user", "content": _ai_user_prompt(card=card, user_answer=user_answer)},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except APITimeoutError as exc:
            raise AIScoringTimeoutError("AI scoring timed out.") from exc
        except APIConnectionError as exc:
            raise AIScoringUnavailableError("AI scoring service is unavailable.") from exc

        content = response.choices[0].message.content
        if not content:
            raise AIScoringUnavailableError("AI scoring returned an empty response.")
        return content


def _ai_system_prompt() -> str:
    dimensions = "、".join(ANSWER_SCORE_DIMENSIONS)
    risks = "、".join(GENERAL_RISKS)
    return (
        "你是 OfferForge 的中文技术面试答题评分器。只返回严格 JSON，不要 Markdown。"
        f"固定 7 个评分维度是：{dimensions}。每项 0 到 10 分，总分 0 到 100。"
        f"重点识别这些风险表达：{risks}。"
        "输出字段必须包含 total_score、dimension_scores、strengths、problems、risk_expressions、"
        "suggestions、optimized_answer_30s、memory_labels。"
        "strengths/problems/suggestions 各 1 到 5 条，risk_expressions 可为空，memory_labels 3 到 8 个短标签。"
    )


def _ai_user_prompt(*, card: KnowledgeCard, user_answer: str) -> str:
    payload = {
        "card": {
            "title": card.title,
            "category": card.category.value if hasattr(card.category, "value") else str(card.category),
            "question": card.question,
            "core_knowledge": card.core_knowledge,
            "reference_answer": card.reference_answer,
            "tags": card.tags or [],
        },
        "user_answer": user_answer,
    }
    return json.dumps(payload, ensure_ascii=False)


class AnswerArenaService:
    def __init__(
        self,
        card_repository: KnowledgeCardRepository,
        *,
        rule_provider: AnswerScoringProvider | None = None,
        ai_provider: AnswerScoringProvider | None = None,
    ) -> None:
        self.card_repository = card_repository
        self.rule_provider = rule_provider or RuleAnswerScoringProvider()
        self.ai_provider = ai_provider

    def score_answer(
        self,
        *,
        card_id: int,
        user_answer: str,
        mode: str = "rule",
    ) -> AnswerScoreResponse:
        card = self.card_repository.get_by_id(card_id)
        if card is None:
            raise KnowledgeCardNotFoundError(card_id)

        provider = self.rule_provider if mode == "rule" else self.ai_provider
        if provider is None:
            raise AIScoringNotConfiguredError("AI scoring is not configured.")
        return provider.score(card=card, user_answer=user_answer)
