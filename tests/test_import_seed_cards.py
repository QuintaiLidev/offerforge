from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import import_seed_cards


TIDONG_SEED = Path("data_seed/cards_seed_tidong_interview_v1.json")
PENGZHIRUI_SEED = Path("data_seed/cards_seed_pengzhirui_interview_v1.json")


def test_dry_run_reads_tidong_seed(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = import_seed_cards.main([str(TIDONG_SEED), "--dry-run"], environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Dry run only. No API request was sent." in captured.out
    assert "Card count: 10" in captured.out
    assert "interview-tidong-20260706-v1" in captured.out
    assert "三个接口做性能测试，你会怎么做？" in captured.out


def test_dry_run_reads_pengzhirui_seed(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = import_seed_cards.main([str(PENGZHIRUI_SEED)], environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Dry run only. No API request was sent." in captured.out
    assert "Card count: 13" in captured.out
    assert "interview-pengzhirui-20260707-v1" in captured.out
    assert "安全测试工具输出的 JSON 变体，怎么保证有效？" in captured.out


def test_invalid_json_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid_seed = tmp_path / "bad.json"
    invalid_seed.write_text("{not json", encoding="utf-8")

    exit_code = import_seed_cards.main([str(invalid_seed)], environ={})

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Seed file is not valid JSON" in captured.err


def test_missing_required_field_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid_seed = tmp_path / "missing-field.json"
    invalid_seed.write_text(
        json.dumps(
            [
                {
                    "title": "Missing reference answer",
                    "category": "python",
                    "difficulty": "medium",
                    "question_type": "knowledge",
                    "core_knowledge": "core",
                    "question": "question",
                    "scoring_rules": {"must_include": ["x"]},
                    "tags": ["seed"],
                    "source_reference": "test-seed",
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = import_seed_cards.main([str(invalid_seed)], environ={})

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "failed KnowledgeCardCreate validation" in captured.err
    assert "reference_answer" in captured.err


def test_execute_uses_mocked_bulk_api_without_real_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request_json(
        method: str,
        url: str,
        *,
        username: str,
        password: str,
        payload: Any | None = None,
        timeout: int = 30,
    ) -> Any:
        calls.append(
            {
                "method": method,
                "url": url,
                "username": username,
                "password": password,
                "payload": payload,
                "timeout": timeout,
            }
        )
        if url.endswith("/api/v1/cards/sources"):
            return {"items": []}
        if url.endswith("/api/v1/cards/bulk"):
            assert isinstance(payload, list)
            return {"created_count": len(payload), "items": [{"id": 1}]}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(import_seed_cards, "request_json", fake_request_json)
    env = {
        "SKILLLOOP_BASE_URL": "https://skillloop.example",
        "SKILLLOOP_BASIC_AUTH_USERNAME": "skillloop",
        "SKILLLOOP_BASIC_AUTH_PASSWORD": "test-password",
    }

    exit_code = import_seed_cards.main([str(TIDONG_SEED), "--execute"], environ=env)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Import executed." in captured.out
    assert "Created count: 10" in captured.out
    assert "test-password" not in captured.out
    assert "test-password" not in captured.err
    assert [call["method"] for call in calls] == ["GET", "POST"]
    assert calls[0]["url"] == "https://skillloop.example/api/v1/cards/sources"
    assert calls[1]["url"] == "https://skillloop.example/api/v1/cards/bulk"
    assert calls[1]["username"] == "skillloop"
    assert calls[1]["password"] == "test-password"


def test_execute_stops_when_source_reference_already_exists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def fake_request_json(
        method: str,
        url: str,
        *,
        username: str,
        password: str,
        payload: Any | None = None,
        timeout: int = 30,
    ) -> Any:
        calls.append(url)
        return {
            "items": [
                {
                    "source_reference": "interview-tidong-20260706-v1",
                    "total_count": 10,
                    "active_count": 10,
                    "inactive_count": 0,
                }
            ]
        }

    monkeypatch.setattr(import_seed_cards, "request_json", fake_request_json)
    env = {
        "OFFERFORGE_BASE_URL": "https://offerforge.example",
        "OFFERFORGE_BASIC_AUTH_USERNAME": "offerforge",
        "OFFERFORGE_BASIC_AUTH_PASSWORD": "test-password",
    }

    exit_code = import_seed_cards.main([str(TIDONG_SEED), "--execute"], environ=env)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert len(calls) == 1
    assert "Source reference already exists online" in captured.err


def test_execute_requires_base_url(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = import_seed_cards.main(
        [str(TIDONG_SEED), "--execute"],
        environ={
            "OFFERFORGE_BASIC_AUTH_USERNAME": "offerforge",
            "OFFERFORGE_BASIC_AUTH_PASSWORD": "test-password",
        },
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "SKILLLOOP_BASE_URL is required for --execute." in captured.err
    assert "test-password" not in captured.err


def test_execute_requires_basic_auth(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = import_seed_cards.main(
        [str(TIDONG_SEED), "--execute"],
        environ={"OFFERFORGE_BASE_URL": "https://offerforge.example"},
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "SKILLLOOP_BASIC_AUTH_USERNAME is required for --execute." in captured.err


def test_error_output_masks_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_request_json(
        method: str,
        url: str,
        *,
        username: str,
        password: str,
        payload: Any | None = None,
        timeout: int = 30,
    ) -> Any:
        raise import_seed_cards.SeedImportError(
            f"Remote error mentioned {password}"
        )

    monkeypatch.setattr(import_seed_cards, "request_json", fake_request_json)
    env = {
        "OFFERFORGE_BASE_URL": "https://offerforge.example",
        "OFFERFORGE_BASIC_AUTH_USERNAME": "offerforge",
        "OFFERFORGE_BASIC_AUTH_PASSWORD": "test-password",
    }

    exit_code = import_seed_cards.main([str(TIDONG_SEED), "--execute"], environ=env)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "test-password" not in captured.err
    assert "Remote error mentioned ***" in captured.err
