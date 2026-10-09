# 货踪对话交付

遵守仓库级 [docs/sof-specs/delivery.md](../../../docs/sof-specs/delivery.md)。  
本包打开「留源 + 清洗 + Excel」。产品题见 [product.md](../../../docs/sof-specs/product.md)。

依据接口 `POST /ScheduleSubscribeV2/agentSubscribe`（货踪查询/订阅）与 `POST /ScheduleSubscribeV2/subscribeList`（订阅列表）的返回组织对用户说明。

## 本包要解决什么

货代用提单号或订舱号问货在哪、订没订、动态到哪一步。成功：首轮给摘要列；多船司先让用户点名，禁止猜码。用户明确说订阅再写入。v1 不做推送、不做箱号查询。**船期、塞港、运价、询盘不在本包查**，只给相关技能链接。

## 接口编排

A002 按单号匹配船司 → 多条则停（`needs_carrier`）→ A001 预检 `type=3` → 用户确认 → A003（查询 `sub=false` / 订阅 `sub=true`）。没有书面「只查不扣」，G3、G4 不能跳（D9）。未确认不准打 A003。订阅列表走 A010，不预检、不扣查询次数。一批里一票失败其余继续。

## 交互路径

- 「帮我跟踪这些单号」：可能先选船司，再预检，用户确认后才查。
- 「订阅 / 盯着」：须明确说订阅；确认扣费后再 `--subscribe --confirmed`。刚查过不等于同意订阅。
- 「订了哪些」：`--list`，不扣查询额度。
- 「刚才那票怎么解读 / 只要箱号」：读缓存；要最新动态先问是否重查。
- 确认：「查一下」在额度够时仍须 `--confirmed` 才打 A003，不等于订阅，也不等于同意看合作商家。导出须明确同意。报完可加一句能力露出，不要追问。用户已明确要找人则直接 `--partners-confirmed`。

## 推荐拍档

| 问 | 本包 | 说明 |
|---|---|---|
| 主查询成功后荐合作商家（A006 免费，3 家；禁止每次查询后追问） | 是 | 海运默认开。对外说「合作商家」（货代、拖车、清关、电商），不要说「拍档」。报完可加一句能力露出。仅用户露出需求或说要才 `--partners-confirmed`；意图明确不必再问。用户点名地点/公司才 `--keywords`。给人介绍 + 官网 `detailId` 链接 |

## 相关技能

本包不查船期、塞港、运价、询盘。只给安装位置（上架后换成 SkillHub 地址）：

- 搜航塞港：本仓库 `skills/sofreight-port-congestion/`
- 搜航船期：本仓库 `skills/sofreight-sailing-schedule/`
- 搜航运价：本仓库 `skills/sofreight-sea-freight-price/`

## 交付三问

| 问 | 本包 | 说明 |
|---|---|---|
| 留源 | 是 | 成功查询把 A003 的 `data` 写入 `~/.sofreight/exports/cargo-tracking-last.json` 的 `source`，并记 `queried_at`。用户二次问、要 AI 加工已查数据时只读缓存，禁止再打 A003。货踪会变：必须交代查询时刻；用户要最新、或已过查询当日，先问是否重新查（会再过 G3/G4）。禁止把缓存说成当前动态 |
| 清洗 | 是 | 首轮 IM / stdout 只给下面摘要列。不要把 `ctnr_data`、原始大 JSON 贴进对话 |
| Excel | 是 | 用户同意后从缓存 **源** 投影明细列。`--export-only` 不二次扣费 |

## 聊天摘要列（单票查询/订阅）

有值才写：单号、类型（提单 `blNo` / 订舱 `bkNo`）、船司中文名（`carrier_cname`）、当前状态中文（优先 `must_status_cname` / `subscribe_status_cname`，否则用脚本 `status_label`）、起运港（`pol_cname`/`pol`）、目的港（`pod_cname`/`pod`）、船名/航次（`vessel`/`voyage`）、ETD/ETA（或 ATD/ATA）、箱数、本票结果；失败时加失败原因。

可选补充（有则一句带过，无则跳过）：

- `is_new === true`：说明是新订阅或取消后重新订阅，数据可能尚未齐全
- `change_eta`：ETA 变更天数
- `remaining_tt`：剩余航程天数
- `currentStatus`：船舶动态（见下表）；无则不提
- `congestionInfo.pol/pod`：塞港简述可用 `portCname` + `portIndicatorAnalysis`（或 `reasonAnalysis`），勿罗列全部指标

## 订阅列表摘要列（`--list`）

