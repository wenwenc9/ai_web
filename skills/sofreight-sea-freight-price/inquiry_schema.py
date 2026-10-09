"""A009 POST /AgentInquiryOrder/save 请求体。改入参只改这里。"""

from __future__ import annotations

from typing import Any

ENDPOINT = "/AgentInquiryOrder/save"

# CLI dest → 箱型键（box_type_json）
BOXES = (
    ("gp20", "20GP"),
    ("gp40", "40GP"),
    ("hc40", "40HC"),
    ("hc45", "45HC"),
    ("nor40", "40NOR"),
    ("special_container", "特种柜"),
)

# 查价 query 里与询盘 body 同名的字段
QUERY_FIELDS = (
    "pol_code",
    "pod_code",
    "carrier_code",
    "etd_date_1",
    "etd_date_2",
    "service_code",
    "tt_1",
    "tt_2",
    "via_type",
    "valid_date_1",
    "valid_date_2",
)

# 有价行覆盖（product_id 另从 spot_product_id 兜底）
ROW_FIELDS = (
    "pol_code",
    "pod_code",
    "pol_cname",
    "pol_name",
    "pod_cname",
    "pod_name",
    "carrier_code",
)

# CLI 文本覆盖
TEXT_CLI = (
    "pol_name",
    "pod_name",
    "pol_cname",
    "pod_cname",
    "pol_code",
    "pod_code",
    "product_id",
    "remark",
    "carrier_code",
)

VIA_LABEL = {0: "不限", 1: "直航", 2: "中转"}

# 对人预览：body 键或合成键 → 中文列
PREVIEW = (
    ("origin", "起运港"),
    ("destination", "目的港"),
    ("carrier_code", "承运人代码"),
    ("product_id", "运价编号"),
    ("boxes", "箱型箱量"),
    ("etd", "ETD"),
    ("via", "直航/中转"),
    ("service_code", "航线代码"),
    ("tt", "航程(天)"),
    ("remark", "备注"),
)

JSON_SCHEMA: dict[str, Any] = {
    "$id": "sofreight-sea-freight-price/a009-save",
    "title": "A009 AgentInquiryOrder/save",
    "type": "object",
    "additionalProperties": False,
    "required": ["demand", "box_type_json"],
    "properties": {
        "demand": {"type": "array", "description": "附加需求，当前固定 []"},
        "box_type_json": {
            "type": "object",
            "description": "柜型箱量；未选的柜型为 0",
            "additionalProperties": False,
            "properties": {
                label: {"type": "integer", "minimum": 0} for _, label in BOXES
            },
        },
        "pol_code": {"type": "string", "description": "起运港 UN/LOCODE"},
        "pod_code": {"type": "string", "description": "目的港 UN/LOCODE"},
        "pol_cname": {"type": "string", "description": "起运港中文名"},
        "pod_cname": {"type": "string", "description": "目的港中文名"},
        "pol_name": {"type": "string", "description": "起运港英文名"},
        "pod_name": {"type": "string", "description": "目的港英文名"},
        "carrier_code": {"type": "string", "description": "承运人代码"},
        "product_id": {"type": "string", "description": "有价询盘运价编号"},
        "remark": {"type": "string", "description": "用户口头要求等备注"},
        "etd_date_1": {"type": "string", "description": "ETD 起"},
        "etd_date_2": {"type": "string", "description": "ETD 止"},
        "service_code": {"type": "string", "description": "航线代码"},
        "tt_1": {"type": "integer", "description": "航程下限（天）"},
        "tt_2": {"type": "integer", "description": "航程上限（天）"},
        "via_type": {"type": "integer", "enum": [0, 1, 2], "description": "0 不限 / 1 直航 / 2 中转"},
        "valid_date_1": {"type": "string", "description": "运价有效期起"},
        "valid_date_2": {"type": "string", "description": "运价有效期止"},
    },
}

BODY_KEYS = frozenset(JSON_SCHEMA["properties"])
BOX_LABELS = tuple(label for _, label in BOXES)


def empty_body() -> dict[str, Any]:
    return {
        "demand": [],
        "box_type_json": {label: 0 for label in BOX_LABELS},
    }


def project(payload: dict[str, Any]) -> dict[str, Any]:
    """只保留 schema 字段；可选字段空值丢掉。"""
    out: dict[str, Any] = {}
    for key in JSON_SCHEMA["properties"]:
        if key not in payload:
            continue
        value = payload[key]
        if key in JSON_SCHEMA["required"]:
            out[key] = value
            continue
        if value in (None, "", []):
            continue
        out[key] = value
    return out


def preview_row(payload: dict[str, Any]) -> dict[str, Any]:
    box = payload.get("box_type_json") or {}
    etd_1, etd_2 = payload.get("etd_date_1"), payload.get("etd_date_2")
    tt_1, tt_2 = payload.get("tt_1"), payload.get("tt_2")
    values = {
        "origin": payload.get("pol_cname") or payload.get("pol_name") or payload.get("pol_code"),
        "destination": payload.get("pod_cname") or payload.get("pod_name") or payload.get("pod_code"),
        "carrier_code": payload.get("carrier_code"),
        "product_id": payload.get("product_id"),
        "boxes": {key: qty for key, qty in box.items() if qty},
        "etd": f"{etd_1 or ''}~{etd_2 or ''}".strip("~") if (etd_1 or etd_2) else None,
        "via": VIA_LABEL.get(payload["via_type"]) if payload.get("via_type") is not None else None,
        "service_code": payload.get("service_code"),
        "tt": f"{tt_1 or ''}~{tt_2 or ''}".strip("~") if (tt_1 is not None or tt_2 is not None) else None,
        "remark": payload.get("remark"),
    }
    return {label: values[key] for key, label in PREVIEW if values.get(key)}
