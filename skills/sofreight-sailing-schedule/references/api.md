# 船期接口速查

正式服前缀：`https://apiv6.sofreight.com/api`  
头：`Authorization: Bearer <api_key>`，`Source-Type: AGENT`，`Lang: zh-cn`。  
船期查询另用 form：`Content-Type: application/x-www-form-urlencoded`。

| 编号 | 方法 | 路径 | 用途 |
|---|---|---|---|
| A004 | GET | `/DPort/index` | 按关键词/五字码查港口（G2） |
| A007 | POST | `/ship_schedule/get_schedule` | 按港口组合查询船期（直航 + 中转） |

`code != 1` 一律视为本次失败。

| 错误码 | 含义 |
|---|---|
| `10002` | 需要开通搜航会员 |
| `500002` | 浪花不足（本包查询路径不预检；若接口仍返回则按失败说明） |
| `500004` | 浪花被禁用，联系客服 |

## A004（港口五字码）

查询参数：`keywords`（中文/英文港名）或 `port_code`（校验显式五字码），以及 `page`、`rows`、`with_group=0`。  
返回列表里取 `port_code` / `port_cname` / `port_name`。港名多条时脚本停在 `needs_port`；显式五字码查不到则失败，不进 A007。**禁止 Agent 自行猜码**。

## A007

必填 form：`pol_code`、`dest_code`。  
常用可选：`carrier`、`weekly`、`vessel`、`voyage`、`query_type`（`DIRECT`/`TRANS`/`ALL`）、`etd_1`/`etd_2`、`sort`（`ETD_ASC`/`ETD_DESC`/`TT_ASC`/`TT_DESC`）、`is_skip_blank_sailing`（`1` 过滤空班）、`src_type=AI`。  
本包固定传 `confirm=0`（当前查询不消费代币/次数/浪花）。不做 A001 额度预检。

成功时 `data.directList` 为共舱组对象，`data.transferList` 为中转数组。二者皆空算业务成功（暂无船期）。

港口未解析完（`needs_port`）前禁止调用 A007。缺 Key 禁止调用。

## 错误与重试

| 情况 | 怎么做 |
|---|---|
| 缺 Key（退出码 2） | 读 [auth.md](auth.md)，不打 A004/A007 |
| Key 被拒（退出码 4） | 联系客服，不盲重试 |
| 港口码不对 | 改五字码，不拿原参数狂打 |
| 空结果 | 业务成功，不换参重试 |
| 网络超时、5xx | 最多再试一次；认证错误不自动重试 |

报错可以带 A00x、HTTP 状态、脱敏 `msg`。禁止带完整 Key、Authorization。

## 用户追问 → A007 参数（Agent 交互速查）

用户在对话里追加条件时，先按此表翻译成 CLI 参数，**命中港口多候选时先用 `view`/展示约定引导，不要盲查**：

| 用户说 | 动作 |
|---|---|
| "只看 MSC / 马士基 / ONE" | 把船司口语翻译为代码 → 重查带 `--carrier` |
| "九月中旬的 / 10月1日到10日开船" | 提取起止日 → `--etd-start` / `--etd-end` |
| "只要直达 / 只看中转" | `--query-type DIRECT` / `--query-type TRANS` |
| "EVER MILD 这班 / 查某条船 / 按航次 1471E 查" | `--vessel EVER MILD` / `--voyage 1471E`。**接口为完整匹配，不做模糊查询**：船名要给全名（口语里只有简称时先追问或从 `view` 概览里帮用户认全名），航次同理 |
| "不要空班 / 跳过空班" | `--skip-blank` |
| "最快的 / 航程最短" | `--sort TT_ASC` |
| "最近的班次" | 直接看 `view` 近 3 班即可，无需重查 |
| "换个船司 / 换时间再查" | 同一港口组合重跑；港口未变可复用五字码 |

若只想从**已查结果**里过滤（不重新打 A007），直接用返回 JSON 的 `direct`/`transfer`
清洗行按字段筛选即可（船司字段等），结果建议沿用「航线概览 + 精简班次」的同构格式。

### 常用船司中英文对照（口语 → carrier 代码）

| 口语/中文 | 代码（carrier） |
|---|---|
| 马士基 | MAERSK / MSK |
| 地中海航运 | MSC |
| 达飞 | CMA / CMA CGM |
| 中远海运 | COSCO |
| 东方海外 | OOCL |
| 长荣海运 | EMC |
| 阳明海运 | YML |
| 万海航运 | WHL |
| 海洋网联 | ONE |
| 赫伯罗特 | HPL |
| 太平船务 | PIL |
| 海丰国际 | SITC |
| 以星航运 | ZIM |
| 金星轮船（Gold Star） | GSL |
| 兴亚海运（IAL） | IAL |
| 德翔海运（TS Lines） | TSLINES |
| 高丽海运 | KMTC |
| 南星海运 | NAMSUNG |
| 正利航业 / CNC | CNC |
| 现代商船 | HMM |

注：`carrier` 实际取值以搜航数据为准，口语不确定时先查询结果里的「船司」列核对，再决定是否重查。
