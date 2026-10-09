#!/usr/bin/env python3
"""搜航海运整箱运价 POST /SeaFclFreight/index。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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

from sofreight_runtime.credentials import load_api_key, mask_key, save_api_key
from sofreight_runtime.exit_codes import MISSING_KEY, OK, UNAUTHORIZED
from sofreight_runtime.http import request_json
from sofreight_runtime.output import print_json, write_xlsx
from sofreight_runtime.partners import fetch_partners
from sofreight_runtime.paths import credentials_path, exports_dir

from envelope import AUTH_HINT, CACHE_NAME, add_partners_cli, envelope, read_cache, run_partners, write_cache

A008 = "/SeaFclFreight/index"
ENDPOINT = A008
CHAT_LIMIT = 10
EXPORT_HINT = (
    "以上为挂牌参考价摘要（最多 10 条）。如需全量明细（全部命中行、NOR 柜型、中转港、驳船起运港等），"
    "请回复「导出 Excel」，将用 --export-only 从缓存生成，不会再次查询。"
)
INQUIRY_HINT = (
    "对上面哪一档价格感兴趣？在搜航提交询盘后，会有专人对接并帮你争取更优成交价。"
    "回复「询盘」，我会先汇总港口与箱型箱量给你确认，确认后才提交。"
    "询盘意向，会到咱们搜航AgentDeal询报价系统，会有专门客服稍后电话联系您"
)
VIA_LABEL = {0: "不限", 1: "直航", 2: "中转"}

CHAT_COLUMNS = (
    ("pol_cname", "起运港"),
    ("pod_cname", "目的港"),
    ("carrier_cname", "承运人"),
    ("carrier_code", "承运人代码"),
    ("service_code", "航线代码"),
    ("vessel", "船名"),
    ("voyage", "航次"),
    ("etd_date_show", "开航日"),
    ("tt", "航程(天)"),
    ("price_20gp", "20GP"),
    ("price_40gp", "40GP"),
    ("price_40hc", "40HC"),
    ("price_45hc", "45HC"),
    ("currency", "计价币种"),
    ("begin_date", "运价生效日"),
    ("end_date", "运价截止日"),
)

# Excel / 缓存：接口字段去掉下面这些后全部写入。
EXCLUDE_FIELDS = frozenset(
    {
        "tenant_id",
        "tenant_name",
        "tenant_en_name",
        "tenant_region",
        "tenant_user_id",
        "introduce_info",
        "tenant_user_info",
        "freight_id",
        "hash_code",
        "spot_type",
        "recommend_type",
        "feeder_pol_seq",
        "pol_seq",
        "pod_seq",
        "via_seq",
        "vessel_pol_seq",
        "vessel_via_seq",
        "carrier_seq",
        "carrier_logo",
        "carrier_spot_url",
        "currencyTag",
        "transit_id",
        "create_by",
        "fc",
        "trendInfo",
        "congestionInfo",
    }
)


def slim_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key not in EXCLUDE_FIELDS}


def _cell_value(item: dict[str, Any], field: str) -> Any:
    if field == "pol_cname":
        return item.get("pol_cname") or item.get("pol_code")
    if field == "pod_cname":
        return item.get("pod_cname") or item.get("pod_code")
    return item.get(field)


def project_row(item: dict[str, Any], columns: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field, label in columns:
        value = _cell_value(item, field)
        if value not in (None, ""):
            row[label] = value
    return row


def chat_rows(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [project_row(item, CHAT_COLUMNS) for item in source[:CHAT_LIMIT]]


def _excel_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def excel_rows(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys: list[str] = []
    seen: set[str] = set()
    for item in source:
        for key in item:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return [{key: _excel_cell(item.get(key)) for key in keys} for item in source]


def cache_path() -> Path:
    return exports_dir() / CACHE_NAME


def save_query_cache(chat: list, source: list, query: dict) -> None:
    existing = read_cache()
    payload = {
        "chat": chat,
        "source": source,
        "query": query,
        "queried_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if existing.get("ports"):
        payload["ports"] = existing["ports"]
    write_cache(payload)


def write_price_xlsx(chat: list, source: list) -> str:
    return str(write_xlsx({"聊天摘要": chat or [], "挂牌运价明细": excel_rows(source)}, "sea-freight-price"))


def export_from_cache() -> str:
    path = cache_path()
    if not path.is_file():
        raise FileNotFoundError("没有可导出的运价缓存，请先成功查询一次挂牌运价")
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source") or []
    if not source:
        raise FileNotFoundError("运价缓存中没有明细行，请先成功查询到运价后再导出")
    return write_price_xlsx(payload.get("chat") or [], source)


def parse_via_type(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if value in (0, 1, 2):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        number = int(text)
        return number if number in (0, 1, 2) else None
    mapping = {"直航": 1, "仅直航": 1, "中转": 2, "仅中转": 2, "不限": 0}
    return mapping.get(text)


def parse_cntr_type(raw: Any) -> list[dict[str, Any]] | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, list):
        items = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            cntr_type = str(item.get("type") or "").strip().upper()
            if not cntr_type:
                continue
            number = item.get("number")
            items.append(
                {
                    "type": cntr_type,
                    "number": int(number) if number not in (None, "") else 1,
                }
            )
        return items or None

    text = str(raw).strip()
    if not text:
        return None
    if text.startswith("["):
        try:
            return parse_cntr_type(json.loads(text))
        except json.JSONDecodeError:
            return None

    items = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        type_raw, _, num_raw = part.partition(":")
        cntr_type = type_raw.strip().upper()
        if not cntr_type:
            continue
        number = int(num_raw) if num_raw.strip() else 1
        items.append({"type": cntr_type, "number": number or 1})
    return items or None


def build_payload(pol_code: str, pod_code: str, options: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "pol_code": pol_code.strip().upper(),
        "pod_code": pod_code.strip().upper(),
    }
    for key, value in options.items():
        if isinstance(value, str):
            value = value.strip()
        if value in (None, "", []):
            continue
        payload[key] = value
    return payload


def empty_price_message(query: dict[str, Any]) -> str:
    parts = [f"起运港 {query['pol_code']}", f"目的港 {query['pod_code']}"]
    if query.get("carrier_code"):
        parts.append(f"船司 {query['carrier_code']}")
    if query.get("service_code"):
        parts.append(f"航线 {query['service_code']}")
    if query.get("etd_date_1") or query.get("etd_date_2"):
        etd = f"{query.get('etd_date_1') or ''}~{query.get('etd_date_2') or ''}".rstrip("~")
        parts.append(f"ETD {etd}")
    if query.get("via_type") is not None:
        via = VIA_LABEL.get(query["via_type"])
        if via:
            parts.append(via)
    return f"未找到匹配运价（{'，'.join(parts)}）。请核对 UN/LOCODE 与筛选条件。"


def query_sea_freight_price(
        api_key: str,
        pol_code: str,
        pod_code: str,
        *,
        carrier_code: str | None = None,
        cntr_type: Any = None,
        container_types: Any = None,
        etd_date_1: str | None = None,
        etd_date_2: str | None = None,
        order_field: str | None = None,
        service_code: str | None = None,
        tt_1: int | None = None,
        tt_2: int | None = None,
        valid_date_1: str | None = None,
        valid_date_2: str | None = None,
        via_type: Any = None,
        timeout_s: float = 30.0,
) -> dict[str, Any]:
    if not api_key or not str(api_key).strip():
        raise ValueError("api_key 不能为空，请前往搜航网进行申请~")
    if not pol_code or not str(pol_code).strip():
        raise ValueError("pol_code（起运港 UN/LOCODE）不能为空")
    if not pod_code or not str(pod_code).strip():
        raise ValueError("pod_code（目的港 UN/LOCODE）不能为空")

    via_int = parse_via_type(via_type)
    parsed_cntr = parse_cntr_type(cntr_type if cntr_type not in (None, "") else container_types)
    options = {
        "carrier_code": carrier_code,
        "cntr_type": parsed_cntr,
        "etd_date_1": etd_date_1,
        "etd_date_2": etd_date_2,
        "order_field": order_field,
        "service_code": service_code,
        "tt_1": tt_1,
        "tt_2": tt_2,
        "valid_date_1": valid_date_1,
        "valid_date_2": valid_date_2,
        "via_type": via_int,
        "rows": 20,
        "confirm": 1
    }
    query = build_payload(pol_code, pod_code, options)

    try:
        body = request_json(
            "POST",
            ENDPOINT,
            api_key,
            json_body=query,
            timeout=timeout_s,
        )
    except PermissionError:
        raise
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "query": query, "summary": {"message": f"网络请求失败：{exc}"}}

    if body.get("code") != 1:
        return {
            "status": "error",
            "query": query,
            "summary": {"message": body.get("msg") or "接口返回 code 非 1"},
        }

    outer = body.get("data") or {}
    items = outer.get("data") or []
    api_total = outer.get("total", 0)
    direct = outer.get("direct", 0)
    transit = outer.get("transit", 0)

    if not items:
        return {
            "status": "empty",
            "total": 0,
            "api_total": api_total,
            "pricing_list": [],
            "query": query,
            "summary": {"message": empty_price_message(query)},
        }

    items = [slim_item(item) for item in items if isinstance(item, dict)]

    return {
        "status": "ok",
        "total": len(items),
        "api_total": api_total,
        "direct": direct,
        "transit": transit,
        "pricing_list": items,
        "query": query,
        "summary": {
            "message": (
                f"查询成功，本次仅返回 {len(items)} 条。已匹配直航 {direct} 条，中转 {transit} 条。更多详情请前往搜航网 https://www.sofreight.com 查询。"
                "挂牌参考价，非正式订舱确认。"
            )
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sofreight sea freight price")
    key_action = parser.add_mutually_exclusive_group()
    key_action.add_argument("--save", metavar="KEY", help="Save API Key locally (masked in output)")
    key_action.add_argument("--clear", action="store_true", help="Delete the locally saved API Key")
    parser.add_argument("--pol-code", default="", help="Origin port UN/LOCODE")
    parser.add_argument("--pod-code", default="", help="Destination port UN/LOCODE")
    parser.add_argument("--carrier-code", default="", help="Carrier codes, comma-separated")
    parser.add_argument("--cntr-type", default="", help='JSON array, e.g. [{"type":"20GP","number":2}]')
    parser.add_argument("--container-types", default="", help="Types like 20GP,40HC (qty defaults to 1)")
    parser.add_argument("--etd-date-1", default="")
    parser.add_argument("--etd-date-2", default="")
    parser.add_argument("--order-field", default="")
    parser.add_argument("--service-code", default="")
    parser.add_argument("--tt-1", "--tt-min", dest="tt_1", type=int, default=None)
    parser.add_argument("--tt-2", "--tt-max", dest="tt_2", type=int, default=None)
    parser.add_argument("--valid-date-1", default="")
    parser.add_argument("--valid-date-2", default="")
    parser.add_argument("--via-type", default="", help="0/不限, 1/直航, 2/中转")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--export", action="store_true", help="Write Excel after this query")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Write Excel from last successful query cache; no API call",
    )
    add_partners_cli(parser)
    args = parser.parse_args()
    if args.save is not None or args.clear or args.export_only or args.partners_confirmed:
        return args
    if not args.pol_code.strip() or not args.pod_code.strip():
        parser.error(
            "--pol-code and --pod-code are required unless "
            "--save/--clear/--export-only/--partners-confirmed"
        )
    return args


def run_key_command(args: argparse.Namespace) -> int:
    if args.save is not None:
        save_api_key(args.save)
        print_json(
            envelope(
                status="saved",
                action="key",
                summary="API Key 已保存。",
                query={"masked": mask_key(args.save.strip())},
            )
        )
        return OK
    credentials_path().unlink(missing_ok=True)
    print_json(envelope(status="cleared", action="key", summary="本机 API Key 已清除。"))
    return OK


def present_price(result: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    query = result.get("query") or {}
    message = (result.get("summary") or {}).get("message") or ""
    status = result.get("status") or "error"
    if status == "error":
        return envelope(status="error", action="price", summary=message, query=query)
    items = result.get("pricing_list") or []
    chat = chat_rows(items)
    save_query_cache(chat, items, query)
    hints = {"inquiry_available": True, "inquiry_hint": INQUIRY_HINT}
    export_path = None
    if status == "ok":
        hints.update(
            source_cached=True,
            export_available=True,
            export_hint=EXPORT_HINT,
        )
        if args.export:
            export_path = write_price_xlsx(chat, items)
    return envelope(
        status=status,
        action="price",
        summary=message,
        query=query,
        counts={
            "returned": len(items),
            "api_total": result.get("api_total") or 0,
            "direct": result.get("direct") or 0,
            "transit": result.get("transit") or 0,
        },
        chat=chat,
        hints=hints,
        export_path=export_path,
    )


def main() -> int:
    args = parse_args()
    if args.save is not None or args.clear:
        return run_key_command(args)
    if args.partners_confirmed:
        try:
            result = run_partners(keywords=args.keywords)
        except PermissionError:
            print_json(envelope(status="unauthorized", action="partners", summary="API Key 被拒绝。"))
            return UNAUTHORIZED
        print_json(result)
        return MISSING_KEY if result["status"] == "missing_key" else OK
    if args.export_only:
        try:
            path = export_from_cache()
        except FileNotFoundError as exc:
            print_json(envelope(status="error", action="export", summary=str(exc)))
            return 1
        print_json(
            envelope(
                status="ok",
                action="export",
                summary="Excel 已生成。请把路径告诉用户，不要把表格读回对话。",
                export_path=path,
            )
        )
        return OK

    api_key = load_api_key()
    if not api_key:
        print_json(
            envelope(
                status="missing_key",
                action="price",
                summary=AUTH_HINT,
                setup_reference="references/auth.md",
            )
        )
        return MISSING_KEY

    try:
        result = query_sea_freight_price(
            api_key,
            args.pol_code,
            args.pod_code,
            carrier_code=args.carrier_code or None,
            cntr_type=args.cntr_type or None,
            container_types=args.container_types or None,
            etd_date_1=args.etd_date_1 or None,
            etd_date_2=args.etd_date_2 or None,
            order_field=args.order_field or None,
            service_code=args.service_code or None,
            tt_1=args.tt_1,
            tt_2=args.tt_2,
            valid_date_1=args.valid_date_1 or None,
            valid_date_2=args.valid_date_2 or None,
            via_type=args.via_type or None,
            timeout_s=args.timeout,
        )
    except PermissionError:
        print_json(
            envelope(status="unauthorized", action="price", summary="API Key 被拒绝。")
        )
        return UNAUTHORIZED
    except ValueError as exc:
        print_json(envelope(status="error", action="price", summary=str(exc)))
        return 1

    public = present_price(result, args)
    print_json(public)
    if public["status"] in {"ok", "empty"}:
        return OK
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
