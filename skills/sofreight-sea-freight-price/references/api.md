# 运价接口速查

正式服前缀：`https://apiv6.sofreight.com/api`  
头：`Authorization: Bearer <api_key>`，`Source-Type: AGENT`，`Lang: zh-cn`。

| 编号 | 方法 | 路径 | 用途 |
|---|---|---|---|
| A004 | GET | `/DPort/index` | 港口名 → UN/LOCODE（`search_port.py`） |
| A008 | POST | `/SeaFclFreight/index` | 海运整箱挂牌运价（`price.py`） |
| A009 | POST | `/AgentInquiryOrder/save` | 海运实盘询盘（`inquiry.py`） |

`code != 1` 一律视为该次失败。鉴权见 [auth.md](auth.md)。过关见 [gates.md](gates.md)。

## A004 港口码

| CLI | 说明 |
|---|---|
| `--keywords` / `-k` | 中/英文港名 |
| `--type` / `-t` | `POL` 起运 / `POD` 目的 |
| `--port-code` | 按码反查 |
| `--code-only` | 只吐第一条码；**多候选时禁止用** |

成功：`status` + `action=port`，候选在 `chat`（UN/LOCODE、中英文名）。  
多条：`status=needs_port`，等用户选后再查价。

```bash
python scripts/search_port.py --keywords 盐田 --type POL
```

## A008 运价

必填：`pol_code`、`pod_code`（大写 UN/LOCODE，来自 A004 或用户明示）。空值字段不传。

| 字段 | 说明 |
|---|---|
| `carrier_code` | 船司，逗号分隔 |
| `cntr_type` | `[{"type":"20GP","number":2},…]`；勿默认单一柜型 |
| `etd_date_1` / `etd_date_2` | ETD 区间 |
| `order_field` | `20gp` / `40gp` / `40hc` / `45hc` / `20nor` / `40nor` |
| `tt_1` / `tt_2` | 航程范围 |
| `valid_date_1` / `valid_date_2` | 有效期区间 |
| `via_type` | `0` 不限 / `1` 直航 / `2` 中转（CLI 可用「直航」等） |
| `rows` | 每页条数，默认 `20` |
| `confirm` | 接口约定字段，默认 `1` |

脚本 stdout 用统一信封（见 [brief.md](brief.md)）：`status` / `action` / `summary` / `chat` / `hints`。全量行只进缓存。

```bash
python scripts/price.py --pol-code CNYTN --pod-code USLAX
```

## A009 询盘

写入AgentDeal。无 `--confirmed` 只预览，不请求接口。请求体字段只维护 [inquiry_schema.py](../inquiry_schema.py)（`JSON_SCHEMA`）。箱型勿默认。有价询盘用 `--from-cache --row N`。无价询盘带上查价条件与查港港名。确认：`--from-cache --confirmed`。

| CLI | 说明 |
|---|---|
| `--from-cache` | 用最近一次 A008 的港口与筛选项（及预览快照） |
| `--row` | 缓存中第 N 条运价（从 1 起） |
| `--gp20` / `--gp40` / `--hc40` / `--hc45` / `--nor40` | 对应柜型箱量；查价已带 `cntr_type` 时可省略 |
| `--special-container` | 特种柜 |
| `--confirmed` | 用户已确认本次写入 |

```bash
python scripts/inquiry.py --from-cache --gp20 1
python scripts/inquiry.py --from-cache --confirmed
python scripts/inquiry.py --from-cache --row 1 --gp20 1 --confirmed
```

## 错误与重试

| 情况 | 怎么做 |
|---|---|
| 缺 Key（退出码 2） | 读 [auth.md](auth.md)，不打 A004/A008/A009 |
| Key 被拒（退出码 4） | 联系客服，不盲重试 |
| 港口 0 条 / 多条 | 换词或让用户选；禁止猜码 |
| `empty` | 业务成功无数据，不换参狂打 |
| 网络超时、5xx | 最多再试一次 |
| 需要会员 / 浪花不足 | 人话说明 |
