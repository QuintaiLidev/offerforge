from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.knowledge_card import KnowledgeCardCreate  # noqa: E402

CARDS_BULK_ENDPOINT = "/api/v1/cards/bulk"
CARDS_SOURCES_ENDPOINT = "/api/v1/cards/sources"


class SeedImportError(Exception):
    """Raised for user-facing import script failures."""


@dataclass(frozen=True)
class ValidatedSeed:
    path: Path
    cards: list[dict[str, Any]]

    @property
    def source_references(self) -> list[str | None]:
        return sorted(
            {card.get("source_reference") for card in self.cards},
            key=lambda value: "" if value is None else value,
        )

    @property
    def titles(self) -> list[str]:
        return [str(card["title"]) for card in self.cards]


def load_and_validate_seed(path: Path) -> ValidatedSeed:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedImportError(f"Seed file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SeedImportError(f"Seed file is not valid JSON: {exc}") from exc

    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise SeedImportError("Seed file must contain a JSON list of objects.")
    if not payload:
        raise SeedImportError("Seed file must contain at least one card.")

    validated_cards: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        try:
            validated = KnowledgeCardCreate.model_validate(item)
        except Exception as exc:
            title = item.get("title", "<missing title>")
            raise SeedImportError(
                f"Card #{index} ({title}) failed KnowledgeCardCreate validation: {exc}"
            ) from exc
        validated_cards.append(validated.model_dump(mode="json"))

    return ValidatedSeed(path=path, cards=validated_cards)


def require_env(
    name: str,
    environ: dict[str, str],
    *,
    legacy_name: str | None = None,
) -> str:
    selected_name = name if name in environ or legacy_name is None else legacy_name
    value = environ.get(selected_name, "").strip()
    if not value:
        raise SeedImportError(f"{name} is required for --execute.")
    return value


def build_url(base_url: str, endpoint: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))


def make_basic_auth_header(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def request_json(
    method: str,
    url: str,
    *,
    username: str,
    password: str,
    payload: Any | None = None,
    timeout: int = 30,
) -> Any:
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": make_basic_auth_header(username, password),
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise SeedImportError(
            f"HTTP {exc.code} from {url}: {summarize_response(response_body)}"
        ) from exc
    except URLError as exc:
        raise SeedImportError(f"Request to {url} failed: {exc.reason}") from exc

    if not response_body:
        return {}
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise SeedImportError(
            f"Response from {url} was not valid JSON: {summarize_response(response_body)}"
        ) from exc


def summarize_response(response_body: str, limit: int = 500) -> str:
    compact = " ".join(response_body.split())
    if len(compact) > limit:
        return compact[:limit] + "..."
    return compact


def assert_source_not_imported(
    *,
    base_url: str,
    username: str,
    password: str,
    seed: ValidatedSeed,
) -> None:
    url = build_url(base_url, CARDS_SOURCES_ENDPOINT)
    sources = request_json("GET", url, username=username, password=password)
    items = sources.get("items") if isinstance(sources, dict) else None
    if not isinstance(items, list):
        raise SeedImportError(
            "Could not verify existing source_reference values; aborting import."
        )

    existing = {
        item.get("source_reference"): item
        for item in items
        if isinstance(item, dict) and item.get("source_reference") is not None
    }
    conflicts = [
        source
        for source in seed.source_references
        if source is not None
        and source in existing
        and int(existing[source].get("total_count") or 0) > 0
    ]
    if conflicts:
        conflict_list = ", ".join(str(source) for source in conflicts)
        raise SeedImportError(
            f"Source reference already exists online: {conflict_list}. "
            "Delete or deactivate intentionally before importing again."
        )


def run_dry_run(seed: ValidatedSeed) -> None:
    print("Dry run only. No API request was sent.")
    print(f"Seed file: {seed.path}")
    print(f"Card count: {len(seed.cards)}")
    print("Source reference(s):")
    for source_reference in seed.source_references:
        print(f"- {source_reference}")
    print("Titles:")
    for index, title in enumerate(seed.titles, start=1):
        print(f"{index}. {title}")


def run_execute(seed: ValidatedSeed, environ: dict[str, str]) -> None:
    base_url = require_env(
        "SKILLLOOP_BASE_URL",
        environ,
        legacy_name="OFFERFORGE_BASE_URL",
    )
    username = require_env(
        "SKILLLOOP_BASIC_AUTH_USERNAME",
        environ,
        legacy_name="OFFERFORGE_BASIC_AUTH_USERNAME",
    )
    password = require_env(
        "SKILLLOOP_BASIC_AUTH_PASSWORD",
        environ,
        legacy_name="OFFERFORGE_BASIC_AUTH_PASSWORD",
    )

    assert_source_not_imported(
        base_url=base_url,
        username=username,
        password=password,
        seed=seed,
    )

    url = build_url(base_url, CARDS_BULK_ENDPOINT)
    result = request_json(
        "POST",
        url,
        username=username,
        password=password,
        payload=seed.cards,
    )
    created_count = result.get("created_count") if isinstance(result, dict) else None
    print("Import executed.")
    print(f"Created count: {created_count}")
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        print(f"Returned items: {len(result['items'])}")


def mask_sensitive(text: str, secrets: list[str]) -> str:
    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import SkillLoop seed cards through the existing bulk API."
    )
    parser.add_argument("seed_path", type=Path, help="Path to seed JSON file.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the seed without sending API requests. This is default.",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Actually call the remote bulk API after source_reference safety checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    args = parse_args(argv)
    env = dict(os.environ if environ is None else environ)
    passwords = [
        env.get("SKILLLOOP_BASIC_AUTH_PASSWORD", ""),
        env.get("OFFERFORGE_BASIC_AUTH_PASSWORD", ""),
    ]
    try:
        seed = load_and_validate_seed(args.seed_path)
        if args.execute:
            run_execute(seed, env)
        else:
            run_dry_run(seed)
    except SeedImportError as exc:
        print(mask_sensitive(f"Error: {exc}", passwords), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
