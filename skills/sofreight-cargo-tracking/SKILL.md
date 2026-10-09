---
name: sofreight-cargo-tracking
description: 按提单号或订舱号查询、订阅货物跟踪并查看订阅列表。适用于海运、物流、国际物流、货代运输。用户提到货物跟踪、货踪、提单、订舱号、箱动态时使用。
slug: sofreight-cargo-tracking
displayName: 搜航货踪
version: 0.3.3
summary: 海运货物跟踪：按提单号或订舱号查询与订阅。
license: MIT
---

# 搜航货踪

处理提单号或订舱号的货物跟踪，也可查看已订阅列表。建议每批最多 5 票；一票一票过关，单票失败不能阻断其余票。

过关步骤：[references/gates.md](references/gates.md)。  
开通与 Key：[references/auth.md](references/auth.md)。  
交付（三问皆开）与聊天列：[references/brief.md](references/brief.md)。  
接口人话：[references/api.md](references/api.md)。

本包自带鉴权。上架到 Agent 平台时只拖这一夹，不要再装独立的 Key skill。

## 铁律

1. **G0** 缺 Key 先停。跑 `--status`；读 [references/auth.md](references/auth.md)。引导先在 https://www.sofreight.com/ 注册搜航账户，再打开 https://www.sofreight.com/personal_center/api_key（个人中心 → APIKEY）自行创建。遇到问题再联系搜航客服（400-048-5656、call@sofreight.com、微信 sofreight56）。优先 `SOF_API_KEY`。禁止聊天回显完整 Key，禁止调用 `MemberApiKey/create`。
2. **G2** 船司必须来自 A002。0 个：本票失败。多个：`needs_carrier`，列出 `carrier_code`、`carrier_cname`，等 `--carrier`。禁止猜船司。**此时仍不调 A003**。
3. **G3→G4** 先 A001（`type=3`）预检额度。没有 `--confirmed` 绝不调用 A003（查询 `sub=false` 与订阅 `sub=true` 都要确认）。用户只说「查一下」不等于订阅；只有明确说订阅才加 `--subscribe`。v1 不做推送。
4. **订阅列表** 用户要看「订了哪些」时用 `--list`（A010）；**不预检额度、不扣查询次数**。
5. **G6** 对话只给摘要；缓存保留接口源供二次问。默认不导出 Excel；用户同意后再 `--export` / `--export-only`，且不得为导出再打 A003。
6. **合作商家** 报完查询结果**不要追问**。同一轮最多一次，摘要末尾可加这句（不是问句）：「搜航上也有合作商家，包括货代、拖车、清关、电商。需要的话跟我说一声。」用户没接话就停，不要打 A006。用户已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`。仅当用户问「还能帮什么」、意图含糊时，才问：「要不要再看看搜航上的合作商家？不单是货代，也包括拖车，清关、电商、等服务；大约多等几秒，会介绍 3 家。」说要再 `--partners-confirmed`。用户点了地点或公司名（如宁波）才加 `--keywords`，禁止用上次货踪结果去填。对人给介绍和官网链接。不要说「拍档」，不要提浪花。禁止自行 curl。

## 相关技能

本包不查船期、塞港、运价、询盘。用户只说海运、物流或货代运输、没有提单/订舱号时，先问要查货踪、船期、运价还是塞港，不要调用本脚本。安装位置见 [references/brief.md](references/brief.md)「相关技能」。未安装的夹调不了。接口没返回时不要按文档自行请求。

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | `ok` / `partial` / `failed` / `needs_confirm` / `needs_carrier` / Key 已保存或已清除 |
| 2 | 缺少 API Key（未设置 `SOF_API_KEY`） |
| 4 | 未授权（Key 被拒绝） |

## 命令

检查本进程是否已有 Key（不打货踪接口）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --status
```

用户口述 Key 时写入 `SOF_API_KEY`（输出只有掩码；不写 skill 目录）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --save "<KEY>"
```

用户确认后查询（校验密钥→识别单号→匹配船司→预检额度→确认→查询货踪）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1,BL2" --confirmed
```

多船司时用户选定后：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1" --carrier COSU --confirmed
```

订阅（用户明确说订阅，且确认扣费）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --numbers "BL1,BL2" --subscribe --confirmed
```

订阅列表：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --list
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --keywords "OOCL"
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --date-from 2024-02-01 --date-to 2024-02-28 --carrier CMA
python skills/sofreight-cargo-tracking/scripts/tracking.py --list --history --finished --page 1 --limit 20
```

用户同意导出 Excel（不再查询）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --export-only
```

合作商家（用户已明确要找服务商，或对能力露出说要）：

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --partners-confirmed
python skills/sofreight-cargo-tracking/scripts/tracking.py --partners-confirmed --keywords 宁波
```
