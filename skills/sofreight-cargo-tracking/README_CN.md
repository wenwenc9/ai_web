# 搜航货踪

按提单号或订舱号查询 / 订阅搜航货物跟踪。

## 安装

```bash
cd skills/sofreight-cargo-tracking
pip install -r requirements.txt
```

## 配置 API Key

目标环境变量：**`SOF_API_KEY`**。**禁止**写入 skill 目录。

- 平台 / 执行器：直接注入 `SOF_API_KEY`
- 用户在对话中提供 Key：执行 `--save`（写入当前进程 env，并持久化到用户目录）

```bash
python scripts/tracking.py --status
python scripts/tracking.py --save "<KEY>"
python scripts/tracking.py --clear
```

注册后打开 https://www.sofreight.com/personal_center/api_key 自行创建 Key。本 skill **禁止**调用 `MemberApiKey/create`。

## 用法

```bash
python scripts/tracking.py --numbers "BL1,BL2" --confirmed                 # 确认后查询
python scripts/tracking.py --numbers "BL1" --carrier COSU --confirmed     # 多船司时指定
python scripts/tracking.py --numbers "BL1,BL2" --subscribe --confirmed    # 订阅
python scripts/tracking.py --list                            # 订阅列表
python scripts/tracking.py --list --keywords "OOCL" --carrier CMA
python scripts/tracking.py --export-only                      # 从缓存导出 Excel
```

流程：校验密钥 → 识别单号 → 匹配船司 → 预检额度 → 确认 → 查询/订阅货踪 → 返回摘要。查询与订阅须 `--confirmed`。
