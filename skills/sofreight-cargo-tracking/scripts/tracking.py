import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from typing import Literal


def _ensure_runtime() -> None:
    """Skill 目录内的 sofreight_runtime 优先（单夹上架）；否则用仓库 runtime/。"""
    script = Path(__file__).resolve()
    skill_root = script.parent.parent
    if (skill_root / "sofreight_runtime").is_dir():
        sys.path.insert(0, str(skill_root))
        return
    repo_runtime = script.parents[3] / "runtime"
    if (repo_runtime / "sofreight_runtime").is_dir():
        sys.path.insert(0, str(repo_runtime))
        return
    raise ModuleNotFoundError(
        "找不到 sofreight_runtime。上架时应拖整个 skill 目录（含 sofreight_runtime）。"
        "开发仓库里先运行: python tools/sync_runtime.py"
    )


_ensure_runtime()

from sofreight_runtime.credentials import load_api_key, mask_key, missing_key_hint, save_api_key
from sofreight_runtime.exit_codes import MISSING_KEY, OK, UNAUTHORIZED
from sofreight_runtime.http import request_json
from sofreight_runtime.output import print_json, write_xlsx
from sofreight_runtime.partners import fetch_partners
from sofreight_runtime.paths import credentials_path, exports_dir
from sofreight_runtime.quota import CARGO_TRACK_TYPE, can_cover, parse_quota


OrderType = Literal["blNo", "bkNo"]
UNKNOWN_TYPE_ERROR = "无法判断提单或订舱号，请标明类型"
A001 = "/DMemberVipRefuelingNumber/searchLeftNumber"
A002 = "/ScheduleSubscribeV2/getCarrierByNo"
A003 = "/ScheduleSubscribeV2/agentSubscribe"
A010 = "/ScheduleSubscribeV2/subscribeList"
HttpClient = Callable[..., dict[str, Any]]
PUSH_STATUS_LABELS = {
    0: "订阅中",
    1: "正常",
    2: "暂无数据",
    3: "已取消",
    4: "已结束",
    5: "暂时取消",
}
SUBSCRIBE_TYPE_LABELS = {
    1: "提单",
    2: "订舱",
    3: "订舱",
}
BUSINESS_ERRORS = {
    10002: "需要开通搜航会员",
    500002: "浪花不足",
    500004: "浪花被禁用，联系客服",
}
DETAIL_COLUMNS = (
    "单号",
    "港口",
    "船名",
    "航次",
    "箱号",
    "箱型",
    "封条",
    "事件时间",
    "事件中文",
)
SUCCESS_STATUSES = {"ok", "unsubscribed"}
CACHE_NAME = "cargo-tracking-last.json"
EXPORT_HINT = "聊天里只给摘要。需要 Excel 明细时请明确说「导出」，我会用 --export-only 生成文件，不会再扣一次查询。"
AUTH_HINT = missing_key_hint(
    'python skills/sofreight-cargo-tracking/scripts/tracking.py --save "<KEY>"'
)


@dataclass(frozen=True)
class Ticket:
    order_number: str
    order_type: OrderType | None
    error: str | None = None


def detect_order_type(raw: str) -> OrderType | None:
    """Infer a type using only the first-phase local heuristic.

    Leading and trailing whitespace is ignored. ASCII alphanumeric values
    containing letters, and numeric values longer than 16 characters, tend
    to be bills of lading. Pure numbers of 8–16 digits tend to be booking
    numbers. Empty, unrecognized, and otherwise ambiguous values return None.
    """
    value = raw.strip()
    if not value or re.fullmatch(r"[A-Za-z0-9]+", value) is None:
        return None
    if value.isdigit():
        if 8 <= len(value) <= 16:
            return "bkNo"
        if len(value) > 16:
            return "blNo"
        return None
    return "blNo"


def normalize_numbers(items: list[str]) -> list[Ticket]:
    tickets: list[Ticket] = []
    for item in items:
        order_number = item.strip()
        order_type = detect_order_type(order_number)
        error = None if order_type is not None else UNKNOWN_TYPE_ERROR
        tickets.append(Ticket(order_number, order_type, error))
    return tickets


