# Subscription NFT

基于 Sepolia 的可升级订阅会员 NFT。用户支付 `0.01 ETH` 获得 30 天会员；后续支付同样费用只会延长原 NFT 的过期时间，不会重复铸造。NFT 为灵魂绑定凭证，无法转让。

## 在线作品展示

GitHub Pages 会自动将 `frontend/` 发布成无需钱包的产品演示站。它演示了购买、续费、过期和运营补偿等状态流转，方便直接发给面试官查看。页面不连接钱包、不发起交易，也不收集任何数据。

## 功能

- UUPS 可升级 ERC-721 代理合约
- `0.01 ETH / 30 天` 默认订阅方案，可由管理员调整
- NFT 过期后仍留在钱包，但 `isActive` 返回 `false`
- 续费从未到期的结束时间累加；已过期则从当前链上时间开始计算
- `DEFAULT_ADMIN_ROLE` 可暂停销售、更新套餐和金库、提款、升级
- `OPERATOR_ROLE` 可为已有会员手动延期
- `Pausable`、`ReentrancyGuard`、基于角色的权限控制和精确支付检查
- 简洁的钱包前端，显示可读有效期与明确的交易错误提示

## 本地开发

```powershell
Copy-Item .env.example .env
npm install
npm run compile
npm test
```

## 新增：申论 AI 批改（DeepSeek）

仓库内 `shenlun-ai-backend/` 提供申论 AI 批改前后端（默认 DeepSeek，可部署到 Railway）。

```powershell
Set-Location shenlun-ai-backend
Copy-Item .env.example .env
# 填入 DEEPSEEK_API_KEY
python -m pip install -r requirements.txt
python -m pytest tests -q
uvicorn app.main:app --reload --port 8000
```

浏览器打开 `http://127.0.0.1:8000` 即可提交作文并查看批改结果。

## 部署到 Sepolia

1. 在 `.env` 设置 `SEPOLIA_RPC_URL` 和仅用于部署的钱包 `DEPLOYER_PRIVATE_KEY`。
2. 确保部署钱包有 Sepolia ETH。
3. 执行：

```powershell
npm run deploy:sepolia
```

输出的地址是 **代理合约地址**，应保存到前端配置中。初始部署钱包同时是管理员、运营节点与资金金库；生产环境建议在部署后把这些权限分别授予多签地址和运营钱包，并通过 `setTreasury` 使用多签金库。

## 升级

升级只能由 `DEFAULT_ADMIN_ROLE` 发起。升级前先完成审计、在测试网验证，并确认新实现保持既有存储布局：

```powershell
npm run upgrade:sepolia
```

该命令会读取 `.env` 的 `CONTRACT_ADDRESS`。示例升级实现位于 `contracts/test/SubscriptionNFTV2.sol`，仅供演示升级流程。

## 合约交互

| 操作 | 调用方 | 方法 |
| --- | --- | --- |
| 购买或续费 | 用户 | `subscribe()`，附带精确的订阅价格 |
| 查询会员 | 任意地址 | `membershipOf(account)` 或 `isActive(account)` |
| 人工延期 | 运营节点 | `extendMembership(account, duration)` |
| 暂停/恢复 | 管理员 | `pause()` / `unpause()` |
| 提款 | 管理员 | `withdraw()` |

合约不接受直接转账；ETH 必须通过 `subscribe()` 支付，避免资金无意锁定。
