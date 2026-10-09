---
name: sofreight-sea-freight-price
description: 查询海运整箱挂牌运价，并可提交实盘询盘。适用于海运、物流、国际物流、货代运输。用户提到海运费、海运整箱、运价、FCL、询盘、实盘时使用。
slug: sofreight-sea-freight-price
displayName: 搜航运价
version: 0.5.5
summary: 海运整箱运价与询盘：查挂牌价，可提交实盘。
license: MIT
---

# 搜航运价

按起运港/目的港查询海运整箱挂牌运价。港名不能猜码。查价不等于询盘；未确认不得提交询盘。

过关步骤：[references/gates.md](references/gates.md)。  
开通与 Key：[references/auth.md](references/auth.md)。  
聊天给哪些列、交付三问：[references/brief.md](references/brief.md)。  
接口人话：[references/api.md](references/api.md)。

本包自带鉴权。上架到 Agent 平台时只拖这一夹，不要再装独立的 Key skill。

## 铁律

1. **G0** 缺 Key 先停。读不到 `SOF_API_KEY` / 本机 credentials 就返回 `missing_key`（退出码 2）。读 [references/auth.md](references/auth.md)。引导先在 https://www.sofreight.com/ 注册搜航账户，再打开 https://www.sofreight.com/personal_center/api_key（个人中心 → APIKEY）自行创建。遇到问题再联系搜航客服（400-048-5656、call@sofreight.com、微信 sofreight56）。优先 `SOF_API_KEY`。禁止聊天回显完整 Key，禁止调用 `MemberApiKey/create`。
2. **G2** 仅有港名必须先 `search_port.py`（POL/POD 各查一次，A004）。多候选 → `needs_port`，等用户选定；禁止猜测 UN/LOCODE。此时不调 A008。
3. **G5** 码齐后再 `price.py`（A008）。勿默认柜型；`status: empty` 是业务成功（无匹配），不要换参狂重试。
4. **G6** 按 [references/brief.md](references/brief.md)：首轮只给摘要列；源写入缓存。用户同意后再 `--export` / `--export-only`。询盘须 `--confirmed`。禁止把完整 `pricing_list` 灌进首轮聊天。
5. **合作商家** 报完查询结果**不要追问**。同一轮最多一次，摘要末尾可加这句（不是问句）：「搜航上也有合作商家，包括货代、拖车、清关、电商。需要的话跟我说一声。」用户没接话就停，不要打 A006。用户已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`。仅当用户问「还能帮什么」、意图含糊时，才问：「要不要再看看搜航上的合作商家？不单是货代，也包括拖车，清关、电商、等服务；大约多等几秒，会介绍 3 家。」说要再 `--partners-confirmed`。用户点了地点或公司名（如宁波）才加 `--keywords`，禁止用上次运价结果去填。对人给介绍和官网链接。不要说「拍档」，不要提浪花。禁止自行 curl。
6. **范围** 挂牌价查询与询盘写入都在本包。查价不等于询盘；询盘必须单独确认。订舱仍不是本包。

## 相关技能

本包不查货踪、船期、塞港。用户只说海运、物流或货代运输、没有运价/询盘时，先问要查货踪、船期、运价还是塞港，不要调用本脚本。安装位置见 [references/brief.md](references/brief.md)「相关技能」。未安装的夹调不了，不要按接口文档自行请求。

## 退出码

| 退出码 | 含义 |
|---|---|
| 0 | `ok` / `empty` / `needs_port` / `needs_confirm` / Key 已保存或已清除 |
| 1 | 业务失败或参数错误 |
| 2 | 缺少 API Key |
| 4 | 未授权（Key 被拒绝） |

## 命令

```bash
python skills/sofreight-sea-freight-price/scripts/price.py --save "<KEY>"
python skills/sofreight-sea-freight-price/scripts/search_port.py --keywords 盐田 --type POL
python skills/sofreight-sea-freight-price/scripts/search_port.py --keywords 洛杉矶 --type POD
python skills/sofreight-sea-freight-price/scripts/price.py --pol-code CNYTN --pod-code USLAX
python skills/sofreight-sea-freight-price/scripts/price.py --pol-code CNYTN --pod-code USLAX --export
python skills/sofreight-sea-freight-price/scripts/price.py --export-only
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --gp20 1
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --confirmed
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --row 1 --gp20 1 --confirmed
python skills/sofreight-sea-freight-price/scripts/price.py --partners-confirmed
python skills/sofreight-sea-freight-price/scripts/price.py --partners-confirmed --keywords 宁波
```

在本夹根目录执行时，把路径换成 `python scripts/price.py …`。
