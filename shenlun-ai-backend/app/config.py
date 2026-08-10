from pydantic import BaseModel
import os


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./shenlun_ai.db")
    grading_model_provider: str = os.getenv("GRADING_MODEL_PROVIDER", "mock")
    grading_model_name: str = os.getenv("GRADING_MODEL_NAME", "shenlun-heuristic-v1")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_timeout_seconds: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


DEFAULT_PROMPT_TEMPLATE = (
    "你是资深申论阅卷老师。请基于题干与作文，严格按申论评分逻辑输出 JSON，字段必须包含："
    "overall_score(0-100), dimension_scores(立意/结构/论证/语言), summary, strengths, weaknesses, key_issues(list), "
    "revision_plan(list)。不要输出额外解释。"
)


settings = Settings()