def summarize(tickets: list[Ticket]) -> dict[str, int]:
    failed = sum(ticket.error is not None for ticket in tickets)
    return {"total": len(tickets), "ok": len(tickets) - failed, "failed": failed}


def _payload_data(response: dict[str, Any]) -> Any:
    return response.get("data", response)


def _carrier_candidates(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = _payload_data(response)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("list", "records", "carrier_list", "carrierList", "carriers"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if any(
        key in data
        for key in ("carrier_code", "carrierCode", "carrie_code", "carrieCode")
    ):
        return [data]
    return []


def _first(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def _business_error(response: dict[str, Any]) -> str:
    code = response.get("code")
    mapped = BUSINESS_ERRORS.get(code)
    if mapped:
        return mapped
    return str(response.get("msg") or response.get("message") or f"接口返回 code={code}")


def _public_carrier(candidate: dict[str, Any]) -> dict[str, str]:
    code = str(
        _first(
            candidate,
            "carrier_code",
            "carrierCode",
            "carrie_code",
            "carrieCode",
        )
    )
    cname = str(
        _first(
            candidate,
            "carrier_cname",
            "carrierCname",
            "carrier_name_cn",
            "carrierNameCn",
            "carrier_name",
            "carrierName",
            default=code,
        )
    )
    return {"carrier_code": code, "carrier_cname": cname}


def _quota_params(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": CARGO_TRACK_TYPE,
        "bill_so": ticket["order_number"],
        "track_type": 1 if ticket["order_type"] == "blNo" else 2,
        "carrie_code": ticket["carrier_code"],
        "pol_code": "",
        "pod_code": "",
    }


def _subscribe_body(ticket: dict[str, Any], subscribe: bool) -> dict[str, Any]:
    return {
        "orderNumber": ticket["order_number"],
        "orderNumberType": ticket["order_type"],
        "carrier": ticket["carrier_code"],
        "sub": subscribe,
    }


def cache_path() -> Path:
    return exports_dir() / CACHE_NAME


def _queried_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_query_cache(result: dict[str, Any]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "queried_at": result.get("queried_at") or _queried_at(),
        "chat": result.get("chat", []),
        "details": result.get("details", []),
        "source": result.get("source") or [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_query_cache() -> dict[str, Any] | None:
    path = cache_path()
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def export_from_cache() -> str:
    path = cache_path()
    if not path.is_file():
        raise FileNotFoundError("没有可导出的货踪缓存，请先成功查询一票货踪")
    payload = json.loads(path.read_text(encoding="utf-8"))
    details = payload.get("details") or []
    if not details:
        rebuilt: list[dict[str, Any]] = []
        for item in payload.get("source") or []:
            if not isinstance(item, dict):
                continue
            number = str(item.get("order_number") or "")
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            rebuilt.extend(_event_rows(number, data))
        details = rebuilt
    return str(
        write_xlsx(
            {
                "摘要": payload.get("chat") or [],
                "明细": details,
            },
            "cargo-tracking",
        )
    )


def _present_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in DETAIL_COLUMNS
        if row.get(key) not in (None, "")
    }


def _detail_row(
    number: str,
    event: dict[str, Any],
    ctnr: dict[str, Any],
    default_vessel: str,
    default_voyage: str,
) -> dict[str, Any]:
    actual = _first(event, "status_time", "event_time", "time", "事件时间")
    estimated = _first(event, "status_etime", "statusEtime")
    event_time = actual or (
        f"{estimated}（预计）" if estimated not in (None, "") else ""
    )
    return _present_detail(
        {
            "单号": number,
            "港口": _first(event, "port_name", "portName", "port", "港口"),
            "船名": _first(event, "vessel", "vessel_name", "船名") or default_vessel,
            "航次": _first(event, "voyage", "voyage_no", "航次") or default_voyage,
            "箱号": _first(
                ctnr,
                "ctnr_no",
                "container_no",
                "containerNo",
                "箱号",
            )
            or _first(event, "ctnr_no", "container_no", "箱号"),
            "箱型": _first(ctnr, "ctnr_type", "container_type", "箱型"),
            "封条": _first(ctnr, "seal_no", "sealNo", "seal", "封条"),
            "事件时间": event_time,
            "事件中文": _first(
                event,
                "status_desc_cn",
                "status_name_cn",
                "status",
                "事件中文",
            ),
        }
    )


def _iter_containers(ctnr_data: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(ctnr_data, dict):
        items: list[tuple[str, dict[str, Any]]] = []
        for key, value in ctnr_data.items():
            if isinstance(value, dict):
                items.append((str(value.get("ctnr_no") or key), value))
        return items
    if isinstance(ctnr_data, list):
        items = []
        for value in ctnr_data:
            if isinstance(value, dict):
                items.append((str(value.get("ctnr_no") or ""), value))
        return items
    return []


def _event_rows(number: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
    default_vessel = str(
        _first(detail, "vessel", "vessel_name")
        or _first(data, "vessel", "vessel_name")
    )
    default_voyage = str(
        _first(detail, "voyage", "voyage_no")
        or _first(data, "voyage", "voyage_no")
    )
    ctnr_data = detail.get("ctnr_data", data.get("ctnr_data"))
    containers = _iter_containers(ctnr_data)
    if containers:
        rows: list[dict[str, Any]] = []
        for ctnr_no, ctnr in containers:
            events = (
                ctnr.get("container_event_list")
                or ctnr.get("events")
                or ctnr.get("event_list")
                or []
            )
            container = {**ctnr, "ctnr_no": ctnr.get("ctnr_no") or ctnr_no}
            if not isinstance(events, list) or not events:
                rows.append(
                    _detail_row(
                        number, {}, container, default_vessel, default_voyage
                    )
                )
                continue
            for event in events:
                if isinstance(event, dict):
                    rows.append(
                        _detail_row(
                            number,
                            event,
                            container,
                            default_vessel,
                            default_voyage,
                        )
                    )
        return rows

    events = _first(
        detail if detail else data,
        "events",
        "event_list",
        "eventList",
        "tracking_events",
        default=[],
    )
    if not isinstance(events, list):
        events = _first(
            data,
            "events",
            "event_list",
            "eventList",
            "tracking_events",
            default=[],
        )
    if not isinstance(events, list):
        return []
    return [
        _detail_row(number, event, {}, default_vessel, default_voyage)
        for event in events
        if isinstance(event, dict)
    ]


def _chat_blob(ticket: dict[str, Any]) -> dict[str, Any]:
    data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
    current = (
        data.get("currentStatus")
        if isinstance(data.get("currentStatus"), dict)
        else {}
    )
    return {**current, **detail, **data}


def _container_count(data: dict[str, Any], detail: dict[str, Any]) -> int:
    ctnr_data = detail.get("ctnr_data", data.get("ctnr_data"))
    if isinstance(ctnr_data, dict):
        return len(ctnr_data)
    if isinstance(ctnr_data, list):
        return len(ctnr_data)
    counted = _first(
        data,
        "container_count",
        "containerCount",
        "containers_num",
        default=None,
    )
    try:
        return int(counted) if counted not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _chat_row(ticket: dict[str, Any]) -> dict[str, Any]:
    data = ticket.get("data") if isinstance(ticket.get("data"), dict) else {}
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
    blob = _chat_blob(ticket)
    eta = _first(blob, "eta", "ETA")
    ata = _first(blob, "ata", "ATA")
    eta_ata = " / ".join(str(value) for value in (eta, ata) if value)
    order_type = {
        "blNo": "提单",
        "bkNo": "订舱",
    }.get(ticket.get("order_type"), "未知")
    status_cn = ticket.get("status_label") or _first(
        blob,
        "must_status_cname",
        "subscribe_status_cname",
        "must_status_name",
        "subscribe_status_name",
        "current_status_name",
        "currentStatusName",
        "status_name_cn",
        "statusNameCn",
    )
    row = {
        "单号": ticket["order_number"],
        "类型": order_type,
        "船司中文名": ticket.get("carrier_name")
        or _first(blob, "carrier_cname", "carrierCname", default=""),
        "当前状态中文": status_cn,
        "起运港": _first(
            blob,
            "pol_cname",
            "polCname",
            "pol_name",
            "polName",
            "port_of_loading",
            "pol",
        ),
        "目的港": _first(
            blob,
            "pod_cname",
            "podCname",
            "pod_name",
            "podName",
            "port_of_discharge",
            "pod",
        ),
        "ETA/ATA": eta_ata,
        "箱数": _container_count(data, detail),
        "本票结果": {
            "ok": "成功",
            "failed": "失败",
            "needs_carrier": "待选船司",
            "insufficient_quota": "额度不足",
            "needs_confirm": "待确认",
            "unsubscribed": "未订阅",
        }.get(ticket.get("status"), ticket.get("status", "")),
    }
    if ticket.get("error"):
        row["失败原因"] = ticket["error"]
    return row


def _quota_dict(snapshot: Any, needed: int) -> dict[str, Any]:
    return {
        "left_number": snapshot.left_number,
        "coins_num": snapshot.coins_num,
        "coins_disabled": snapshot.coins_disabled,
        "uses_coins": snapshot.uses_coins_for(needed),
    }


def _insufficient_prompt(executable_count: int, quota: dict[str, Any]) -> str:
    return (
        f"当前额度不足以查询 {executable_count} 票货踪"
        f"（剩余次数 {quota.get('left_number', 0)}，浪花 {quota.get('coins_num', 0)}）。"
        "请充值次数或浪花后再查，勿重试付费接口。"
    )


def _confirm_prompt(executable_count: int, quota: dict[str, Any]) -> str:
    if quota.get("uses_coins"):
        return (
            f"将查询 {executable_count} 票货踪（剩余次数 {quota['left_number']}，"
            "不足部分将使用浪花）。确认后才会调用查询/订阅接口，是否继续？"
        )
    return (
        f"将查询 {executable_count} 票货踪（剩余次数 {quota['left_number']}）。"
        "确认后才会调用查询/订阅接口，是否继续？"
    )


def _cannot_run(resolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "order_number": item["order_number"],
            "error": item.get("error") or "无法执行",
        }
        for item in resolved
        if item["status"] == "failed"
    ]


def _needs_carrier_tickets(resolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "order_number": item["order_number"],
            "carriers": item.get("carriers", []),
        }
        for item in resolved
        if item["status"] == "needs_carrier"
    ]


def _public_result(
    status: str,
    tickets: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    summary = [_chat_row(ticket) for ticket in tickets]
    payload: dict[str, Any] = {
        "status": status,
        **extra,
        "tickets": summary,
        "chat": summary,
    }
    source = []
    for item in tickets:
        if isinstance(item.get("data"), dict):
            source.append(
                {
                    "order_number": item.get("order_number"),
                    "data": item["data"],
                }
            )
    if source:
        payload["source"] = source
    return payload


def _default_http(
    method: str,
    path: str,
    api_key: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return request_json(
        method,
        path,
        api_key,
        params=params,
        json_body=json_body,
    )


def _select_carriers(
    candidates: list[dict[str, Any]],
    carrier: str | None,
) -> list[dict[str, str]]:
    public = [_public_carrier(item) for item in candidates]
    if not carrier:
        return public
    matched = [item for item in public if item["carrier_code"] == carrier]
    return matched


def _apply_subscribe_result(item: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
    if data.get("sub") is False and not detail:
        item.update(status="unsubscribed", data=data)
        return []

    push_status = detail.get("push_status", data.get("push_status"))
    if push_status == 0:
        item.update(status="ok", data=data, status_label="订阅中")
        return []
    if push_status == 2:
        item.update(status="ok", data=data, status_label="暂无数据")
        return []
    if push_status == 3:
        item.update(status="ok", data=data, status_label="已取消")
        return _event_rows(item["order_number"], data)
    if push_status == 5:
        item.update(status="ok", data=data, status_label="暂时取消")
        return _event_rows(item["order_number"], data)
    if push_status == 4:
        item.update(status="ok", data=data, status_label="已结束")
        return _event_rows(item["order_number"], data)

    item.update(status="ok", data=data)
    return _event_rows(item["order_number"], data)


def run_partners(
    *,
    http: HttpClient | None = None,
    api_key: str | None = None,
    keywords: str | None = None,
) -> dict[str, Any]:
    key = api_key or load_api_key()
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
        http=http or _default_http,
        context={"keywords": query} if query else {},
    )
    result: dict[str, Any] = {
        "status": fetched["status"],
        "partners": fetched.get("partners") or [],
    }
    if query:
        result["keywords"] = query
    cache = load_query_cache()
    if cache:
        result["tickets"] = cache.get("chat") or []
        result["chat"] = cache.get("chat") or []
        result["queried_at"] = cache.get("queried_at")
        result["source_cached"] = True
    if fetched.get("error"):
        result["error"] = fetched["error"]
    return result


def run_batch(
    numbers: list[str],
    *,
    confirmed: bool,
    subscribe: bool,
    http: HttpClient | None = None,
    api_key: str | None = None,
    carrier: str | None = None,
) -> dict[str, Any]:
    """Resolve carriers, check quota, then query/subscribe only after G4 confirm.

    A003 charges times or coins (D9). No ``confirmed`` → ``needs_confirm``, never POST.
    """
    key = api_key or load_api_key()
    if not key:
        return {
            "status": "missing_key",
            "tickets": [],
            "chat": [],
            "error": AUTH_HINT,
            "setup_reference": "references/auth.md",
        }

    client = http or _default_http
    resolved: list[dict[str, Any]] = []
    for ticket in normalize_numbers(numbers):
        item: dict[str, Any] = {
            "order_number": ticket.order_number,
            "order_type": ticket.order_type,
        }
        if ticket.error:
            item.update(status="failed", error=ticket.error)
            resolved.append(item)
            continue

        lookup_param = "bl_no" if ticket.order_type == "blNo" else "so_no"
        try:
            response = client(
                "GET",
                A002,
                key,
                params={lookup_param: ticket.order_number},
                json_body=None,
            )
        except PermissionError:
            raise
        except Exception as exc:
            item.update(status="failed", error=str(exc))
            resolved.append(item)
            continue

        if response.get("code") != 1:
            item.update(status="failed", error=_business_error(response))
            resolved.append(item)
            continue

        selected = _select_carriers(_carrier_candidates(response), carrier)
        if len(selected) != 1:
            if carrier and not selected:
                item.update(
                    status="failed",
                    carriers=_select_carriers(_carrier_candidates(response), None),
                    error=f"指定船司 {carrier} 不在候选列表",
                )
            else:
                item.update(
                    status="needs_carrier" if selected else "failed",
                    carriers=selected,
                    error=None if selected else "未匹配到船司",
                )
            resolved.append(item)
            continue

        chosen = selected[0]
        item.update(
            status="resolved",
            carrier_code=chosen["carrier_code"],
            carrier_name=chosen["carrier_cname"],
        )
        resolved.append(item)

    if any(item["status"] == "needs_carrier" for item in resolved):
        return _public_result(
            "needs_carrier",
            resolved,
            executable_count=sum(
                item["status"] == "resolved" for item in resolved
            ),
            needs_carrier_tickets=_needs_carrier_tickets(resolved),
        )

    executable = [item for item in resolved if item["status"] == "resolved"]
    needed = len(executable)
    snapshots = []
    for item in executable:
        try:
            response = client(
                "GET",
                A001,
                key,
                params=_quota_params(item),
                json_body=None,
            )
        except PermissionError:
            raise
        except Exception as exc:
            item.update(status="failed", error=str(exc))
            continue
        if response.get("code") != 1:
            item.update(status="failed", error=_business_error(response))
            continue
        snapshot = parse_quota(_payload_data(response), CARGO_TRACK_TYPE)
        snapshots.append(snapshot)

    executable = [item for item in resolved if item["status"] == "resolved"]
    needed = len(executable)
    quota_snapshot = min(
        snapshots,
        key=lambda value: value.left_number,
        default=None,
    )
    quota = (
        _quota_dict(quota_snapshot, needed)
        if quota_snapshot is not None
        else {
            "left_number": 0,
            "coins_num": 0,
            "coins_disabled": True,
            "uses_coins": False,
        }
    )
    quota_covers_batch = (
        len(snapshots) == needed
        and all(can_cover(snapshot, needed) for snapshot in snapshots)
    )
    if not confirmed or not quota_covers_batch:
        for item in executable:
            item["status"] = "needs_confirm"
        prompt = (
            _confirm_prompt(len(executable), quota)
            if quota_covers_batch
            else _insufficient_prompt(len(executable), quota)
        )
        return _public_result(
            "needs_confirm",
            resolved,
            prompt=prompt,
            left_number=quota["left_number"],
            executable_count=len(executable),
            uses_coins=quota["uses_coins"],
            cannot_run=_cannot_run(resolved),
            quota=quota,
        )

    details: list[dict[str, Any]] = []
    for item in executable:
        body = _subscribe_body(item, subscribe)
        try:
            response = client(
                "POST",
                A003,
                key,
                params=None,
                json_body=body,
            )
        except PermissionError:
            raise
        except Exception as exc:
            item.update(status="failed", error=str(exc))
            continue
        if response.get("code") != 1:
            item.update(status="failed", error=_business_error(response))
            continue
        data = _payload_data(response)
        data = data if isinstance(data, dict) else {}
        details.extend(_apply_subscribe_result(item, data))

    ok_count = sum(item["status"] in SUCCESS_STATUSES for item in resolved)
    failed_count = sum(item["status"] == "failed" for item in resolved)
    if ok_count and not failed_count:
        status = "ok"
    elif ok_count:
        status = "partial"
    else:
        status = "failed"
    return _public_result(
        status,
        resolved,
        left_number=quota["left_number"],
        executable_count=len(executable),
        quota=quota,
        details=details,
    )


def _list_order_number(item: dict[str, Any]) -> str:
    return str(
        _first(item, "bl_no", "so_no", "bk_no", default="")
        or ""
    )


def _list_eta_ata(item: dict[str, Any]) -> str:
    atd = _first(item, "atd")
    ata = _first(item, "ata")
    if atd or ata:
        return " / ".join(str(value) for value in (atd, ata) if value)
    etd = _first(item, "etd", "ETD")
    eta = _first(item, "eta", "ETA")
    return " / ".join(str(value) for value in (etd, eta) if value)


def _list_push_label(item: dict[str, Any]) -> str:
    raw = item.get("push_status")
    try:
        code = int(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        code = None
    if code is not None and code in PUSH_STATUS_LABELS:
        return PUSH_STATUS_LABELS[code]
    return str(
        _first(
            item,
            "subscribe_status_cname",
            "subscribe_status_name",
            default="",
        )
        or ""
    )


def _list_chat_row(item: dict[str, Any]) -> dict[str, Any]:
    try:
        subscribe_type = int(item.get("subscribe_type"))
    except (TypeError, ValueError):
        subscribe_type = None
    row = {
        "单号": _list_order_number(item),
        "类型": SUBSCRIBE_TYPE_LABELS.get(subscribe_type or -1, "未知"),
        "船司": _first(item, "carrier", "carrier_cname", default=""),
        "状态中文": _first(item, "subscribe_status_cname", default="")
        or _list_push_label(item),
        "推送状态": _list_push_label(item),
        "起运港": _first(item, "pol", "pol_cname", default=""),
        "目的港": _first(item, "pod", "pod_cname", default=""),
        "ETD/ETA": _list_eta_ata(item),
        "船名": _first(item, "vessel", default=""),
        "航次": _first(item, "voyage", default=""),
        "订阅时间": _first(item, "subscribe_date", default=""),
    }
    notice = _first(item, "notic_msg", "notice_msg", default="")
    if notice:
        row["提示"] = notice
    return {key: value for key, value in row.items() if value not in (None, "")}


def _subscribe_list_params(
    *,
    keywords: str | None,
    date_from: str | None,
    date_to: str | None,
    carrier: str | None,
    history: bool,
    finished: bool,
    page: int,
    limit: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": page,
        "limit": limit,
        "keywords": (keywords or "").strip() or None,
        "subscribe_date[0]": (date_from or "").strip() or None,
        "subscribe_date[1]": (date_to or "").strip() or None,
        "is_history": "1" if history else None,
        "is_finish": "1" if finished else None,
    }
    carrier_code = (carrier or "").strip()
    if carrier_code:
        params["carrier"] = [carrier_code]
    return params


def run_subscribe_list(
    *,
    keywords: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    carrier: str | None = None,
    history: bool = False,
    finished: bool = False,
    page: int = 1,
    limit: int = 20,
    http: HttpClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """List cargo-tracking subscriptions (A010). Does not consume query quota."""
    key = api_key or load_api_key()
    if not key:
        return {
            "status": "missing_key",
            "tickets": [],
            "chat": [],
            "error": AUTH_HINT,
            "setup_reference": "references/auth.md",
        }

    client = http or _default_http
    params = _subscribe_list_params(
        keywords=keywords,
        date_from=date_from,
        date_to=date_to,
        carrier=carrier,
        history=history,
        finished=finished,
        page=page,
        limit=limit,
    )
    response = client("POST", A010, key, params=params, json_body=None)
    if response.get("code") != 1:
        return {
            "status": "failed",
            "error": _business_error(response),
            "tickets": [],
            "chat": [],
        }

    page_data = response.get("data") if isinstance(response.get("data"), dict) else {}
    rows_raw = page_data.get("data") if isinstance(page_data.get("data"), list) else []
    chat = [
        _list_chat_row(item)
        for item in rows_raw
        if isinstance(item, dict)
    ]
    return {
        "status": "ok",
        "chat": chat,
        "tickets": chat,
        "total": page_data.get("total"),
        "per_page": page_data.get("per_page"),
        "current_page": page_data.get("current_page"),
        "last_page": page_data.get("last_page"),
        "history": response.get("history"),
        "finish_count": response.get("finish_count"),
        "onGoing_count": response.get("onGoing_count"),
        "pol_filter": response.get("pol_filter"),
        "pod_filter": response.get("pod_filter"),
        "carrier_filter": response.get("carrier_filter"),
    }


def export_result(result: dict[str, Any]) -> str:
    path = write_xlsx(
        {
            "摘要": result.get("chat", []),
            "明细": result.get("details", []),
        },
        "cargo-tracking",
    )
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sofreight cargo tracking")
    key_action = parser.add_mutually_exclusive_group()
    key_action.add_argument(
        "--status",
        action="store_true",
        help="Check whether SOF_API_KEY is available to this process",
    )
    key_action.add_argument(
        "--save",
        metavar="KEY",
        help="Set SOF_API_KEY from user-provided key (masked in output; not skill folder)",
    )
    key_action.add_argument(
        "--clear",
        action="store_true",
        help="Clear SOF_API_KEY from process / user persistence",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List subscriptions (A010); does not consume query quota",
    )
    parser.add_argument("--numbers", help="Comma-separated numbers")
    parser.add_argument(
        "--carrier",
        help="Carrier code: for query pick from A002; for --list filter subscriptions",
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="User confirmed this charged query/subscribe (G4 / D9)",
    )
    parser.add_argument("--subscribe", action="store_true")
    parser.add_argument(
        "--partners-confirmed",
        action="store_true",
        help="List cooperating merchants; A006 only",
    )
    parser.add_argument(
        "--keywords",
        help="--list: bl/so/pol/pod/carrier; --partners-confirmed: A006 keywords (e.g. 宁波)",
    )
    parser.add_argument("--date-from", help="Subscribe-list start date YYYY-MM-DD")
    parser.add_argument("--date-to", help="Subscribe-list end date YYYY-MM-DD")
    parser.add_argument(
        "--history",
        action="store_true",
        help="Subscribe-list: include history (is_history=1)",
    )
    parser.add_argument(
        "--finished",
        action="store_true",
        help="Subscribe-list: finished only (is_finish=1)",
    )
    parser.add_argument("--page", type=int, default=1, help="Subscribe-list page (default 1)")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Subscribe-list page size (default 20)",
    )
    parser.add_argument("--export", action="store_true", help="Write Excel after this query")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Write Excel from last successful query cache; no API call",
    )
    args = parser.parse_args()
    managing_key = bool(args.status or args.save is not None or args.clear)
    if managing_key:
        return args
    if args.partners_confirmed or args.export_only:
        return args
    if args.list:
        if args.page < 1 or args.limit < 1:
            parser.error("--page and --limit must be >= 1")
        return args
    if not args.numbers:
        parser.error(
            "--numbers is required unless --list / --partners-confirmed / "
            "--export-only / --status/--save/--clear"
        )
    return args


def run_key_command(args: argparse.Namespace) -> int:
    if args.status:
        key = load_api_key()
        if not key:
            print_json(
                {
                    "status": "missing",
                    "remote_validated": False,
                    "error": AUTH_HINT,
                    "setup_reference": "references/auth.md",
                }
            )
            return MISSING_KEY
        print_json({"status": "ok", "masked": mask_key(key), "remote_validated": False})
        return OK
    if args.save is not None:
        save_api_key(args.save)
        print_json({"status": "saved", "masked": mask_key(args.save.strip())})
        return OK
    credentials_path().unlink(missing_ok=True)
    print_json({"status": "cleared"})
    return OK


def main() -> int:
    args = parse_args()
    if args.status or args.save is not None or args.clear:
        return run_key_command(args)
    if args.partners_confirmed:
        try:
            result = run_partners(keywords=args.keywords)
        except PermissionError:
            print_json({"status": "unauthorized"})
            return UNAUTHORIZED
        print_json(result)
        return MISSING_KEY if result["status"] == "missing_key" else OK
    if args.export_only:
        try:
            path = export_from_cache()
        except FileNotFoundError as exc:
            print_json({"status": "failed", "error": str(exc)})
            return 1
        print_json({"status": "ok", "export_path": path})
        return OK

    if args.list:
        try:
            result = run_subscribe_list(
                keywords=args.keywords,
                date_from=args.date_from,
                date_to=args.date_to,
                carrier=args.carrier,
                history=args.history,
                finished=args.finished,
                page=args.page,
                limit=args.limit,
            )
        except PermissionError:
            print_json({"status": "unauthorized"})
            return UNAUTHORIZED
        print_json(result)
        return MISSING_KEY if result["status"] == "missing_key" else OK

    numbers = [number.strip() for number in args.numbers.split(",")]
    try:
        result = run_batch(
            numbers,
            confirmed=args.confirmed,
            subscribe=args.subscribe,
            carrier=args.carrier,
        )
    except PermissionError:
        print_json({"status": "unauthorized"})
        return UNAUTHORIZED
    if result["status"] in {"ok", "partial"}:
        result["queried_at"] = _queried_at()
        save_query_cache(result)
        result["export_available"] = True
        result["export_hint"] = EXPORT_HINT
        if result.get("source"):
            result["source_cached"] = True
        if args.export:
            result["export_path"] = export_result(result)
    result.pop("details", None)
    result.pop("source", None)
    print_json(result)
    return MISSING_KEY if result["status"] == "missing_key" else OK


if __name__ == "__main__":
    raise SystemExit(main())
