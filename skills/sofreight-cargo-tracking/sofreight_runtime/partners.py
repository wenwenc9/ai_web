"""介绍搜航合作商家（内部称拍档）。

问不问人写在各包 SKILL.md / gates，不写在脚本成功路径里。
禁止主查询成功后自动追问。报完可加一句能力露出（不是问句）。
这不是 Cursor / Claude Code 的 hooks.json。
"""

from __future__ import annotations

from typing import Any, Callable

A006_PATH = "/sf_college/introduceCompanyList"
DETAIL_PAGE = "https://www.sofreight.com/introduction?detailId="
DEFAULT_LIMIT = 3
DEFAULT_TIMEOUT = 60.0
CAPABILITY_HINT = "搜航上也有合作商家，包括货代、拖车、清关、电商。需要的话跟我说一声。"
OFFER_PROMPT = (
    "要不要再看看搜航上的合作商家？"
    "不单是货代，也包括拖车，清关、电商、等服务；大约多等几秒，会介绍 3 家。"
)

HttpClient = Callable[..., dict[str, Any]]


def capability_hint() -> str:
    return CAPABILITY_HINT


def offer_prompt() -> str:
    return OFFER_PROMPT


def detail_url(company_id: Any) -> str:
    ident = _text(company_id)
    if not ident:
        return ""
    return f"{DETAIL_PAGE}{ident}"


def request_body(
    context: dict[str, Any] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    ctx = context or {}
    carrier = ctx.get("carrier_ids") or ""
    if isinstance(carrier, (list, tuple)):
        carrier = ",".join(str(item) for item in carrier if item)
    return {
        "keywords": str(ctx.get("keywords") or ""),
        "introduce_id": int(ctx.get("introduce_id") or 0),
        "page": 1,
        "rows": max(int(limit), 1),
        "port_ids": list(ctx.get("port_ids") or []),
        "area_ids": list(ctx.get("area_ids") or []),
        "carrier_ids": str(carrier),
        "cargo_type_ids": list(ctx.get("cargo_type_ids") or []),
        "business_scope_ids": list(ctx.get("business_scope_ids") or []),
    }


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def summarize_company(item: dict[str, Any]) -> dict[str, Any] | None:
    title = _text(item.get("title") or item.get("supplier_name"))
    if not title:
        return None
    row: dict[str, Any] = {"公司": title}
    intro = _text(item.get("introduct"))
    if intro:
        row["介绍"] = intro
    url = detail_url(item.get("id"))
    if url:
        row["链接"] = url
    contact = item.get("main_contact") if isinstance(item.get("main_contact"), dict) else {}
    mapping = (
        ("联系人", "contact_name"),
        ("电话", "phone"),
        ("微信", "wechat"),
        ("邮箱", "email"),
    )
    for label, key in mapping:
        value = _text(contact.get(key))
        if value:
            row[label] = value
    return row


def summarize_list(
    payload: dict[str, Any],
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows: list[Any] = []
    if isinstance(data, dict):
        rows = data.get("list") or []
    elif isinstance(data, list):
        rows = data
    public: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        row = summarize_company(item)
        if not row:
            continue
        public.append(row)
        if len(public) >= limit:
            break
    return public


def fetch_partners(
    api_key: str,
    *,
    http: HttpClient,
    context: dict[str, Any] | None = None,
    limit: int = DEFAULT_LIMIT,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """只发 A006。不扣浪花。调用方必须已经得到用户同意，且不得顺带打付费查询。"""
    response = http(
        "POST",
        A006_PATH,
        api_key,
        json_body=request_body(context, limit),
        timeout=timeout,
    )
    if response.get("code") != 1:
        return {
            "status": "failed",
            "error": str(
                response.get("msg")
                or response.get("message")
                or f"接口返回 code={response.get('code')}"
            ),
            "partners": [],
        }
    return {
        "status": "ok",
        "partners": summarize_list(response, limit),
    }
