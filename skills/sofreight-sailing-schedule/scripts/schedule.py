import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


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

HttpClient = Callable[..., dict[str, Any]]

A004 = "/DPort/index"
A007 = "/ship_schedule/get_schedule"
PORT_CODE_RE = re.compile(r"^[A-Za-z0-9]{5}$")
QUERY_TYPES = {"", "ALL", "DIRECT", "TRANS"}
SORT_VALUES = {"", "ETD_ASC", "ETD_DESC", "TT_ASC", "TT_DESC"}
CACHE_NAME = "sailing-schedule-last.json"
CHAT_ROW_LIMIT = 30
CHAT_TRUNCATE_HINT = (
    f"首轮对话仅展示每类前 {CHAT_ROW_LIMIT} 条。"
    "完整结果已写入缓存；需要全量明细请明确说「导出」用 --export-only，不会再扣一次查询。"
)
EXPORT_HINT = (
    "聊天里只给清洗摘要。需要 Excel 明细时请明确说「导出」，"
    "我会用 --export-only 生成文件，不会再扣一次查询。"
)
BUSINESS_ERRORS = {
    10002: "需要开通搜航会员",
    500002: "浪花不足",
    500004: "浪花被禁用，联系客服",
}
AUTH_HINT = missing_key_hint(
    'python skills/sofreight-sailing-schedule/scripts/schedule.py --save "<KEY>"'
)


def _payload_data(response: dict[str, Any]) -> Any:
    return response.get("data", response)


def _business_error(response: dict[str, Any]) -> str:
    code = response.get("code")
    mapped = BUSINESS_ERRORS.get(code)
    if mapped:
        return mapped
    return str(response.get("msg") or response.get("message") or f"接口返回 code={code}")


def normalize_port_code(raw: str | None, *, field: str) -> tuple[str | None, str | None]:
    value = (raw or "").strip().upper()
    if not value:
        return None, f"缺少{field}"
    if PORT_CODE_RE.fullmatch(value) is None:
        return None, f"{field}须为 5 位搜航港口五字码"
    return value, None


