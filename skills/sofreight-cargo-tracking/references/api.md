# 货踪接口说明

正式服前缀：`https://apiv6.sofreight.com/api`  
头：`Authorization: Bearer <api_key>`，`Source-Type: AGENT`，`Lang: zh-cn`。

| 接口名称 | 附录编号 | 方法 | 路径 | 用途 |
|---|---|---|---|---|
| 查询剩余额度 | A001 | GET | `/DMemberVipRefuelingNumber/searchLeftNumber` | 查询货踪剩余次数（`type=3`） |
| 船司匹配 | A002 | GET | `/ScheduleSubscribeV2/getCarrierByNo` | 按提单号或订舱号匹配船司 |
| 货踪查询/订阅 | A003 | POST | `/ScheduleSubscribeV2/agentSubscribe` | 查询或订阅货踪 |
| 订阅列表 | A010 | POST | `/ScheduleSubscribeV2/subscribeList` | 查询已订阅货踪列表（query 传参，**不扣查询额度**） |

`code != 1` 一律视为该票失败。

| 错误码 | 含义 |
|---|---|
| `10002` | 需要开通搜航会员 |
| `500002` | 浪花不足 |
| `500004` | 浪花被禁用，联系客服 |

货踪查询/订阅接口 `code=1` 时的业务特征（该票仍算成功，除非另有失败码）：

| 特征 | 含义 |
|---|---|
| `data.sub === false` 且无 `detail` | 未订阅 |
| `push_status=0` | 订阅中（等待采集） |
| `push_status=1` | 正常，有动态 |
| `push_status=2` | 暂无数据 |
| `push_status=3` | 已取消 |
| `push_status=4` | 已结束 |
| `push_status=5` | 暂时取消 |

另见业务失败码：`10002` 会员、`500002` 浪花不足、`500004` 浪花禁用；`code=0` 可能是系统异常或船司匹配错误（看 `msg`）。详细对话说法见 [brief.md](brief.md)。

请求体 `sub=false` 表示查询，`sub=true` 表示订阅。调用前须完成「船司匹配」「预检额度」；**无 `--confirmed` 不准打 A003**（D9）。

## 订阅列表（A010）

`POST`，筛选条件放在 **query**（可无 body）。本 skill 暴露的常用参数：

| CLI | query | 说明 |
|---|---|---|
| `--keywords` | `keywords` | blNo / soNo / pol / pod / carrier（仅 `--list`；看合作商家时 `--keywords` 另给 A006） |
| `--date-from` / `--date-to` | `subscribe_date[0]` / `[1]` | 订阅日期 |
| `--carrier` | `carrier` | 船司过滤（数组） |
| `--history` | `is_history=1` | 历史数据 |
| `--finished` | `is_finish=1` | 已完成 |
| `--page` / `--limit` | `page` / `limit` | 分页，默认 1 / 20 |

成功：`code==1`，列表在 `data.data`；另有 `history`、`finish_count`、`onGoing_count` 及港口/船司过滤候选。失败按业务 `code`/`msg` 处理，**不要**当缺 Key。

## 错误与重试

| 情况 | 怎么做 |
|---|---|
| 缺 Key（退出码 2） | 读 [auth.md](auth.md)，不打业务接口 |
| Key 被拒（退出码 4） | 联系客服，不盲重试 |
| 参数/单号/船司不对 | 改这一票，不拿原参数狂打 |
| 空结果 / 暂无数据 | 业务成功，不换参重试 |
| 网络超时、5xx | 最多再试一次；认证和额度错误不自动重试 |
| `needs_confirm` | 禁止当失败重试查询接口 |
