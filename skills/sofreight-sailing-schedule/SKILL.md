---
name: sofreight-sailing-schedule
description: 按起运港到目的港查询直航与中转船期。适用于海运、物流、国际物流、货代运输。用户提到船期、班期、开航日、ETD、ETA时使用。
slug: sofreight-sailing-schedule
displayName: 搜航船期
version: 0.6.6
summary: 海运船期：起运港到目的港直航与中转班期。
license: MIT
---

# 搜航船期

按起运港、目的港查询船期。可用中文港名或五字码。须有效 API Key；**当前查询不扣次数/浪花**，港口解析完成后可直接查询。

过关步骤：[references/gates.md](references/gates.md)。  
开通与 Key：[references/auth.md](references/auth.md)。  
交付（三问皆开）与聊天列：[references/brief.md](references/brief.md)。  
**统一展示（所有前端必须一致）：[references/display.md](references/display.md)。**  
接口人话：[references/api.md](references/api.md)。

本包自带鉴权。上架到 Agent 平台时只拖这一夹，不要再装独立的 Key skill。

**运行环境**：查询/港口解析等主流程不依赖第三方库，用系统默认 `python` 即可；
只有导出 Excel 需要 `openpyxl`（缺包时返回友好错误与安装指引，不会抛堆栈）。

## 铁律

1. **G0** 缺 Key 先停。跑 `--status`；读 [references/auth.md](references/auth.md)。引导先在 https://www.sofreight.com/ 注册搜航账户，再打开 https://www.sofreight.com/personal_center/api_key（个人中心 → APIKEY）自行创建。遇到问题再联系搜航客服（400-048-5656、call@sofreight.com、微信 sofreight56）。优先 `SOF_API_KEY`。禁止聊天回显完整 Key，禁止调用 `MemberApiKey/create`。
2. **G2** 港口走 A004。中文/英文港名先搜；**显式五字码也要校验**。多个候选时 `needs_port`，等用户选定。脚本会给出候选表 `candidates_view` 与推荐（首位通常是全港/主港汇总，见 `hint`）——把候选表展示给用户并说明推荐，用户选定后再带 `--pol-code`/`--dest-code`。禁止猜码。此时不调 A007。
3. **G3 / 查询侧 G4** 跳过额度预检与扣费确认（当前不扣次数/浪花，brief 已书面声明）。港口解析完成后直接查。`--confirmed` 兼容保留但无作用，也不等于同意看合作商家。
4. **G6** 首轮对用户展 `view`；stdout 清洗列每类最多 30 条，完整在缓存。默认不导出 Excel；用户同意后再 `--export` / `--export-only`。缺 `openpyxl` 时查询仍成功，另看 `export_error`。
5. **合作商家** 报完查询结果**不要追问**。同一轮最多一次，摘要末尾可加这句（不是问句）：「搜航上也有合作商家，包括货代、拖车、清关、电商。需要的话跟我说一声。」用户没接话就停，不要打 A006。用户已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`。仅当用户问「还能帮什么」、意图含糊时，才问：「要不要再看看搜航上的合作商家？不单是货代，也包括拖车，清关、电商、等服务；大约多等几秒，会介绍 3 家。」说要再 `--partners-confirmed`。用户点了地点或公司名（如宁波）才加 `--keywords`，禁止用上次船期结果去填。对人给介绍和官网链接。不要说「拍档」，不要提浪花。禁止自行 curl。
6. **统一展示**：成功查询 JSON 自带 `view`（脚本生成：直航共舱概览、空班单列、近 3 班；中转精简表；尾注）。**原样展示 `view`，禁止自行重排或改版**，见 [references/display.md](references/display.md)。`direct`/`transfer` 可能截断，仅供二次加工，不替代 `view`；二次问全量读缓存。

## 相关技能

本包不查货踪、塞港、运价、询盘。用户只说海运、物流或货代运输、没有船期/班期时，先问要查货踪、船期、运价还是塞港，不要调用本脚本。安装位置见 [references/brief.md](references/brief.md)「相关技能」。未安装的夹调不了，不要按接口文档自行请求。

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | `ok` / `needs_port` / Key 已保存或已清除 |
| 2 | 缺少 API Key |
| 4 | 未授权（Key 被拒绝） |

## 命令

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --status
```

用户说中文港名（多候选会停在 `needs_port`）：

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --pol 盐田 --dest 雅加达
```

用户选定五字码后直接查询：

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --pol-code CNYTN --dest-code IDJKT
```

查询并导出 Excel：

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --pol-code CNYTN --dest-code IDJKT --export
```

只读缓存导出：

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --export-only
```

合作商家（用户已明确要找服务商，或对能力露出说要）：

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --partners-confirmed
python skills/sofreight-sailing-schedule/scripts/schedule.py --partners-confirmed --keywords 宁波
```
