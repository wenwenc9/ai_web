# Changelog

## 0.3.3

- 货架能搜到「海运 / 物流 / 货物跟踪」；触发专词与船期、运价、塞港互斥，避免四包同时装时抢对话。

## 0.3.2

- 品牌英文改为 sofreight：目录与 slug 从 `sofeight-cargo-tracking` 更名为 `sofreight-cargo-tracking`。

## 0.3.1

- 合入现行工厂：订阅列表改领 A010（不再占用港口搜索 A004）；G0 自助创建 Key；海运拍档 `--partners-confirmed`。
- 按 D9 恢复 A003 前 `--confirmed`；额度不够仍停在 `needs_confirm`，不打付费接口。
- brief 补产品题、三问、拍档、相关技能与留源新鲜度；补 `VERSION.txt`。

## 0.3.0

- 新增订阅列表：`--list`（`/ScheduleSubscribeV2/subscribeList`），支持关键词、订阅日期、船司、历史/已完成、分页；不扣查询额度。

## 0.2.4

- 上线前修复：openpyxl 懒加载 + `requirements.txt`；摘要字段对齐 Apifox；`--carrier` 无匹配不再静默回退；浪花按缺口校验；`push_status` 3/4/5 标签；全失败返回 `failed`。

## 0.2.3

- 步骤/接口中文名改为更顺口的产品用语（如「匹配船司」「预检额度」），去掉「人话」表述。

## 0.2.2

- 恢复 `--save` / `--clear`：用户口述 Key 时写入 `SOF_API_KEY`（当前进程 + 用户级持久化），仍禁止写入 skill 目录。

## 0.2.1

- API Key 配置改为以环境变量 `SOF_API_KEY` 为目标，禁止写入 skill 目录。

## 0.2.0

- 查询与订阅取消二次确认闸门；额度够直接调用查询/订阅接口。
- 额度不足改为 `insufficient_quota`（不再返回 `needs_confirm`）。
- 文档改用清晰步骤名：校验密钥 → 识别单号 → 匹配船司 → 预检额度 → 查询/订阅货踪 → 返回摘要。
- `--confirmed` 仅保留兼容，主流程与主文档不依赖。

## 0.1.1

- `SKILL.md` 头补齐 SkillHub 投放字段（slug / displayName / version / summary / license）。

## 0.1.0

- 首个可上架货踪包：本包鉴权，认船司→看额度→确认后查询。
- 聊天摘要；Excel 须用户同意；`--export-only` 不二次扣费。
- v1 不做推送、不做箱号。
