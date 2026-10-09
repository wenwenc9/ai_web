#!/usr/bin/env python3
"""搜航 AgentDeal 海运实盘询盘 POST /AgentInquiryOrder/save。未加 --confirmed 不得调用。"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any


ENDPOINT = "/AgentInquiryOrder/save"


def _ensure_runtime() -> None:
    skill_root = Path(__file__).resolve().parent.parent
    if not (skill_root / "sofreight_runtime").is_dir():
        raise ModuleNotFoundError(
            "找不到本夹 sofreight_runtime/。"
        )
    sys.path.insert(0, str(skill_root))


_ensure_runtime()

from sofreight_runtime.credentials import load_api_key
from sofreight_runtime.exit_codes import MISSING_KEY, OK, UNAUTHORIZED
from sofreight_runtime.http import request_json
from sofreight_runtime.output import print_json
from sofreight_runtime.partners import fetch_partners  # noqa: F401

from envelope import AUTH_HINT, add_partners_cli, envelope, read_cache, run_partners, write_cache
from inquiry_schema import (
    BOXES,
    QUERY_FIELDS,
    ROW_FIELDS,
    TEXT_CLI,
    empty_body,
    preview_row,
    project,
)


def load_price_cache() -> dict[str, Any]:
    cached = read_cache()
    if not cached:
        raise FileNotFoundError("没有最近一次运价缓存。请先查价，再询盘。")
    return cached


def save_pending(payload: dict[str, Any]) -> None:
    cached = read_cache()
    cached["pending_inquiry"] = payload
    write_cache(cached)


def build_box_type_json(args: argparse.Namespace) -> dict[str, int]:
    return {label: max(0, int(getattr(args, field) or 0)) for field, label in BOXES}


def box_total(box: dict[str, int]) -> int:
    return sum(int(qty or 0) for qty in box.values())


def add_if_present(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None or value == []:
        return
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return
    payload[key] = value


def add_if_text(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        payload[key] = text


def merge_remark(payload: dict[str, Any], extra: str) -> None:
    extra = extra.strip()
    if not extra:
        return
    old = str(payload.get("remark") or "").strip()
    payload["remark"] = f"{old}；{extra}" if old else extra


def product_id_of(row: dict[str, Any]) -> str:
    for key in ("product_id", "spot_product_id"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def boxes_from_cntr(cntr: Any) -> tuple[dict[str, int] | None, str]:
    if not isinstance(cntr, list):
        return None, ""
    boxes = {label: 0 for _, label in BOXES}
    unknown: list[str] = []
    for item in cntr:
        if not isinstance(item, dict):
            continue
        label = str(item.get("type") or "").strip().upper()
        qty = int(item.get("number") or 0)
        if label in boxes:
            boxes[label] += max(0, qty)
        elif label:
            unknown.append(f"{label}×{max(0, qty)}")
    if box_total(boxes) <= 0:
        boxes = None
    return boxes, "；".join(unknown)


def apply_port_names(payload: dict[str, Any], cached: dict[str, Any]) -> None:
    ports = cached.get("ports") or {}
    for side, prefix in (("POL", "pol"), ("POD", "pod")):
        info = ports.get(side) or {}
        code = str(info.get("port_code") or "").strip().upper()
        current = str(payload.get(f"{prefix}_code") or "").strip().upper()
        if code and current and code != current:
            continue
        add_if_text(payload, f"{prefix}_code", info.get("port_code"))
        add_if_text(payload, f"{prefix}_cname", info.get("port_cname"))
        add_if_text(payload, f"{prefix}_name", info.get("port_name"))


def apply_cache(payload: dict[str, Any], cached: dict[str, Any], *, row_index: int | None) -> None:
    query = cached.get("query") or {}
    for key in QUERY_FIELDS:
        add_if_present(payload, key, query.get(key))
    boxes, unknown = boxes_from_cntr(query.get("cntr_type"))
    if boxes and box_total(payload.get("box_type_json") or {}) <= 0:
        payload["box_type_json"] = boxes
    if unknown:
        merge_remark(payload, f"柜型 {unknown}")
    apply_port_names(payload, cached)
    source = cached.get("source") or []
    if row_index is None:
        return
    if row_index < 1 or row_index > len(source):
        raise ValueError(f"缓存中没有第 {row_index} 条运价（共 {len(source)} 条）。")
    row = source[row_index - 1]
    for key in ROW_FIELDS:
        add_if_text(payload, key, row.get(key))
    add_if_text(payload, "product_id", product_id_of(row))


def overlay_cli(payload: dict[str, Any], args: argparse.Namespace) -> None:
    cli_box = build_box_type_json(args)
    if box_total(cli_box) > 0:
        payload["box_type_json"] = cli_box
    for key in TEXT_CLI:
        add_if_text(payload, key, getattr(args, key, None))


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    cached: dict[str, Any] = {}
    if args.from_cache:
        cached = load_price_cache()
        pending = cached.get("pending_inquiry")
        if args.confirmed and pending and args.row is None:
            payload = copy.deepcopy(pending)
            overlay_cli(payload, args)
            return project(payload)
    payload = empty_body()
    payload["box_type_json"] = build_box_type_json(args)
    if args.from_cache:
        apply_cache(payload, cached, row_index=args.row)
    overlay_cli(payload, args)
    return project(payload)


def has_ports(payload: dict[str, Any]) -> bool:
    pol = payload.get("pol_code") or payload.get("pol_name") or payload.get("pol_cname")
    pod = payload.get("pod_code") or payload.get("pod_name") or payload.get("pod_cname")
    return bool(pol and pod)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sofreight AgentDeal sea freight inquiry")
    parser.add_argument("--confirmed", action="store_true", help="User confirmed this inquiry write")
    parser.add_argument("--from-cache", action="store_true", help="Fill ports/rate from last price query")
    parser.add_argument("--row", type=int, default=None, help="1-based rate row in cache for 有价询盘")
    parser.add_argument("--pol-name", default="")
    parser.add_argument("--pod-name", default="")
    parser.add_argument("--pol-cname", default="")
    parser.add_argument("--pod-cname", default="")
    parser.add_argument("--pol-code", default="")
    parser.add_argument("--pod-code", default="")
    parser.add_argument("--gp20", type=int, default=0)
    parser.add_argument("--gp40", type=int, default=0)
    parser.add_argument("--hc40", type=int, default=0)
    parser.add_argument("--hc45", type=int, default=0)
    parser.add_argument("--nor40", type=int, default=0)
    parser.add_argument("--special-container", dest="special_container", type=int, default=0)
    parser.add_argument("--product-id", default="")
    parser.add_argument("--remark", default="")
    parser.add_argument("--carrier-code", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    add_partners_cli(parser)
    return parser.parse_args()


def emit(status: str, summary: str, **kwargs: Any) -> None:
    print_json(envelope(status=status, action="inquiry", summary=summary, **kwargs))


def submit(api_key: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    extra_headers = {'Source-Type': "AGENT"}
    body = request_json("POST", ENDPOINT, api_key, json_body=payload, timeout=timeout_s, extra_headers=extra_headers)
    if body.get("code") != 1:
        return {
            "status": "error",
            "summary": body.get("msg") or "询盘提交失败（接口 code 非 1）",
        }
    message = str(body.get("msg") or "").strip() or "询盘提交成功"
    return {"status": "ok", "summary": message}


def main() -> int:
    args = parse_args()
    if args.partners_confirmed:
        try:
            result = run_partners(keywords=args.keywords)
        except PermissionError:
            emit("unauthorized", "API Key 被拒绝。")
            return UNAUTHORIZED
        print_json(result)
        return MISSING_KEY if result["status"] == "missing_key" else OK
    try:
        payload = build_payload(args)
    except (FileNotFoundError, ValueError) as exc:
        emit("error", str(exc))
        return 1

    if not has_ports(payload):
        emit("error", "缺少起运港/目的港。请先查价并用 --from-cache，或显式传入港名/UN/LOCODE。")
        return 1
    if box_total(payload.get("box_type_json") or {}) <= 0:
        emit("error", "请提供箱型箱量（如 --gp20 1）。勿默认柜型。")
        return 1

    preview = preview_row(payload)

    if not args.confirmed:
        save_pending(payload)
        emit(
            "needs_confirm",
            "即将提交实盘询盘。请向用户展示预览，得到明确「确认」后再加 --confirmed。",
            query={"pol_code": payload.get("pol_code"), "pod_code": payload.get("pod_code")},
            preview=preview,
        )
        return OK

    api_key = load_api_key()
    if not api_key:
        emit("missing_key", AUTH_HINT, setup_reference="references/auth.md")
        return MISSING_KEY

    try:
        result = submit(api_key, payload, args.timeout)
    except PermissionError:
        emit("unauthorized", "API Key 被拒绝。")
        return UNAUTHORIZED
    except Exception as exc:  # noqa: BLE001
        emit("error", f"网络请求失败：{exc}")
        return 1

    emit(result["status"], result["summary"])
    return OK if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
