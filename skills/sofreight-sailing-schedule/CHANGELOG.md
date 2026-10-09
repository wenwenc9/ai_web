# Changelog

## 0.6.6

- 货架能搜到「海运 / 物流」；触发专词去掉「航程」（易与货踪抢），与货踪、运价、塞港互斥。

## 0.6.5

- 品牌英文改为 sofreight：目录与 slug 从 `sofeight-sailing-schedule` 更名为 `sofreight-sailing-schedule`。

## 0.6.4

- 导出 Excel 时把 list/dict 单元格转成文本（中转港 `["PUSAN"]` 写成 `PUSAN`），避免 openpyxl 报错。

## 0.6.3

- 对齐现行接口编号：港口搜索 A004，船期查询 A007（不再占用塞港的 A005）。
- G0 改为自助创建 Key（个人中心 APIKEY）；客服只做兜底。
- 海运拍档：`--partners-confirmed` 打 A006；报完不追问。
- 留源补 `queried_at`。工厂 runtime 支持船期 form POST。

## 0.6.2

- `view` 直航/中转表去掉「固定班期」列（清洗列与 Excel 仍保留「周几」）。

## 0.6.1

- `view` 班次去重改为船名+航次+开船日（同船同日不同航次不再合并）；注释与 `display.md` 对齐。
- 随查询 `--export` 缺 `openpyxl` 时保留 `status=ok` 与 `view`，另带 `export_error`（不再整次 `failed`）。
- `brief` / `gates` / `display` / `SKILL` 写清：`view` 用全量聚合；stdout 清洗列可截断；二次问全量读缓存。

## 0.6.0

- 成功查询带统一对话视图 `view`（直航共舱概览 + 中转精简表）；见 `references/display.md`。
- `needs_port` 增加 `candidates_view` / `recommended` / `hint`，便于 IM 展示候选港。
- 清洗字段「服务代码」改为「航线代码」。
- Excel：表头样式、冻结首行、列宽、空班行高亮；`openpyxl` 改为懒加载（查询不依赖该包）。

## 0.5.0

- 船期查询不再做 A001 额度预检，也不再要求 `--confirmed`；缺 Key 仍拦截。
- A004 传 `confirm=0`；额度不足也可直接查询。

## 0.4.0

- 首轮 IM 每类最多 30 条；全量进缓存/Excel，超限带 `chat_hint`。
- 额度不足改为 `insufficient_quota`，直接告知，不再混进 `needs_confirm`。
- 显式五字码经 A005（`port_code=`）校验，无效不进额度预检。

## 0.3.0

- G2：接入 A005 港口五字码搜索。港名多候选时 `needs_port`，列出选项等用户确认后再查船期；禁止猜码。

## 0.2.0

- 打开 Excel：用户同意后 `--export` / `--export-only`；从缓存源投影直航/中转两表，不为导出再打 A004。

## 0.1.0

- 首版：按起运港/目的港五字码查询船期（直航 + 中转）。
- 额度预检 A001（`type=4`），用户确认后才调 A004；接口返回的方案全部清洗汇总，不再只取代表条。
- 交付：留源 + 清洗。
