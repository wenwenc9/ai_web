# Changelog

## 0.5.5

- 货架能搜到「海运 / 物流」；触发专词与货踪、船期、塞港互斥，避免四包同时装时抢对话。

## 0.5.4

- 品牌英文改为 sofreight：目录与 slug 从 `sofeight-sea-freight-price` 更名为 `sofreight-sea-freight-price`。

## 0.5.3

- A009 请求体独立为 `inquiry_schema.py`，脚本按 schema 组包。

## 0.5.2

- 询盘提交带上所有用户条件：查价筛选项、查港港名、预览快照。确认可用 `--from-cache --confirmed` 提交同一份预览。

## 0.5.1

- 对齐现行接口编号：港口搜索 A004，挂牌运价 A008，询盘 A009。
- G0 改为自助创建 Key；海运拍档 `--partners-confirmed`。
- 留源补 `queried_at`。查价/询盘主路径保持同事实现。

## 0.5.0

- 查价 / 查港 / 询盘 / 导出 / Key 共用 stdout 信封：`status`、`action`、`summary`、`chat`、`counts`、`hints`。

## 0.4.1

- Excel 写入接口全量行：去掉 `EXCLUDE_FIELDS` 后其余字段原样进表，不再用聊天摘要列裁表。

## 0.4.0

- 查价后询问是否实盘询盘；`scripts/inquiry.py` 提交 I001，须 `--confirmed`。
- 无匹配运价也可无价询盘（读本次港口缓存）。有价询盘用 `--from-cache --row`。
- 去掉夹内 Node 子 skill，鉴权与货踪/运价同一套 Key。

## 0.3.0

- 交付三问改为清洗、留源、Excel 皆开：首轮 IM 用中文摘要列，源写入缓存，用户同意后导出挂牌运价明细。
- `--export` / `--export-only`；`--export-only` 不二次请求 P002。
- 列名与 `references/brief.md` 对齐（承运人、开航日、柜型费率、运价有效期等）。

## 0.2.0

- 目录更名为 `sofreight-sea-freight-price`（工厂命名约定）。
- 补齐五件套：`gates.md` / `brief.md` / `auth.md` / `api.md` + 薄 `SKILL.md`。
- 交付三问：清洗开、留源关、Excel 关；港口多候选 `needs_port`；`empty` 退出码 0。
- `sofreight_runtime` 经 `tools/sync_runtime.py` 与仓库原件对齐。

## 0.1.1

- 并入港口 UN/LOCODE 查询：`scripts/search_port.py`。
- 强制流程：港名 → 查码 → 再查价。

## 0.1.0

- 首个可上架运价包：Python CLI，本包自带鉴权。
