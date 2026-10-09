# 船期闸门

本能力过搜航七道闸。**当前船期查询不扣次数/浪花**（brief 书面声明），因此跳过 G3 额度预检与查询侧 G4 扣费确认；仍要 API Key（G0）。Excel 导出仍须用户同意。看合作商家走 `--partners-confirmed`，与查询确认分开。

成功查询的 JSON 带统一对话视图 `view`——**对用户只展 `view`**，规则见 [display.md](display.md)；清洗列与双轨说明见 [brief.md](brief.md)。

## 用户：「查一下 A 港到 B 港的船期」

| 闸 | 本能力怎么过 |
|---|---|
| G0 | `--status`。缺 Key → 整次停，读 [auth.md](auth.md)，引导注册并自助创建 Key；配 `SOF_API_KEY` 或 `--save` |
| G1 | 起运港/目的港必填：`--pol`/`--dest`（中文名、英文名或五字码）或已选定的 `--pol-code`/`--dest-code`。可选：`carrier`、`query_type`、`etd`、`sort`、过滤空班 |
| G2 | 港口主数据走 A004（`/DPort/index`）。中文/英文名先搜索；**显式五字码也要 A004 校验**（`port_code=`）。**0 个**失败；**1 个**采用；港名**多个** → `needs_port`，展示 `candidates_view`（及 `recommended`/`hint` 若有）等用户选定。**禁止猜码**。此时不调 A007 |
| G3 | **跳过**，因为当前船期查询不消耗次数/浪花，不做 A001 预检；额度不足也可查 |
| G4（查询） | **跳过扣费确认**，同上。`--confirmed` 保留兼容但无作用。G4 不准跳「声明」：本包已在 brief 写明不扣费 |
| G4（Excel） | 导出仍须用户明确同意：`--export` / `--export-only`。缺 `openpyxl` 时查询仍 `ok` + `view`，另带 `export_error` |
| G5 | 港口解析完成后直接调 A007（`confirm=0`）；空结果算业务成功，说清条件，不换参狂重试 |
| G6 | 对用户展 `view`（全量聚合概览）；stdout 清洗列每类最多 30 条，全量在缓存。未同意不写 xlsx |

```bash
# 用户说中文港名：先解析，多候选会停在 needs_port
python skills/sofreight-sailing-schedule/scripts/schedule.py --pol 盐田 --dest 雅加达

# 用户选定五字码后直接查询（无需 --confirmed）
python skills/sofreight-sailing-schedule/scripts/schedule.py --pol-code CNYTN --dest-code IDJKT
```

## 用户加条件（直航 / 中转 / 船司 / 开航日 / 最短航程）

仍走上一节过关链。**未选定港口前不调 A007**。

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py \
  --pol-code CNYTN --dest-code IDJKT \
  --query-type DIRECT --carrier MSC --sort TT_ASC --skip-blank
```

## 用户对已查结果再问

留源已开：换视角只读缓存 `source`。先报 `queried_at`。用户要最新或已过当日：先问是否重新查，禁止把缓存说成当前班期，禁止不经询问再打 A007。

## 用户要看合作商家

产品已开（brief 拍档=是）。A006 免费，不要提浪花。**禁止**报完船期就追问。同一轮最多一次，摘要末尾可加能力露出（见 SKILL 铁律「需要的话跟我说一声」）。用户没接话就停。已经明确要找服务商、货代、拖车、清关、电商或合作商家：不必再问，直接 `--partners-confirmed`（只打 A006）。仅「还能帮什么」等含糊意图才问固定句。用户点了地点或公司名才 `--keywords`，禁止用上次船期去填。对人给介绍和 `https://www.sofreight.com/introduction?detailId={id}`。`--confirmed` 不等于同意。

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --partners-confirmed
python skills/sofreight-sailing-schedule/scripts/schedule.py --partners-confirmed --keywords 宁波
```

## 写入 / Excel

- 写入：本包不做订阅、推送、订舱。跳过，因为能力只是查询船期。
- Excel：用户明确同意后才导出。查询当时加 `--export`；看完摘要再要表用 `--export-only`（读缓存，禁止再调 A007）。

```bash
python skills/sofreight-sailing-schedule/scripts/schedule.py --export-only
```
