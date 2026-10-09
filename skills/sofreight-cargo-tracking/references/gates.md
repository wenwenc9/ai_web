# 货踪闸门

本能力过搜航七道闸。A003 会消耗次数或浪花，所以 **查询与订阅都必须过 G3、G4**（D9）。没有书面「只查不扣」。订阅列表（A010）不扣查询额度，跳过 G3/G4。

## 用户：「帮我跟踪这些单号」

| 闸 | 本能力怎么过 |
|---|---|
| G0 | `--status`。缺 Key → 整批停，读 [auth.md](auth.md)，引导注册并自助创建 Key；配 `SOF_API_KEY` 或 `--save` |
| G1 | 本地识别提单 `blNo` / 订舱 `bkNo`。坏单号本票失败，其余继续。v1 不做箱号。每批建议最多 5 票 |
| G2 | A002 按单号匹配船司。0 个：本票失败。1 个：采用。多个：`needs_carrier`，列出 `carrier_code`、`carrier_cname`，用户带 `--carrier` 再跑。禁止猜。**此时不调 A003** |
| G3 | A001 预检（`type=3` 货物跟踪）。次数优先，用尽再看浪花。stdout 写清将执行票数、剩余次数、是否动浪花、无法执行的票。不够仍返回 `needs_confirm`，禁止打 A003 |
| G4 | 用户明确确认后才加 `--confirmed`，此时才调 A003。`needs_confirm` 时禁止重试 A003。「查一下」不等于订阅 |
| G5 | 逐票 A003（默认 `sub=false`）。单票失败继续其余票，整批允许部分成功 |
| G6 | 按 [brief.md](brief.md) 摘要；缓存留源；未同意不写 xlsx |

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1,BL2"
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1,BL2" --confirmed
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1" --carrier COSU --confirmed
```

## 用户明确说「订阅 / 盯着」

订阅是写入动作，须用户明确说订阅才加 `--subscribe`，且仍须 `--confirmed`（A003 扣费）。不得因为刚查过就自动订阅。v1 不做推送；下次用户再问时再查。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1,BL2" --subscribe --confirmed
```

## 用户：「订阅了哪些 / 看看我的货踪订阅」

流程：`G0 → 拉订阅列表 → 返回摘要`。A010 **不预检额度、不扣查询次数**，跳过 G3/G4（查询侧）。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --list
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --keywords "OOCL"
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --date-from 2024-02-01 --date-to 2024-02-28
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --carrier CMA --history --finished
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --page 1 --limit 20
```

可告知进行中/已完成数量（`onGoing_count` / `finish_count`）及是否有历史（`history`）。空列表是业务成功，不是报错。

## 用户对已查货踪再问

留源已开：换视角只读缓存 `source`。先报 `queried_at`。用户要最新或已过当日：先问是否重新查（再过 G3/G4），禁止把缓存说成当前动态，禁止不经询问再打 A003。

## 用户要看合作商家

产品已开（brief 拍档=是）。A006 免费，不要提浪花。**禁止**报完货踪就追问。同一轮最多一次，摘要末尾可加能力露出（见 SKILL 铁律「需要的话跟我说一声」）。用户没接话就停。已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`（只打 A006）。仅「还能帮什么」等含糊意图才问固定句。用户点了地点或公司名才 `--keywords`，禁止用上次货踪去填。对人给介绍和 `https://www.sofreight.com/introduction?detailId={id}`。`--confirmed` 不等于同意。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --partners-confirmed
python skills/sofreight-cargo-tracking/scripts/tracking.py --partners-confirmed --keywords 宁波
```

## 用户要 Excel

- 查询当时就要表：加 `--export`（仍须本次已 `--confirmed` 且查询成功）。
- 看完摘要才要表：`--export-only`（读缓存，禁止再调查询接口，避免二次扣费）。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --export-only
```

## 多船司待选（`needs_carrier`）

返回 `needs_carrier` 时：列出该票可选的 `carrier_code`、`carrier_cname`，请用户选一个。**此时尚未调用查询/订阅接口，不扣费。**  
用户选定后再跑，带上 `--carrier` 与 `--confirmed`；未选定前不要猜船司、不要重试付费接口。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1" --carrier COSU --confirmed
```

## 额度不足（`needs_confirm` 且不够覆盖本批）

预检发现次数/浪花不够覆盖本批可执行票数时：说明将执行票数、剩余次数、浪花情况，引导充值或减少单号。**禁止把额度不足当失败去重试 A003。**

## 批量部分成功

一批里允许有的票成功、有的失败。对失败票说清原因，对成功票仍按 [brief.md](brief.md) 给摘要。不要因为单票失败就整批作废或整批重跑。

## 查完结果是「暂无数据」

接口成功且状态为「暂无数据」：按成功交付，告诉用户暂无动态。**不是报错**，不要换单号、不要立刻重试同一查询。

## 查完显示未订阅，用户再说要订阅

查询结果为未订阅时：可询问是否订阅；**只有用户明确同意后再**加 `--subscribe --confirmed` 跑一遍。不得因刚查过就自动订阅。

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1" --subscribe --confirmed
```

## 单号未标明提单还是订舱

本地启发式能判断则继续；无法判断时本票失败（提示标明类型），其余票继续。可请用户说明「这是提单号」或「这是订舱号」后再查该票。v1 脚本无单独类型参数时，以用户口头确认后的理解重新组织 `--numbers` 查询；仍无法识别则本票失败，勿瞎猜。

## 一批超过建议上限（>5 票）

建议每批最多 5 票。超过时先告知建议分批，征得同意后再按批执行（每批仍走完整流程）。不要默默一次扔超大批次，也不要擅自丢弃多出的单号。

## 需要开通会员 / 浪花不足 / 浪花禁用

业务错误（如 `10002` 需开通会员、`500002` 浪花不足、`500004` 浪花禁用）：用自然语言说明原因，引导联系搜航客服或充值。**不是 Key 没配上**；认证类错误不自动重试，额度/会员类错误禁止盲打付费接口。
