# 搜航 API Key（本包自带）

货踪上架是**这一夹**。缺 Key 时读本文，不要另找独立 Key skill。

## 怎么拿到 Key

1. 在 https://www.sofreight.com/ 注册搜航账户（未注册不能创建 Key）
2. 登录后打开 https://www.sofreight.com/personal_center/api_key ，或走 **个人中心 → APIKEY**，自行创建
3. 遇到问题再联系搜航客服：电话 400-048-5656，邮箱 call@sofreight.com，微信 sofreight56

禁止调用 `MemberApiKey/create`，禁止用账号密码换会过期的 Token。Agent 只引导到前台页面，不要代用户调创建接口。

不要在聊天、工单、SKILL 文件或日志里粘贴完整 Key。stdout 只允许掩码（如 `sk-****6789`）。

## 配到哪里（优先顺序）

1. **智能体平台 Secret / 环境变量**：把 Key 注入**执行脚本的进程**，变量名 `SOF_API_KEY`。只配在聊天模型侧不够。改完后重启执行器，再跑 `--status`。
2. **本机文件**：`~/.sofreight/credentials.json`（可用 `--save`）。环境变量优先于文件。

## 本包命令（不连搜航业务接口）

```bash
python skills/sofreight-cargo-tracking/scripts/tracking.py --status
python skills/sofreight-cargo-tracking/scripts/tracking.py --save "<KEY>"
python skills/sofreight-cargo-tracking/scripts/tracking.py --clear
```

`--status` 只看当前进程能否读到 Key，`remote_validated=false` 正常；第一次真实查询才会验证 Key 是否被搜航接受。不要用订阅（`--subscribe`）来试 Key。

平台若在本夹根目录执行，把上面路径换成 `python scripts/tracking.py --status`。

## 常见情况

| 情况 | 怎么做 |
|---|---|
| `--status` 为 `missing` / 退出码 2 | 按上文注册并自助创建 Key，再配置，重启执行器 |
| 退出码 4 / `unauthorized` | Key 被拒绝，联系客服，不盲重试 |
| 需要会员 / 浪花不足 / 浪花禁用 | 人话说明，不是 Key 没配上 |
| `needs_confirm` 且额度不够 | 引导充值或减少单号；不要重试付费接口 |
