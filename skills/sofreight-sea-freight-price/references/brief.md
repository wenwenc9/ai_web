# 运价对话交付

遵守仓库级 [docs/sof-specs/delivery.md](../../../docs/sof-specs/delivery.md)。  
清洗、留源、Excel 均打开：首轮只给挂牌价摘要；完整费率从缓存导出。挂牌价为参考价，不是订舱确认。产品题见 [product.md](../../../docs/sof-specs/product.md)。

规范倾向「运价查询」与「询盘」分夹；**本夹合入时仍含询盘写入**，询盘必须单独过 G4。订舱不在本包。

## 本包要解决什么

货代问起运港到目的港的海运整箱挂牌价。成功：首轮摘要最多 10 条，港名多码先让用户点名，禁止猜码。用户明确要实盘时，再提交询盘。v1 不做订舱。**货踪、船期、塞港不在本包查**，只给相关技能链接。

## 接口编排

A004 按港名搜 UN/LOCODE → 多条则停（`needs_port`）→ A008 查挂牌价（`confirm=1`）。本包未接 A001（无 type），查价不设 `--confirmed`（保持同事路径）。询盘走 A009，无 `--confirmed` 只预览。未选定港口前不调 A008。

## 交互路径

- 「盐田到洛杉矶运价」：可能先选港，再查价。
- 「刚才那次怎么比」：读缓存；运价会变，要最新或已过查询当日先问是否重查。
- 确认：「查一下运价」不等于同意询盘、不等于同意看合作商家。导出须明确同意。报完可加一句合作商家能力露出，不要追问。用户已明确要找人则直接 `--partners-confirmed`。

## 推荐拍档

| 问 | 本包 | 说明 |
|---|---|---|
| 主查询成功后荐合作商家（A006 免费，3 家；禁止每次查询后追问） | 是 | 海运默认开。对外说「合作商家」（货代、拖车、清关、电商），不要说「拍档」。报完可加一句能力露出。仅用户露出需求或说要才 `--partners-confirmed`；意图明确不必再问。用户点名地点/公司才 `--keywords`。给人介绍 + 官网 `detailId` 链接 |

## 相关技能

本包不查货踪、船期、塞港。只给安装位置（上架后换成 SkillHub 地址）：

- 搜航塞港：本仓库 `skills/sofreight-port-congestion/`
- 搜航船期：本仓库 `skills/sofreight-sailing-schedule/`
- 搜航货踪：本仓库 `skills/sofreight-cargo-tracking/`

## 交付三问

| 问 | 本包 | 说明 |
|---|---|---|
| 留源 | 是 | 成功查询把 A008 运价行写入 `~/.sofreight/exports/sea-freight-price-last.json` 的 `source`，并记 `queried_at`。用户二次问、要比价或加工已查结果时只读缓存，禁止再打 A008。运价会变：必须交代查询时刻；用户要最新或已过查询当日，先问是否重查。禁止把缓存说成当前报价 |
| 清洗 | 是 | 首轮 IM / stdout 只给下面摘要列，最多 10 条（按接口返回顺序）。禁止把完整 `pricing_list` 或原始 JSON 贴进首轮聊天 |
| Excel | 是 | 首轮用 `export_hint` **询问**是否需要「导出 / 出 Excel / 下载明细」。用户同意后再 `--export` 或 `--export-only`。明细从缓存源投影，不得从摘要再编一版，不得为导出再查价 |

## 聊天摘要列

先报查询条件：起运港、目的港（中文名 + UN/LOCODE）、可选承运人、直航/中转、ETD 区间。  
再报命中条数（直航 / 中转各多少）；摘要最多 10 条，并询问其余行是否导出 Excel。

| 列名 | 来源字段 | 口径 |
|---|---|---|
| 起运港 | `pol_cname`（无则 `pol_code`） | 装货港 POL |
| 目的港 | `pod_cname`（无则 `pod_code`） | 卸货港 POD |
| 承运人 | `carrier_cname` | 船公司中文名 |
| 承运人代码 | `carrier_code` | 搜航船司码 |
| 航线代码 | `service_code` | 航线 / 服务代码 |
| 船名 | `vessel` | 干线船名 |
| 航次 | `voyage` | 航次号 |
| 开航日 | `etd_date_show` | 预计离港日 ETD |
| 航程(天) | `tt` | 在途天数 TT |
| 20GP | `price_20gp` | 20 尺普柜挂牌价 |
| 40GP | `price_40gp` | 40 尺普柜挂牌价 |
| 40HC | `price_40hc` | 40 尺高柜挂牌价 |
| 45HC | `price_45hc` | 45 尺高柜挂牌价 |
| 计价币种 | `currency` | 费率币种 |
| 运价生效日 | `begin_date` | 本档费率起始日 |
| 运价截止日 | `end_date` | 本档费率有效期止 |

有值才展示。必须询问：是否导出 Excel 看全量明细；是否提交实盘询盘。查价不等于询盘。未同意不要生成 Excel、不要打询盘接口。

## Excel（用户同意后）

从缓存源落表，不要从聊天摘要再编一版。

Agent 只报 `export_path`，不要把工作表读回对话。

## 询盘（用户确认后）

查价成功或 `empty` 都要带 `inquiry_hint`。用户说「询盘 / 实盘 / 正式询价」后：

1. 汇总将提交的港口（含中英文名）、箱型箱量、承运人、ETD、直航/中转、航线、备注与运价编号（有价询盘用缓存第 N 条的 `spot_product_id`）等详细信息。用户提过的条件都要进预览，不要只报港码。
2. 等用户明确说「确认」。查挂牌价那句话不算确认。
3. 再跑 `inquiry.py --from-cache --confirmed`。无 `--confirmed` 只返回 `needs_confirm`，不打 A009。确认必须提交预览同一份条件，禁止只带港码。

无匹配运价也可做无价询盘（读本次查价 `query` + 查港港名；箱型来自用户或查价 `cntr_type`）。汇总所有提到的相关条件信息。

## stdout

三脚本同一信封：`status`、`action`、`summary.message`。可选键缺省不出现。**不要**在成功后改成 `needs_partners`。

| 字段 | 用途 |
|---|---|
| `action` | `price` / `port` / `inquiry` / `export` / `key` |
| `query` | 本次入参 |
| `counts` | `returned` / `api_total` / 查价再加 `direct`、`transit` |
| `chat` | 给客户看的短表（查价最多 10 条摘要列；查港为候选港） |
| `hints` | `source_cached`、`export_*`、`inquiry_*` |
| `export_path` | 仅同意导出后 |
| `preview` | 仅询盘 `needs_confirm` |
| `setup_reference` | 仅缺 Key |

公开 stdout 不含 `source` / `pricing_list`。

## 状态怎么说

| 情况 | 对用户 |
|---|---|
| `ok` | 摘要为挂牌参考价，非正式订舱确认；询问是否导出 Excel；询问是否实盘询盘。可加一句合作商家能力露出，不要追问 |
| `empty` | 成功，当前港口对与筛选无匹配运价；可建议改港、改承运人或 ETD 窗口。不询问导出；询问是否无价询盘 |
| `needs_confirm` | 询盘预览表已列出；等用户确认后再 `--confirmed` |
| `needs_port` | 列出候选港口 UN/LOCODE 与中英文港名，等用户选定后再查价 |
| 退出码 2 | 去开通 Key，不打业务接口 |
| 退出码 4 | Key 不可用，联系客服 |
