# 搜航运价 · 开通与 Key

本包自带鉴权（含港口码与运价脚本）。缺 Key 时先停，见过关检查 G0。

`search_port.py` 与 `price.py` 共用同一份 Key（本夹 `sofreight_runtime`）。

## 怎么拿到 Key

1. 在 https://www.sofreight.com/ 注册搜航账户（未注册不能创建 Key）
2. 登录后打开 https://www.sofreight.com/personal_center/api_key ，或走 **个人中心 → APIKEY**，自行创建
3. 遇到问题再联系搜航客服：电话 400-048-5656，邮箱 call@sofreight.com，微信 sofreight56

禁止调用 `MemberApiKey/create`，禁止用账号密码换会过期的 Token。Agent 只引导到前台页面，不要代用户调创建接口。

不要在聊天、工单、SKILL 文件或日志里粘贴完整 Key。stdout 只允许掩码（如 `sk-****6789`）。

## 配置

优先执行器环境变量 `SOF_API_KEY`；其次本机 `~/.sofreight/credentials.json`（`--save`）。

查码 / 查价时自动读 Key，**不必先跑检查命令**。读不到就返回 `missing_key`、退出码 2。

```bash
python skills/sofreight-sea-freight-price/scripts/price.py --save "<KEY>"
python skills/sofreight-sea-freight-price/scripts/price.py --clear
```

在本夹根目录执行时，把路径换成 `python scripts/price.py --save "<KEY>"`。

## 常见情况

| 情况 | 怎么做 |
|---|---|
| 退出码 2 / `missing_key` | 按上文注册并自助创建 Key，再配置，重启执行器 |
| 退出码 4 / `unauthorized` | Key 被拒绝，联系客服，不盲重试 |
| 需要会员 / 浪花不足 / 浪花禁用 | 人话说明，不是 Key 没配上 |
