from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_ROOT = "https://apiv6.sofreight.com/api"


def api_headers(
    api_key: str,
    *,
    content_type: str = "application/json",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Source-Type": "AGENT",
        "Lang": "zh-cn",
        "Content-Type": content_type,
    }
    if extra:
        headers.update(extra)
    return headers


def _encode_form(form_body: dict[str, Any]) -> bytes:
    pairs: list[tuple[str, str]] = []
    for key, value in form_body.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                pairs.append((key, "" if item is None else str(item)))
        else:
            pairs.append((key, str(value)))
    return urllib.parse.urlencode(pairs).encode("utf-8")


def request_json(
    method: str,
    path: str,
    api_key: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    opener=None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    if json_body is not None and form_body is not None:
        raise ValueError("json_body and form_body cannot both be set")
    url = API_ROOT.rstrip("/") + "/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = None
    content_type = "application/json"
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    elif form_body is not None:
        data = _encode_form(form_body)
        content_type = "application/x-www-form-urlencoded;charset=UTF-8"
    req = urllib.request.Request(
        url,
        data=data,
        headers=api_headers(api_key, content_type=content_type, extra=extra_headers),
        method=method.upper(),
    )
    opener = opener or urllib.request.urlopen
    try:
        with opener(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise PermissionError(raw) from e
        raise
    return json.loads(raw) if raw else {}
