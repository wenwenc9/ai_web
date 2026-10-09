import json
import os
from pathlib import Path

from sofreight_runtime.paths import credentials_path, home_dir


def mask_key(key: str) -> str:
    if not key:
        return ""
    if key.startswith("sk-") and len(key) > 10:
        return f"sk-****{key[-4:]}"
    if len(key) > 8:
        return f"****{key[-4:]}"
    return "****"


KEY_SETUP_URL = "https://www.sofreight.com/personal_center/api_key"
KEY_SETUP_PATH = "个人中心 → APIKEY"
CUSTOMER_SERVICE = "400-048-5656、call@sofreight.com、微信 sofreight56"


def missing_key_hint(save_command: str) -> str:
    return (
        "缺少搜航 API Key。请先在 https://www.sofreight.com/ 注册搜航账户，"
        f"登录后打开 {KEY_SETUP_URL}（{KEY_SETUP_PATH}）自行创建。"
        f"遇到问题再联系搜航客服：{CUSTOMER_SERVICE}。"
        "开通后把 Key 配到执行器环境变量 SOF_API_KEY，或本机保存："
        f"{save_command}。"
        "细则见 references/auth.md。禁止在聊天里回显完整 Key，禁止调用 MemberApiKey/create。"
    )


def save_api_key(key: str) -> Path:
    home_dir().mkdir(parents=True, exist_ok=True)
    path = credentials_path()
    path.write_text(json.dumps({"api_key": key.strip()}, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def load_api_key() -> str | None:
    env = os.environ.get("SOF_API_KEY", "").strip()
    if env:
        return env
    path = credentials_path()
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    key = str(data.get("api_key") or "").strip()
    return key or None
