from pydantic import BaseModel
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _resolve_api_key() -> str | None:
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./shenlun_ai.db")
    grading_model_provider: str = os.getenv("GRADING_MODEL_PROVIDER", "deepseek")
    grading_model_name: str = os.getenv("GRADING_MODEL_NAME", "deepseek-chat")
    openai_api_key: str | None = _resolve_api_key()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    openai_timeout_seconds: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")


DEFAULT_PROMPT_TEMPLATE = (
    "你是资深申论阅卷老师。请基于题干与作文，严格按申论评分逻辑输出 JSON，字段必须包含："
    "overall_score(0-100), dimension_scores(立意/结构/论证/语言), summary, strengths, weaknesses, key_issues(list), "
    "revision_plan(list)。不要输出额外解释。"
)


settings = Settings()
