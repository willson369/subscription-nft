# Shenlun AI Grading（DeepSeek + Railway）

基于 **FastAPI + DeepSeek** 的申论 AI 批改服务，前后端同仓部署：

- 前端页面：`/`（提交作文、轮询批改结果）
- 创建用户：`POST /api/v1/users`
- 提交作文：`POST /api/v1/assignments`
- 历史记录：`GET /api/v1/users/{user_id}/assignments`
- 作业详情：`GET /api/v1/assignments/{assignment_id}`
- 提交批改：`POST /api/v1/ai/corrections`
- 查询结果：`GET /api/v1/ai/corrections/{task_id}`
- 策略管理：`POST/GET /api/v1/admin/grading-strategies`

## 本地运行

```powershell
Copy-Item .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

浏览器打开 `http://127.0.0.1:8000`

## 运行测试

```powershell
python -m pytest tests -q
```

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（必填） | 空 |
| `OPENAI_API_KEY` | 备用 Key（与上者二选一） | 空 |
| `GRADING_MODEL_PROVIDER` | `deepseek` / `openai` / `mock` | `deepseek` |
| `GRADING_MODEL_NAME` | 模型名 | `deepseek-chat` |
| `OPENAI_BASE_URL` | OpenAI 兼容网关 | `https://api.deepseek.com/v1` |
| `OPENAI_TIMEOUT_SECONDS` | 超时秒数 | `90` |
| `DATABASE_URL` | 数据库 | `sqlite:///./shenlun_ai.db` |
| `CORS_ORIGINS` | CORS 来源 | `*` |

## Railway 部署

```powershell
railway init --name shenlun-ai-grading -y
railway variables --set "DEEPSEEK_API_KEY=sk-xxx" --set "GRADING_MODEL_PROVIDER=deepseek" --set "GRADING_MODEL_NAME=deepseek-chat" --set "OPENAI_BASE_URL=https://api.deepseek.com/v1"
railway up --detach
railway domain
```
