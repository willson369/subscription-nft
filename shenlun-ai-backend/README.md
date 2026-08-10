# Shenlun AI Grading Backend (MVP)

基于 **FastAPI + SQLAlchemy** 的申论 AI 批改后端基础实现，包含：

- 用户、作业、批改记录三张核心表
- 创建用户接口：`POST /api/v1/users`
- 提交作文接口：`POST /api/v1/assignments`
- 历史记录接口：`GET /api/v1/users/{user_id}/assignments`
- 查看作业详情接口：`GET /api/v1/assignments/{assignment_id}`
- 提交批改任务接口：`POST /api/v1/ai/corrections`
- 查询批改结果接口：`GET /api/v1/ai/corrections/{task_id}`
- 后台策略管理接口：`POST /api/v1/admin/grading-strategies`、`GET /api/v1/admin/grading-strategies`
- 异步后台批改流程（MVP 使用可替换的启发式评分器）

## 本地运行

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 运行测试

```powershell
python -m pytest tests -q
```

## 环境变量

- `DATABASE_URL`：数据库连接串，默认 `sqlite:///./shenlun_ai.db`
- `GRADING_MODEL_PROVIDER`：模型提供商标识，默认 `mock`
- `GRADING_MODEL_NAME`：模型名称，默认 `shenlun-heuristic-v1`
- `OPENAI_API_KEY`：当 `model_provider=openai` 时必填
- `OPENAI_BASE_URL`：OpenAI 兼容网关地址，默认 `https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS`：模型接口超时秒数，默认 `60`
