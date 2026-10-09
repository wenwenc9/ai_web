"""运价包公开 stdout 信封。可选键缺省不出现。"""

from __future__ import annotations

import json
from typing import Any

from sofreight_runtime.credentials import load_api_key, missing_key_hint
from sofreight_runtime.http import request_json
from sofreight_runtime.partners import fetch_partners
from sofreight_runtime.paths import exports_dir

AUTH_HINT = missing_key_hint('python scripts/price.py --save "<KEY>"')
CACHE_NAME = "sea-freight-price-last.json"


def read_cache() -> dict[str, Any]:
    path = exports_dir() / CACHE_NAME
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(data: dict[str, Any]) -> None:
    path = exports_dir() / CACHE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def envelope(
    *,
    status: str,
    action: str,
    summary: str,
    query: dict[str, Any] | None = None,
    counts: dict[str, Any] | None = None,
    chat: list[Any] | None = None,
    hints: dict[str, Any] | None = None,
    export_path: str | None = None,
    preview: dict[str, Any] | None = None,
    setup_reference: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"status": status, "action": action, "summary": {"message": summary}}
    if query:
        query = {k: v for k, v in query.items() if v not in (None, "")}
        if query:
            out["query"] = query
    if counts:
        counts = {k: v for k, v in counts.items() if v is not None}
        if counts:
            out["counts"] = counts
    if chat is not None:
        out["chat"] = chat
    if hints:
        hints = {k: v for k, v in hints.items() if v not in (None, False, "")}
        if hints:
            out["hints"] = hints
    if export_path:
        out["export_path"] = export_path
    if preview:
        out["preview"] = preview
    if setup_reference:
        out["setup_reference"] = setup_reference
    return out


def _partners_http(
    method: str,
    path: str,
    api_key: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "params": params,
        "json_body": json_body,
        "form_body": form_body,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return request_json(method, path, api_key, **kwargs)


def run_partners(
    *,
    keywords: str | None = None,
    http=None,
) -> dict[str, Any]:
    key = load_api_key()
    if not key:
        return {
            "status": "missing_key",
            "partners": [],
            "error": AUTH_HINT,
            "setup_reference": "references/auth.md",
        }
    query = (keywords or "").strip()
    fetched = fetch_partners(
        key,
        http=http or _partners_http,
        context={"keywords": query} if query else {},
    )
    result: dict[str, Any] = {
        "status": fetched["status"],
        "partners": fetched.get("partners") or [],
        "action": "partners",
    }
    if query:
        result["keywords"] = query
    cache_file = exports_dir() / CACHE_NAME
    if cache_file.is_file():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
        result["source_cached"] = True
        result["query"] = cache.get("query")
        result["queried_at"] = cache.get("queried_at")
    if fetched.get("error"):
        result["error"] = fetched["error"]
    return result


def add_partners_cli(parser, *, keywords_dest: str = "keywords") -> None:
    parser.add_argument(
        "--partners-confirmed",
        action="store_true",
        help="List cooperating merchants; A006 only",
    )
    if keywords_dest == "keywords":
        parser.add_argument(
            "--keywords",
            help="A006 search keywords from the user (e.g. 宁波); do not infer from last query",
        )
    else:
        parser.add_argument(
            "--partner-keywords",
            dest="partner_keywords",
            default="",
            help="A006 search keywords from the user (e.g. 宁波); do not infer from last query",
        )