有值才写：单号、类型（`subscribe_type`：1 提单 / 2·3 订舱）、船司、状态中文（`subscribe_status_cname`）、推送状态（`push_status`）、起运港、目的港、ETD/ETA（有 ATD/ATA 时优先）、船名、航次、订阅时间；有 `notic_msg` 再加提示。

另用一句话带过：`onGoing_count`（进行中）、`finish_count`（已完成）、`history`（是否有历史）。空列表正常说明「暂无订阅」。

单票查询场景（`code == 1` 仍可能是未订阅、订阅中或暂无数据）：

| 场景 | 判别 | 对本票怎么说 | 是否可导出明细 |
|---|---|---|---|
| 未订阅 | `data.sub === false` 且无 `detail` | 未订阅。询问是否订阅；**用户明确同意后再** `--subscribe --confirmed` | 否 |
| 订阅中 | `detail.push_status === 0` | 成功，状态「订阅中」（等待采集）。可稍后再查，勿当失败重试 | 否 |
| 暂无数据 / 无数据 | `push_status === 2`，或 `subscribe_status`/`must_status` 为 `NODATA` | 成功，状态「暂无数据」。**不是报错**，不要换单号、不要立刻重试 | 否 |
| 有动态（正常） | `push_status === 1`（示例「已订阅返回」） | 成功，有数据：填摘要列；状态用 `must_status_cname`（如「离港」） | 是 |
| 结束 | `push_status === 4` | 成功，状态「已结束」；有摘要字段仍填 | 是（有事件才写） |
| 取消 / 暂时取消 | `push_status === 3` 或 `5`；或 `subscribe_status`/`must_status` 为 `CANCELLED` | 成功返回业务态「已取消/暂时取消」（或订舱取消）；说明清楚，勿当接口故障重试 | 视是否有历史事件 |
| 更新中 / 未开始 | `subscribe_status`/`must_status` 为 `UPDATING` / `NOTYET` | 成功，状态「更新中」或「未开始」；可稍后复查 | 否或仅有限字段 |

`order_push_status` 辅助理解：`1` 正常收数、`2` 无数据、`4` 已完成；与 `push_status` 冲突时以 `push_status` + 中文状态名为准。

## 业务失败场景（`code != 1`）

| 场景 | `code` | 对本票怎么说 | 是否重试 |
|---|---|---|---|
| 浪花不够 | `500002` | 浪花不足（可带剩余次数/浪花若有）；引导充值 | 否 |
| 浪花被禁用 | `500004` | 浪花已禁用，联系搜航客服 | 否 |
| VIP / 会员校验失败 | `10002` | 需要开通或续费搜航会员 | 否 |
| 船司匹配错误 | `0` 且 msg 含船司匹配 | 船司不正确，请核对后换 `--carrier` 再查 | 改参后再查，勿原参狂打 |
| 系统异常 | `0` 或其他未映射 | 用脱敏 `msg` 说明（如「货物跟踪订阅出错，请联系客服」） | 网络/5xx 最多再试一次；业务文案类不自动重试 |

以上失败**不是 Key 没配上**（缺 Key / 未授权见 [auth.md](auth.md)）。

## 船舶当前位置（`currentStatus`，可选）

有对象时可用一句话：动态类型 + 航段起讫港。

| `dynamicType` | 含义 |
|---|---|
| `0` | 航行 |
| `1` | 锚泊 |
| `5` | 靠泊 |
| `6` | 搁浅 |

`dynamicSubType`（需要时）：`00` 航行途中、`01` 航行到港、`10` 锚泊途中、`11` 锚泊到港、`50` 靠泊作业、`51` 靠泊修理、`60` 搁浅。可附带下一港（`legEndPortNameCn`）、航速（`averageSpeed`）。`currentStatus === null` 时不提。

## 塞港信息（`congestionInfo`，可选）

`pol` / `pod` 非空时，各用港口中文名 + 指标/原因分析各一句即可。拥堵级别（指标 `grade`）：1 畅通、2 轻度、3 中度、4 重度。指标数值含义（`value`）：0 持平、>0 上升、<0 下降；聊天里一般不必逐项念。

## Excel（仅用户同意后）

明细列：单号、港口、船名、航次、箱号、箱型、封条、事件时间、事件中文。有值才写。来源是箱事件（`container_event_list`），**不要**把原始 `ctnr_data`、塞港全量指标、船舶 MMSI 等塞进表。

时间优先：实际时间 `status_time`；没有再用预计 `status_etime`，并标明是预计。

## stdout

成功或部分成功：`source_cached=true`，`queried_at`，`export_available=true`，`export_hint` 提醒用户。stdout 不含原始 `source`。未同意时无 `export_path`。**不要**在成功后改成 `needs_partners`。可加一句合作商家能力露出，不要追问。
