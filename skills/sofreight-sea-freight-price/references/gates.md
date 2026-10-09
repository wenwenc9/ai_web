# 运价过关步骤

## 用户：「盐田到洛杉矶运价多少」

| 关 | 本能力怎么过 |
|---|---|
| G0 | 直接跑业务命令。读不到 Key → `missing_key` / 退出码 2，读 [auth.md](auth.md)，引导注册并自助创建 Key |
| G1 | 起运港、目的港至少一侧有港名或 UN/LOCODE |
| G2 | `search_port.py` 解析 POL/POD（A004 `/DPort/index`）。多候选 `needs_port`，禁止猜测 UN/LOCODE。此时不调 A008 |
| G3 | **跳过额度预检**：本包未接 A001（无 type）。查价仍传 `confirm=1`。合入保持同事路径，未改为主查询 `--confirmed` |
| G4 | 用户明确要查挂牌价即查；查价不设 `--confirmed`。不等于同意询盘，也不等于同意看合作商家 |
| G5 | `price.py --pol-code … --pod-code …`（A008） |
| G6 | 对照 [brief.md](brief.md)：首轮只给摘要列；源进缓存。用 `export_hint` 询问是否导出，用 `inquiry_hint` 询问是否询盘。默认不落 Excel、不提交询盘 |

```bash
python skills/sofreight-sea-freight-price/scripts/search_port.py --keywords 盐田 --type POL
python skills/sofreight-sea-freight-price/scripts/search_port.py --keywords 洛杉矶 --type POD
python skills/sofreight-sea-freight-price/scripts/price.py --pol-code CNYTN --pod-code USLAX
```

## 用户要 Excel

- 查价当时就要明细表：G5 加 `--export`（同一次查询，不二次请求 A008）。
- 看完摘要再要表：`--export-only`（只读缓存，禁止再打 A008）。

```bash
python skills/sofreight-sea-freight-price/scripts/price.py --pol-code CNYTN --pod-code USLAX --export
python skills/sofreight-sea-freight-price/scripts/price.py --export-only
```

## 用户要询盘 / 实盘询价

必须 **单独再过 G4**。用户说「查一下运价」不等于同意询盘。

| 关 | 本能力怎么过 |
|---|---|
| G0 | 同查价，共用 Key |
| G1 | 起运港与目的港（缓存或明示）；至少一种柜型箱量 > 0，勿默认 |
| G2 | 有价询盘用缓存运价行的 UN/LOCODE 与 `spot_product_id`，禁止另猜码 |
| G3 | 跳过额度预检，因为询盘未提供独立 A001 type |
| G4 | 向用户展示预览；明确「确认」后才加 `--confirmed`。无该旗标只返回 `needs_confirm` |
| G5 | `inquiry.py --from-cache --confirmed`（预览后；有价加 `--row N`，A009）。body 须含用户条件，不只港码 |
| G6 | 把 `summary.message` 原样告诉用户。不要把询盘请求体贴进聊天 |

```bash
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --gp20 1
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --confirmed
python skills/sofreight-sea-freight-price/scripts/inquiry.py --from-cache --row 1 --gp20 1 --confirmed
```

## 用户对已查结果再问

留源已开：换视角只读缓存。先报 `queried_at`。用户要最新或已过当日：先问是否重新查，禁止把缓存说成当前报价，禁止不经询问再打 A008。

## 用户要看合作商家

产品已开（brief 拍档=是）。A006 免费，不要提浪花。**禁止**报完运价就追问。同一轮最多一次，摘要末尾可加能力露出（见 SKILL 铁律「需要的话跟我说一声」）。用户没接话就停。已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`（只打 A006）。仅「还能帮什么」等含糊意图才问固定句。用户点了地点或公司名才 `--keywords`，禁止用上次运价去填。对人给介绍和 `https://www.sofreight.com/introduction?detailId={id}`。查价 `--confirmed` 不存在；询盘 `--confirmed` 不等于同意看合作商家。

```bash
python skills/sofreight-sea-freight-price/scripts/price.py --partners-confirmed
python skills/sofreight-sea-freight-price/scripts/price.py --partners-confirmed --keywords 宁波
```