def _port_records(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = _payload_data(response)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        inner = data.get("data")
        rows = inner if isinstance(inner, list) else []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _public_port(row: dict[str, Any]) -> dict[str, str]:
    code = str(
        row.get("port_code")
        or row.get("portCode")
        or row.get("code")
        or ""
    ).strip().upper()
    cname = str(
        row.get("port_cname")
        or row.get("portCname")
        or row.get("port_name_cn")
        or row.get("portNameCn")
        or ""
    ).strip()
    name = str(
        row.get("port_name")
        or row.get("portName")
        or ""
    ).strip()
    return {
        "port_code": code,
        "port_cname": cname or name or code,
        "port_name": name,
    }


def search_ports(
    keywords: str | None = None,
    *,
    port_code: str | None = None,
    client: HttpClient,
    api_key: str,
    rows: int = 50,
) -> list[dict[str, str]]:
    params: dict[str, Any] = {
        "page": 1,
        "rows": rows,
        "with_group": 0,
    }
    if keywords:
        params["keywords"] = keywords
    if port_code:
        params["port_code"] = port_code
    response = client(
        "GET",
        A004,
        api_key,
        params=params,
        json_body=None,
        form_body=None,
    )
    if response.get("code") != 1:
        raise RuntimeError(_business_error(response))
    seen: set[str] = set()
    ports: list[dict[str, str]] = []
    for row in _port_records(response):
        item = _public_port(row)
        if not item["port_code"] or item["port_code"] in seen:
            continue
        seen.add(item["port_code"])
        ports.append(item)
    return ports


def resolve_port_side(
    *,
    role: str,
    code: str | None,
    name: str | None,
    client: HttpClient,
    api_key: str,
) -> dict[str, Any]:
    """解析起运港/目的港。多候选时 status=needs_port，禁止猜测。"""
    label = "起运港" if role == "pol" else "目的港"
    explicit = (code or "").strip()
    raw_name = (name or "").strip()

    def _validate_code(port_code: str, *, input_text: str) -> dict[str, Any]:
        try:
            candidates = search_ports(
                port_code=port_code,
                client=client,
                api_key=api_key,
            )
        except PermissionError:
            raise
        except Exception as exc:
            return {
                "role": role,
                "input": input_text,
                "status": "failed",
                "error": f"{label}五字码校验失败：{exc}",
            }
        matched = [item for item in candidates if item["port_code"] == port_code]
        if not matched:
            return {
                "role": role,
                "input": input_text,
                "status": "failed",
                "error": f"{label}五字码「{port_code}」在搜航港口主数据中不存在或不可用",
            }
        chosen = matched[0]
        return {
            "role": role,
            "input": input_text,
            "status": "resolved",
            "port_code": chosen["port_code"],
            "port_cname": chosen["port_cname"],
            "port_name": chosen["port_name"],
        }

    if explicit:
        port_code, err = normalize_port_code(explicit, field=f"{label}五字码")
        if err:
            return {"role": role, "input": explicit, "status": "failed", "error": err}
        assert port_code is not None
        return _validate_code(port_code, input_text=explicit)

    if not raw_name:
        return {
            "role": role,
            "input": "",
            "status": "failed",
            "error": f"缺少{label}（可用 --{role} 港名或 --{role}-code 五字码）",
        }
    if PORT_CODE_RE.fullmatch(raw_name.upper()):
        return _validate_code(raw_name.upper(), input_text=raw_name)

    try:
        candidates = search_ports(raw_name, client=client, api_key=api_key)
    except PermissionError:
        raise
    except Exception as exc:
        return {
            "role": role,
            "input": raw_name,
            "status": "failed",
            "error": f"{label}港口搜索失败：{exc}",
        }
    if not candidates:
        return {
            "role": role,
            "input": raw_name,
            "status": "failed",
            "error": f"未找到与「{raw_name}」匹配的搜航港口五字码",
        }
    if len(candidates) == 1:
        chosen = candidates[0]
        return {
            "role": role,
            "input": raw_name,
            "status": "resolved",
            "port_code": chosen["port_code"],
            "port_cname": chosen["port_cname"],
            "port_name": chosen["port_name"],
        }
    # 多候选：给可读候选表 + 推荐（首位通常是全港/主港汇总），帮用户快速决策
    table_rows = ["| 序号 | 五字码 | 中文名 | 英文名 |", "|---|---|---|---|"]
    for idx, item in enumerate(candidates, start=1):
        mark = "（推荐）" if idx == 1 else ""
        table_rows.append(
            f"| {idx} | {item['port_code']} | {item['port_cname']} | {item['port_name']}{mark} |"
        )
    hint = (
        f"候选第 1 个通常是「{raw_name}」的全港/主港汇总；"
        "用户无特定码头要求时推荐选它，避免误选到具体港区/码头。"
    )
    return {
        "role": role,
        "input": raw_name,
        "status": "needs_port",
        "candidates": candidates,
        "recommended": candidates[0],
        "candidates_view": "\n".join(table_rows),
        "hint": hint,
        "prompt": (
            f"{label}「{raw_name}」匹配到 {len(candidates)} 个码头候选，"
            "请把候选表展示给用户确认（推荐第 1 个，通常为全港/主港）。"
        ),
    }


def validate_query_type(raw: str | None) -> tuple[str, str | None]:
    value = (raw or "").strip().upper()
    if value not in QUERY_TYPES:
        return "", f"query_type 仅支持 DIRECT / TRANS / ALL，收到 {raw!r}"
    return value, None


def validate_sort(raw: str | None) -> tuple[str, str | None]:
    value = (raw or "").strip().upper()
    if value not in SORT_VALUES:
        return "", f"sort 仅支持 ETD_ASC / ETD_DESC / TT_ASC / TT_DESC，收到 {raw!r}"
    return value, None


def _schedule_fields(sched: dict[str, Any] | None) -> dict[str, Any]:
    item = sched or {}
    return {
        "船名": item.get("vessel") or "",
        "航次": item.get("voyage") or "",
        "预计开船时间": item.get("etd") or "",
        "预计到达时间": item.get("eta") or "",
        "实际开船时间": item.get("atd") or "",
    }


def _dock_plan(dock: dict[str, Any] | None) -> dict[str, Any]:
    item = dock or {}
    return {
        "码头": item.get("terminal") or "",
        "开港时间": item.get("cyOpening") or "",
        "截港时间": item.get("portCutOff") or "",
        "港口中文名": item.get("portCodeCName") or "",
        "港口英文名": item.get("portCodeName") or "",
    }


def etl_direct(direct_list: Any) -> list[dict[str, Any]]:
    """清洗全部直航班次；字段映射与旧 sof-SailingSchedule 一致，不截断。"""
    if not isinstance(direct_list, dict) or not direct_list:
        return []
    rows: list[dict[str, Any]] = []
    for key, group_items in direct_list.items():
        if not isinstance(group_items, list):
            continue
        for item in group_items:
            if not isinstance(item, dict):
                continue
            schedules = item.get("scheduleList") or []
            if not isinstance(schedules, list) or not schedules:
                schedules = [{}]
            dock = item.get("dock_data") if isinstance(item.get("dock_data"), dict) else {}
            for sched in schedules:
                sched_dict = sched if isinstance(sched, dict) else {}
                row = {
                    "共舱组": item.get("cabinGroup") or key,
                    "船司": item.get("carrier") or "",
                    "航线代码": item.get("serviceCode") or "",
                    "运输类型": "直航",
                    "挂靠码头": item.get("polTerminal") or "",
                    "目的港码头": item.get("destTerminal") or "",
                    "周几": item.get("weekly") or "",
                    "航程": item.get("tt") or "",
                    "空班标记": bool(item.get("allBlank") or False),
                    **_schedule_fields(sched_dict),
                    "码头计划": _dock_plan(dock),
                }
                rows.append(row)
    return rows


def etl_transfer(transfer_list: Any) -> list[dict[str, Any]]:
    """清洗全部中转方案；字段映射与旧 sof-SailingSchedule 一致，不截断。"""
    if not isinstance(transfer_list, list) or not transfer_list:
        return []
    rows: list[dict[str, Any]] = []
    for item in transfer_list:
        if not isinstance(item, dict):
            continue
        schedules = item.get("scheduleList") or []
        if not isinstance(schedules, list):
            schedules = []
        first = schedules[0] if schedules else {}
        second = schedules[1] if len(schedules) > 1 else {}
        if not isinstance(first, dict):
            first = {}
        if not isinstance(second, dict):
            second = {}
        rows.append(
            {
                "船司": item.get("carrier") or "",
                "航线代码": item.get("serviceCode") or "",
                "运输类型": "中转",
                "中转港": item.get("transferPort") or "",
                "挂靠码头": item.get("polTerminal") or "",
                "周几": item.get("weekly") or "",
                "航程": item.get("tt") or "",
                "空班标记": bool(item.get("allBlank") or False),
                "一程船名": first.get("vessel") or "",
                "一程航次": first.get("voyage") or "",
                "一程ETD": first.get("etd") or "",
                "一程ETA": first.get("eta") or "",
                "二程船名": second.get("vessel") or "",
                "二程航次": second.get("voyage") or "",
                "二程ETD": second.get("etd") or "",
                "二程ETA": second.get("eta") or "",
            }
        )
    return rows


def cache_path() -> Path:
    return exports_dir() / CACHE_NAME


def _queried_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_query_cache(result: dict[str, Any]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pol_code": result.get("pol_code"),
        "dest_code": result.get("dest_code"),
        "direct": result.get("_full_direct") or result.get("direct") or [],
        "transfer": result.get("_full_transfer") or result.get("transfer") or [],
        "source": result.get("source"),
        "queried_at": result.get("queried_at") or _queried_at(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_query_cache() -> dict[str, Any] | None:
    path = cache_path()
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
        result["source_cached"] = True
        result["pol_code"] = cache.get("pol_code")
        result["dest_code"] = cache.get("dest_code")
        result["queried_at"] = cache.get("queried_at")
    if fetched.get("error"):
        result["error"] = fetched["error"]
    return result


def _flatten_direct_row(row: dict[str, Any]) -> dict[str, Any]:
    dock = row.get("码头计划") if isinstance(row.get("码头计划"), dict) else {}
    flat = {key: value for key, value in row.items() if key != "码头计划"}
    flat.update(
        {
            "码头": dock.get("码头") or "",
            "开港时间": dock.get("开港时间") or "",
            "截港时间": dock.get("截港时间") or "",
            "港口中文名": dock.get("港口中文名") or "",
            "港口英文名": dock.get("港口英文名") or "",
        }
    )
    return flat


def sheets_from_source(
    source: dict[str, Any] | None,
    *,
    direct: list[dict[str, Any]] | None = None,
    transfer: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Excel 从源投影；无源时退回已清洗列表（仍不二次打接口）。

    直航/中转各自按开船时间升序，方便在 Excel 里直接看近期班次。
    """
    if isinstance(source, dict):
        direct_rows = etl_direct(source.get("directList"))
        transfer_rows = etl_transfer(source.get("transferList"))
    else:
        direct_rows = list(direct or [])
        transfer_rows = list(transfer or [])
    direct_rows = sorted(
        direct_rows,
        key=lambda row: str(row.get("预计开船时间") or "") or "\uffff",
    )
    transfer_rows = sorted(
        transfer_rows,
        key=lambda row: str(row.get("一程ETD") or "") or "\uffff",
    )
    return {
        "直航": [_flatten_direct_row(row) for row in direct_rows],
        "中转": list(transfer_rows),
    }


def export_result(result: dict[str, Any]) -> str:
    sheets = sheets_from_source(
        result.get("source") if isinstance(result.get("source"), dict) else None,
        direct=result.get("_full_direct") or result.get("direct") or [],
        transfer=result.get("_full_transfer") or result.get("transfer") or [],
    )
    return str(write_xlsx(sheets, "sailing-schedule"))


def export_from_cache() -> str:
    path = cache_path()
    if not path.is_file():
        raise FileNotFoundError("没有可导出的船期缓存，请先成功查询一次船期")
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source")
    sheets = sheets_from_source(
        source if isinstance(source, dict) else None,
        direct=payload.get("direct") or [],
        transfer=payload.get("transfer") or [],
    )
    if not sheets["直航"] and not sheets["中转"]:
        raise FileNotFoundError("船期缓存里没有可导出的直航或中转数据")
    return str(write_xlsx(sheets, "sailing-schedule"))


def _present_chat_rows(
    direct: list[dict[str, Any]],
    transfer: list[dict[str, Any]],
) -> dict[str, Any]:
    """首轮 IM 每类最多 CHAT_ROW_LIMIT 条；完整列表留给缓存/Excel。"""
    direct_truncated = len(direct) > CHAT_ROW_LIMIT
    transfer_truncated = len(transfer) > CHAT_ROW_LIMIT
    payload: dict[str, Any] = {
        "direct_count": len(direct),
        "transfer_count": len(transfer),
        "direct": direct[:CHAT_ROW_LIMIT],
        "transfer": transfer[:CHAT_ROW_LIMIT],
        "chat_limit": CHAT_ROW_LIMIT,
        "direct_truncated": direct_truncated,
        "transfer_truncated": transfer_truncated,
    }
    if direct_truncated or transfer_truncated:
        payload["chat_hint"] = CHAT_TRUNCATE_HINT
    return payload


# ---------------------------------------------------------------------------
# 统一对话视图（view）：所有 Agent/IM 前端展示本 skill 结果的唯一事实来源。
# 规则见 references/display.md。禁止调用方自行重排——保持多端展示一致。
# ---------------------------------------------------------------------------
_CABIN_PART_RE = re.compile(r"^\s*([A-Za-z0-9]+?)(?:\(([^)]*)\))?\s*$")
_BLANK_VESSELS = {"BLANK", "BLANK SAILING", "BLANK SAILINGS", "BLANKING"}


def _norm_cell(raw: Any) -> str:
    """清洗单元格：None→空串；list/tuple→顿号连接文本（如中转港 ['PUSAN']）。"""
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        return "、".join(_norm_cell(item) for item in raw)
    text = str(raw).strip()
    return text


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


def _compact_date(raw: Any, *, with_year: bool = False) -> str:
    """'2026-09-11 20:00:00' → '9/11 20:00'；整点/无时间只给 '9/11'。"""
    text = _norm_cell(raw)
    if not text:
        return ""
    parts = text.split(" ")
    date_part = parts[0]
    if len(date_part) != 10 or date_part[4] != "-":
        return text  # 非标准日期，原样返回
    try:
        month = int(date_part[5:7])
        day = int(date_part[8:10])
    except ValueError:
        return text
    md = f"{month}/{day}"
    if with_year:
        md = f"{date_part[:4]}/{md}"
    time_part = parts[1][:5] if len(parts) > 1 else ""
    if time_part and time_part != "00:00":
        md = f"{md} {time_part}"
    return md


def _split_cabin_group(group: str) -> tuple[list[str], list[str]]:
    """解析共舱组 'GSL(KCI)/ONE(WA1)/ZIM(FAX)' → (船司列表, 航线代码列表)。"""
    carriers: list[str] = []
    svcs: list[str] = []
    for part in str(group or "").split("/"):
        m = _CABIN_PART_RE.match(part)
        if not m:
            continue
        carrier = m.group(1)
        svc = (m.group(2) or "").strip()
        if carrier and carrier not in carriers:
            carriers.append(carrier)
        if svc and svc not in svcs:
            svcs.append(svc)
    return carriers, svcs


def _is_blank_row(row: dict[str, Any]) -> bool:
    """空班行：接口空班标记，或船名 BLANK SAILING/空名且无航次。"""
    if row.get("空班标记"):
        return True
    vessel = _norm_cell(row.get("船名"))
    voyage = _norm_cell(row.get("航次"))
    if not vessel and not voyage:
        return True
    return bool(vessel) and vessel.upper() in _BLANK_VESSELS


def _group_key(row: dict[str, Any]) -> str:
    group = _norm_cell(row.get("共舱组"))
    if group:
        return group
    carrier = _norm_cell(row.get("船司"))
    svc = _norm_cell(row.get("航线代码"))
    return f"{carrier}({svc})" if carrier else "未知服务"


def _vessel_label(vessel: str, voyage: str) -> str:
    vessel = _norm_cell(vessel)
    voyage = _norm_cell(voyage)
    if vessel and voyage:
        return f"{vessel} {voyage}"
    return vessel or voyage or "—"


def build_chat_view(result: dict[str, Any]) -> str:
    """生成统一对话展示文本（markdown）。

    - 直航：按共舱组聚合成「航线概览」——同一物理班次（船名+航次+开船日）去重，
      空班从班次行剥离成服务级「空班」列，数据异常行（航程 0 天等）不再混入主表；
      每线给「近 3 班」而非平铺 30 行，根治拥挤与错乱。
    - 中转：每方案一行，只留核心列。
    - 头部：路线 + 全量统计；尾部：截断提示 + 标准 follow-up 话术。
    """
    direct = list(result.get("_full_direct") or result.get("direct") or [])
    transfer = list(result.get("_full_transfer") or result.get("transfer") or [])
    direct_count = int(result.get("direct_count") or len(direct))
    transfer_count = int(result.get("transfer_count") or len(transfer))

    pol = result.get("pol") or {}
    dest = result.get("dest") or {}
    pol_name = _norm_cell(pol.get("port_cname")) or _norm_cell(pol.get("port_name"))
    dest_name = _norm_cell(dest.get("port_cname")) or _norm_cell(dest.get("port_name"))
    pol_code = _norm_cell(pol.get("port_code")) or result.get("pol_code") or ""
    dest_code = _norm_cell(dest.get("port_code")) or result.get("dest_code") or ""
    route = f"{pol_name}（{pol_code}）→ {dest_name}（{dest_code}）"

    if not direct and not transfer:
        return f"**{route} 船期**：当前组合暂无船期，请更换查询条件。"

    # ---- 直航按共舱组聚合 ----
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    seen_sailings: set[tuple[str, str, str]] = set()
    first_owner: dict[tuple[str, str, str], str] = {}
    merge_map: dict[str, str] = {}
    for row in direct:
        gkey = _group_key(row)
        if gkey not in groups:
            groups[gkey] = {
                "carriers": [],
                "svcs": [],
                "lead_svc": "",
                "terminals": [],
                "dest_terminals": [],
                "tts": [],
                "sailings": [],
                "blanks": [],
            }
            order.append(gkey)
        g = groups[gkey]
        carriers, svcs = _split_cabin_group(gkey)
        row_carrier = _norm_cell(row.get("船司"))
        for item in (carriers or ([row_carrier] if row_carrier else [])):
            if item and item not in g["carriers"]:
                g["carriers"].append(item)
        for svc in svcs:
            if svc and svc not in g["svcs"]:
                g["svcs"].append(svc)
        row_svc = _norm_cell(row.get("航线代码"))
        if row_svc and row_svc not in g["svcs"]:
            g["svcs"].append(row_svc)
        if not g["lead_svc"] and row_svc:
            g["lead_svc"] = row_svc
        term = _norm_cell(row.get("挂靠码头"))
        if term and term not in g["terminals"]:
            g["terminals"].append(term)
        dest_term = _norm_cell(row.get("目的港码头"))
        if dest_term and dest_term not in g["dest_terminals"]:
            g["dest_terminals"].append(dest_term)
        tt = _norm_cell(row.get("航程"))
        if tt and tt not in g["tts"]:
            g["tts"].append(tt)
        if _is_blank_row(row):
            # 空班按日期去重：共舱伙伴会给同一空班重复多行
            etd = _norm_cell(row.get("预计开船时间"))
            if etd and all(b[:10] != etd[:10] for b in g["blanks"]):
                g["blanks"].append(etd)
            continue
        vessel = _norm_cell(row.get("船名"))
        voyage = _norm_cell(row.get("航次"))
        etd = _norm_cell(row.get("预计开船时间"))
        if not vessel or not etd:
            continue
        # 船名+航次+开船日：同船同日不同航次各自保留；共舱伙伴完全相同的班次只留一条
        sailing_key = (vessel.upper(), voyage.upper(), etd[:10])
        if sailing_key in seen_sailings:
            # 共舱伙伴重复班次：只留首条；整组若再无独有班次，后折叠进首组
            if gkey not in merge_map:
                merge_map[gkey] = first_owner[sailing_key]
            continue
        seen_sailings.add(sailing_key)
        first_owner[sailing_key] = gkey
        g["sailings"].append({"etd": etd, "vessel": vessel, "voyage": voyage})

    # 折叠孤儿组：班次全被首组吸收（同船队被 API 拆成多个共舱组标签时），
    # 其空班并入首组，避免出现"只有空班没有班次"的怪行
    for gkey in list(order):
        g = groups[gkey]
        if not g["sailings"] and gkey in merge_map:
            target = groups[merge_map[gkey]]
            for b in g["blanks"]:
                if all(existing[:10] != b[:10] for existing in target["blanks"]):
                    target["blanks"].append(b)
            del groups[gkey]
            order.remove(gkey)

    # ---- 收集全部年份，判断日期是否需要带年 ----
    years: set[str] = set()
    for g in groups.values():
        for s in g["sailings"]:
            years.add(s["etd"][:4])
        for b in g["blanks"]:
            years.add(b[:4])
    for row in transfer:
        years.add(_norm_cell(row.get("一程ETD"))[:4])
        years.add(_norm_cell(row.get("一程ETA"))[:4])
        years.add(_norm_cell(row.get("二程ETD"))[:4])
        years.add(_norm_cell(row.get("二程ETA"))[:4])
    years.discard("")
    with_year = len(years) > 1
    year_note = "" if not years else (
        f"，日期未标年份均为 {sorted(years)[0]} 年" if not with_year else "，跨年班次日期已带年份"
    )

    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(f"**{route} 船期**")
    lines.append(
        f"直航 **{direct_count}** 条 · 中转 **{transfer_count}** 条"
        f"{year_note}（查询于 {today[5:].replace('-', '/')}）"
    )

    # ---- 直航概览 ----
    if direct:
        lines.append("")
        lines.append("**直航 · 航线概览**（按共舱航线合并，同船班次去重；另可导出全量明细）")
        lines.append("")
        lines.append("| 承运船司（航线代码） | 挂靠码头 | 航程 | 空班 | 近 3 班（开船日 · 船名） |")
        lines.append("|---|---|---|---|---|")
        shown = 0
        skipped_empty = 0
        for gkey in order:
            g = groups[gkey]
            # 空壳组（无班次无空班，接口噪声）不占行
            if not g["sailings"] and not g["blanks"]:
                skipped_empty += 1
                continue
            if shown >= 12:
                break
            carriers_all = g["carriers"]
            carriers_disp = "·".join(carriers_all[:3]) or "—"
            if len(carriers_all) > 3:
                carriers_disp = f"{carriers_disp} 等{len(carriers_all)}家"
            # 航线代码仅在整组唯一时展示（多代码=同一船队各伙伴代号，聊天里展示无益）
            svc_disp = g["svcs"][0] if len(g["svcs"]) == 1 else ""
            service_cell = (
                f"{carriers_disp}（{_md_escape(svc_disp)}）" if svc_disp else carriers_disp
            )
            terminals_disp = "、".join(g["terminals"]) or "—"
            tts_clean = [tt for tt in g["tts"] if tt not in ("0天", "0")]
            tts_disp = "、".join(tts_clean or g["tts"]) or "—"
            # 空班日期（升序）
            blanks_disp = "、".join(
                _compact_date(b, with_year=with_year)
                for b in sorted(g["blanks"])
            ) or "—"
            # 近 3 班：优先未来，不足用最近历史补足；历史班次标注「已开」
            sailings = sorted(g["sailings"], key=lambda s: s["etd"])
            future = [s for s in sailings if s["etd"][:10] >= today]
            if len(future) < 3:
                past = [s for s in sailings if s["etd"][:10] < today]
                recent = sorted(past, key=lambda s: s["etd"])[- (3 - len(future)):]
                sailings_view = recent + future[:3]
            else:
                sailings_view = future[:3]
            parts = []
            for s in sailings_view:
                label = f"{_compact_date(s['etd'], with_year=with_year)} {s['vessel']}"
                if s["etd"][:10] < today:
                    label += "（已开）"
                parts.append(label)
            sailings_disp = "；".join(parts) or "—"
            lines.append(_md_row([
                service_cell,
                _md_escape(terminals_disp),
                _md_escape(tts_disp),
                _md_escape(blanks_disp),
                _md_escape(sailings_disp),
            ]))
            shown += 1
        if remaining_after_note := (len(order) - shown - skipped_empty):
            lines.append("")
            lines.append(f"> 另有 {remaining_after_note} 条航线未展开，如需全量请筛选或导出。")
        dest_terminals = []
        for g in groups.values():
            for dt in g["dest_terminals"]:
                if dt not in dest_terminals:
                    dest_terminals.append(dt)
        if len(dest_terminals) == 1:
            lines.append("")
            lines.append(f"> 目的港码头：{dest_terminals[0]}")
        lines.append("")
        lines.append("> 空班＝已宣布停开的班期。")

    # ---- 中转 ----
    if transfer:
        transfer_shown = len(transfer)
        heading = "**中转方案**"
        if transfer_count > transfer_shown:
            heading = f"**中转方案**（前 {transfer_shown}/{transfer_count} 条）"
        lines.append("")
        lines.append(heading)
        lines.append("")
        lines.append("| 船司 | 航线代码 | 中转港 | 航程 | 开船 ETD | 到港 ETA | 船名 · 航次 |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in transfer[:30]:
            carrier = _norm_cell(row.get("船司")) or "—"
            svc = _norm_cell(row.get("航线代码")) or "—"
            port = _norm_cell(row.get("中转港")).upper() or "—"
            tt = _norm_cell(row.get("航程")) or "—"
            etd1 = _norm_cell(row.get("一程ETD"))
            eta1 = _norm_cell(row.get("一程ETA"))
            etd2 = _norm_cell(row.get("二程ETD"))
            eta2 = _norm_cell(row.get("二程ETA"))
            depart = _compact_date(etd1 or etd2, with_year=with_year) or "—"
            arrival = _compact_date(eta2 or eta1, with_year=with_year) or "—"
            legs = _vessel_label(row.get("一程船名"), row.get("一程航次"))
            second_vessel = _norm_cell(row.get("二程船名"))
            if second_vessel:
                legs = f"{legs} → {_vessel_label(second_vessel, row.get('二程航次'))}"
            lines.append(_md_row([
                _md_escape(carrier),
                _md_escape(svc),
                _md_escape(port),
                _md_escape(tt),
                _md_escape(depart),
                _md_escape(arrival),
                _md_escape(legs),
            ]))

    # ---- 尾部 follow-up 话术 ----
    truncated = direct_count > 30 or transfer_count > 30
    if truncated:
        lines.append("")
        lines.append("> 完整班次明细未在对话中平铺（避免拥挤）：可按 **船司 / 开航日期段 / 船名·航次** 再筛，")
        lines.append("> 或直接说「**导出**」拿 Excel 全量明细（含共舱、码头计划等所有字段）。")
    return "\n".join(lines)


def _md_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _default_http(
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


def run_query(
    *,
    pol: str = "",
    dest: str = "",
    pol_code: str = "",
    dest_code: str = "",
    confirmed: bool = False,
    carrier: str = "",
    weekly: str = "",
    vessel: str = "",
    voyage: str = "",
    query_type: str = "",
    etd_1: str = "",
    etd_2: str = "",
    sort: str = "",
    skip_blank: bool = False,
    http: HttpClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    del confirmed  # 兼容旧 CLI；船期查询不扣次数/浪花，不再要求确认
    key = api_key or load_api_key()
    if not key:
        return {
            "status": "missing_key",
            "error": AUTH_HINT,
            "setup_reference": "references/auth.md",
        }

    qtype, qtype_err = validate_query_type(query_type)
    sort_value, sort_err = validate_sort(sort)
    errors = [err for err in (qtype_err, sort_err) if err]
    if errors:
        return {"status": "failed", "error": "；".join(errors)}

    client = http or _default_http
    pol_side = resolve_port_side(
        role="pol",
        code=pol_code,
        name=pol,
        client=client,
        api_key=key,
    )
    dest_side = resolve_port_side(
        role="dest",
        code=dest_code,
        name=dest,
        client=client,
        api_key=key,
    )

    if pol_side["status"] == "failed" or dest_side["status"] == "failed":
        parts = [
            side.get("error")
            for side in (pol_side, dest_side)
            if side["status"] == "failed" and side.get("error")
        ]
        return {
            "status": "failed",
            "error": "；".join(parts),
            "pol": pol_side,
            "dest": dest_side,
        }

    needs = [
        side for side in (pol_side, dest_side) if side["status"] == "needs_port"
    ]
    if needs:
        prompts = [side.get("prompt") or "" for side in needs]
        return {
            "status": "needs_port",
            "prompt": " ".join(prompts).strip(),
            "needs_port_sides": [side["role"] for side in needs],
            "pol": pol_side,
            "dest": dest_side,
        }

    pol_resolved = str(pol_side["port_code"])
    dest_resolved = str(dest_side["port_code"])

    form = {
        "pol_code": pol_resolved,
        "dest_code": dest_resolved,
        "carrier": carrier or "",
        "weekly": weekly or "",
        "vessel": vessel or "",
        "voyage": voyage or "",
        "query_type": qtype,
        "etd_1": etd_1 or "",
        "etd_2": etd_2 or "",
        "sort": sort_value,
        "src_type": "AI",
        # 船期查询当前不扣次数/浪花；传 0 表示不消费代币
        "confirm": 0,
        "is_skip_blank_sailing": 1 if skip_blank else 0,
    }
    try:
        response = client(
            "POST",
            A007,
            key,
            params=None,
            json_body=None,
            form_body=form,
        )
    except PermissionError:
        raise
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "pol_code": pol_resolved,
            "dest_code": dest_resolved,
            "pol": pol_side,
            "dest": dest_side,
        }

    if response.get("code") != 1:
        return {
            "status": "failed",
            "error": _business_error(response),
            "pol_code": pol_resolved,
            "dest_code": dest_resolved,
            "pol": pol_side,
            "dest": dest_side,
        }

    data = _payload_data(response)
    data = data if isinstance(data, dict) else {}
    direct = etl_direct(data.get("directList"))
    transfer = etl_transfer(data.get("transferList"))
    message = "查询成功，已返回全部直航和中转船期。"
    if not direct and not transfer:
        message = "当前组合暂无船期，请更换查询条件"

    chat = _present_chat_rows(direct, transfer)
    if chat.get("direct_truncated") or chat.get("transfer_truncated"):
        message = (
            f"查询成功。直航 {chat['direct_count']} 条、中转 {chat['transfer_count']} 条；"
            f"首轮每类仅展示前 {CHAT_ROW_LIMIT} 条，完整结果在缓存/Excel。"
        )

    return {
        "status": "ok",
        "message": message,
        "pol_code": pol_resolved,
        "dest_code": dest_resolved,
        "pol": pol_side,
        "dest": dest_side,
        "source": data,
        "_full_direct": direct,
        "_full_transfer": transfer,
        **chat,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sofreight sailing schedule")
    key_action = parser.add_mutually_exclusive_group()
    key_action.add_argument("--status", action="store_true")
    key_action.add_argument("--save", metavar="KEY")
    key_action.add_argument("--clear", action="store_true")
    parser.add_argument("--pol", default="", help="起运港中文/英文名，或五字码")
    parser.add_argument("--dest", default="", help="目的港中文/英文名，或五字码")
    parser.add_argument("--pol-code", default="", help="起运港五字码（多候选时由用户选定）")
    parser.add_argument("--dest-code", default="", help="目的港五字码（多候选时由用户选定）")
    parser.add_argument("--carrier", default="", help="船司代码")
    parser.add_argument("--weekly", default="", help="周几")
    parser.add_argument("--vessel", default="", help="船名")
    parser.add_argument("--voyage", default="", help="航次")
    parser.add_argument("--query-type", default="", help="DIRECT / TRANS / ALL")
    parser.add_argument("--etd-start", default="", dest="etd_1", help="开航日起 YYYY-MM-DD")
    parser.add_argument("--etd-end", default="", dest="etd_2", help="开航日止 YYYY-MM-DD")
    parser.add_argument("--sort", default="", help="ETD_ASC / ETD_DESC / TT_ASC / TT_DESC")
    parser.add_argument(
        "--skip-blank",
        action="store_true",
        help="过滤空班（is_skip_blank_sailing=1）",
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="兼容旧参数；船期查询不扣费，无需确认即可查询",
    )
    parser.add_argument(
        "--partners-confirmed",
        action="store_true",
        help="List cooperating merchants; A006 only",
    )
    parser.add_argument(
        "--keywords",
        help="A006 search keywords from the user (e.g. 宁波); do not infer from last query",
    )
    parser.add_argument("--export", action="store_true", help="查询成功后导出 Excel")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="从上次成功查询缓存导出 Excel，不打付费接口",
    )
    args = parser.parse_args()
    managing_key = bool(args.status or args.save is not None or args.clear)
    if managing_key:
        return args
    if args.partners_confirmed or args.export_only:
        return args
    if not (args.pol or args.pol_code) or not (args.dest or args.dest_code):
        parser.error(
            "起运港与目的港必填：可用 --pol/--dest（港名或五字码），"
            "或多候选确认后用 --pol-code/--dest-code；"
            "或使用 --partners-confirmed / --status/--save/--clear / --export-only"
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
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            print_json({"status": "failed", "error": str(exc)})
            return 1
        print_json({"status": "ok", "export_path": path})
        return OK

    try:
        result = run_query(
            pol=args.pol,
            dest=args.dest,
            pol_code=args.pol_code,
            dest_code=args.dest_code,
            confirmed=args.confirmed,
            carrier=args.carrier,
            weekly=args.weekly,
            vessel=args.vessel,
            voyage=args.voyage,
            query_type=args.query_type,
            etd_1=args.etd_1,
            etd_2=args.etd_2,
            sort=args.sort,
            skip_blank=args.skip_blank,
        )
    except PermissionError:
        print_json({"status": "unauthorized"})
        return UNAUTHORIZED

    if result["status"] == "ok":
        result["queried_at"] = _queried_at()
        save_query_cache(result)
        result["source_cached"] = True
        result["export_available"] = True
        result["export_hint"] = EXPORT_HINT
        # 统一对话视图：Agent 展示本字段，禁止自行重排（references/display.md）
        result["view"] = build_chat_view(result)
        if args.export:
            try:
                result["export_path"] = export_result(result)
            except ModuleNotFoundError as exc:
                # 查询已成功：保留 status=ok 与 view，单独报告导出失败
                result["export_error"] = str(exc)
                result["export_available"] = False
    result.pop("source", None)
    result.pop("_full_direct", None)
    result.pop("_full_transfer", None)
    print_json(result)
    return MISSING_KEY if result["status"] == "missing_key" else OK


if __name__ == "__main__":
    raise SystemExit(main())
