from __future__ import annotations

from pathlib import Path

from app.core.config import DEFAULT_DATABASE_PATH, load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_env_example_documents_safe_deployment_variables() -> None:
    content = read_text(".env.example")
    lines = {
        line.split("=", maxsplit=1)[0]: line.split("=", maxsplit=1)[1]
        for line in content.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert lines["OFFERFORGE_AUTH_ENABLED"] == "true"
    assert lines["OFFERFORGE_AUTH_USERNAME"] == "change-me"
    assert lines["OFFERFORGE_AUTH_PASSWORD"] == "change-me"
    assert lines["OFFERFORGE_DATABASE_PATH"] == "./data/offerforge.db"
    assert "test-secret" not in content
    assert "please-change-this-password" not in content


def test_deployment_document_exists_and_covers_private_cloud_readiness() -> None:
    content = read_text("docs/DEPLOYMENT.md")

    assert "/app" in content
    assert "Basic Auth" in content
    assert "SQLite" in content
    assert "persistent disk" in content
    assert "OFFERFORGE_AUTH_ENABLED" in content
    assert "OFFERFORGE_AUTH_USERNAME" in content
    assert "OFFERFORGE_AUTH_PASSWORD" in content
    assert "OFFERFORGE_DATABASE_PATH" in content
    assert "python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT" in content
    assert "GET /api/v1/health" in content
    assert "POST /api/v1/practice-attempts" in content


def test_readme_links_to_deployment_guide_and_app_path() -> None:
    content = read_text("README.md")

    assert "Deployment" in content
    assert "docs/DEPLOYMENT.md" in content
    assert "docs/CLOUD_SMOKE_TEST.md" in content
    assert "/app" in content
    assert "Basic Auth" in content


def test_cloud_smoke_test_record_documents_render_mvp_result() -> None:
    content = read_text("docs/CLOUD_SMOKE_TEST.md")

    assert "Render" in content
    assert "GitHub private repo" in content
    assert "Basic Auth enabled" in content
    assert "SQLite" in content
    assert "/api/v1/health" in content
    assert "/docs" in content
    assert "/app" in content
    assert "dont_know" in content
    assert "with_hint" in content
    assert "correct_slow" in content
    assert "correct_explain" in content
    assert "transfer" in content
    assert "Cloud MVP smoke test passed" in content
    assert "password" not in content.lower()


def test_gitignore_excludes_secrets_databases_and_runtime_artifacts() -> None:
    content = read_text(".gitignore")

    assert ".env" in content.splitlines()
    assert "*.db" in content
    assert "*.sqlite" in content
    assert "*.sqlite3" in content
    assert "data/*.db" in content
    assert ".pytest-tmp/" in content
    assert "__pycache__/" in content
    assert ".venv/" in content


def test_procfile_uses_uvicorn_and_platform_port() -> None:
    content = read_text("Procfile")

    assert content.strip() == (
        "web: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    )


def test_database_path_configuration_remains_default_and_overridable(
    tmp_path: Path,
) -> None:
    default_settings = load_settings({})
    cloud_database_path = tmp_path / "offerforge.db"
    cloud_settings = load_settings(
        {
            "OFFERFORGE_DATABASE_PATH": str(cloud_database_path),
        }
    )

    assert default_settings.database_path == DEFAULT_DATABASE_PATH
    assert cloud_settings.database_path == cloud_database_path
    assert cloud_settings.database_url == f"sqlite:///{cloud_database_path.as_posix()}"
