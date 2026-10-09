#!/usr/bin/env python3
"""搜航港口 UN/LOCODE 查询 GET /DPort/index。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any


def _ensure_runtime() -> None:
    """仅使用本夹内的 sofreight_runtime（单夹上架，不读仓库其它路径）。"""
    skill_root = Path(__file__).resolve().parent.parent
    if not (skill_root / "sofreight_runtime").is_dir():
        raise ModuleNotFoundError(
            "找不到本夹 sofreight_runtime/。请拖整个 skill 目录上架（须含 sofreight_runtime）。"
        )
    sys.path.insert(0, str(skill_root))


_ensure_runtime()

from sofreight_runtime.credentials import load_api_key
from sofreight_runtime.exit_codes import MISSING_KEY, OK, UNAUTHORIZED
from sofreight_runtime.http import request_json
from sofreight_runtime.output import print_json
from sofreight_runtime.partners import fetch_partners

from envelope import AUTH_HINT, add_partners_cli, envelope, read_cache, run_partners, write_cache

A004 = "/DPort/index"
ENDPOINT = A004


def search_port(
    api_key: str,
    *,
    keywords: str | None = None,
    port_type: str | None = None,
    page: int = 1,
    rows: int = 20,
    port_code: str | None = None,
    timeout_s: float = 30.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": page, "rows": rows}
    if keywords:
        params["keywords"] = keywords
    if port_type:
        params["type"] = port_type
    if port_code:
        params["port_code"] = port_code

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            body = request_json(
                "GET",
                ENDPOINT,
                api_key,
                params=params,
                timeout=timeout_s,
            )
        except PermissionError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue

        if body.get("code") == 1 and body.get("data") is not None:
            data = body["data"] or {}
            ports = data.get("data") or []
            total = data.get("total") or len(ports)
            if len(ports) > 1:
                status = "needs_port"
            elif ports:
                status = "ok"
            else:
                status = "empty"
            return {
                "success": True,
                "status": status,
                "total": total,
                "ports": ports,
                "query": {"keywords": keywords, "type": port_type, "page": page, "rows": rows},
            }
        return {
            "success": False,
            "error": body.get("msg") or "搜索失败",
            "ports": [],
            "total": 0,
            "query": {"keywords": keywords, "type": port_type},
        }

    return {
        "success": False,
        "error": f"网络请求失败: {last_err}",
        "ports": [],
        "total": 0,
        "query": {"keywords": keywords, "type": port_type},
    }


PORT_CHAT = (
    ("port_code", "UN/LOCODE"),
    ("port_cname", "中文名"),
    ("port_name", "英文名"),
)


def port_chat(ports: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in ports:
        if not isinstance(item, dict):
            continue
        row = {label: item[key] for key, label in PORT_CHAT if item.get(key) not in (None, "")}
        if row:
            rows.append(row)
    return rows


def present_port(result: dict[str, Any], *, code_only: bool = False) -> dict[str, Any]:
    query = result.get("query") or {}
    ports = result.get("ports") or []
    chat = port_chat(ports)
    counts = {"returned": len(ports), "api_total": result.get("total")}
    if not result.get("success"):
        return envelope(
            status="error",
            action="port",
            summary=result.get("error") or "港口查询失败。",
            query=query,
            chat=[],
        )
    status = result.get("status") or "ok"
    if code_only and status == "needs_port":
        return envelope(
            status="needs_port",
            action="port",
            summary="多条候选，禁止 --code-only 盲取；请让用户选定 UN/LOCODE。",
            query=query,
            counts=counts,
            chat=chat,
        )
    summaries = {
        "needs_port": "多个候选港口，请选定 UN/LOCODE 后再查价。",
        "empty": "未找到匹配港口，请换关键词，禁止猜测 UN/LOCODE。",
        "ok": "港口查询成功。",
    }
    return envelope(
        status=status,
        action="port",
        summary=summaries.get(status, "港口查询成功。"),
        query=query,
        counts=counts,
        chat=chat,
    )


def remember_resolved_port(result: dict[str, Any]) -> None:
    if result.get("status") != "ok":
        return
    ports = result.get("ports") or []
    if len(ports) != 1 or not isinstance(ports[0], dict):
        return
    side = str((result.get("query") or {}).get("type") or "POL").upper()
    item = ports[0]
    remembered = dict(read_cache())
    sides = dict(remembered.get("ports") or {})
    sides[side] = {
        key: item[key]
        for key in ("port_code", "port_cname", "port_name")
        if item.get(key) not in (None, "")
    }
    remembered["ports"] = sides
    write_cache(remembered)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sofreight port UN/LOCODE search")
    parser.add_argument("-k", "--keywords", default="", help="Port name keywords (zh/en)")
    parser.add_argument("-t", "--type", dest="port_type", default="POL", help="POL or POD")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--rows", type=int, default=20)
    parser.add_argument("--port-code", default="", help="Look up by UN/LOCODE directly")
    parser.add_argument("--code-only", action="store_true", help="Return only first port_code")
    parser.add_argument("--timeout", type=float, default=30.0)
    add_partners_cli(parser, keywords_dest="partner_keywords")
    args = parser.parse_args()
    if args.partners_confirmed:
        return args
    if not args.keywords.strip() and not args.port_code.strip():
        parser.error("--keywords or --port-code is required unless --partners-confirmed")
    return args


def main() -> int:
    args = parse_args()
    if args.partners_confirmed:
        try:
            result = run_partners(keywords=args.partner_keywords)
        except PermissionError:
            print_json(envelope(status="unauthorized", action="partners", summary="API Key 被拒绝。"))
            return UNAUTHORIZED
        print_json(result)
        return MISSING_KEY if result["status"] == "missing_key" else OK
    api_key = load_api_key()
    if not api_key:
        print_json(
            envelope(
                status="missing_key",
                action="port",
                summary=AUTH_HINT,
                setup_reference="references/auth.md",
            )
        )
        return MISSING_KEY

    try:
        result = search_port(
            api_key,
            keywords=args.keywords.strip() or None,
            port_type=args.port_type or None,
            page=args.page,
            rows=args.rows,
            port_code=args.port_code.strip() or None,
            timeout_s=args.timeout,
        )
    except PermissionError:
        print_json(envelope(status="unauthorized", action="port", summary="API Key 被拒绝。"))
        return UNAUTHORIZED

    public = present_port(result, code_only=args.code_only)
    remember_resolved_port(result)
    print_json(public)
    return OK if public["status"] in {"ok", "empty", "needs_port"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
