import json
import time
from typing import Any

import httpx

from ..utils.text import estimate_word_count


def _safe_split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return paragraphs if paragraphs else [text.strip()]


def _normalize_llm_payload(payload: dict[str, Any], scoring_standard: str, latency_ms: int, token_input: int, token_output: int) -> dict:
    required = ["overall_score", "dimension_scores", "summary", "strengths", "weaknesses", "key_issues", "revision_plan"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Model response missing required fields: {', '.join(missing)}")

    overall_score = float(payload["overall_score"])
    if overall_score < 0 or overall_score > 100:
        raise ValueError("Model response overall_score must be between 0 and 100.")

    dimension_scores = payload["dimension_scores"]
    if not isinstance(dimension_scores, dict):
        raise ValueError("Model response dimension_scores must be an object.")

    key_issues = payload["key_issues"]
    revision_plan = payload["revision_plan"]
    if not isinstance(key_issues, list) or not isinstance(revision_plan, list):
        raise ValueError("Model response key_issues and revision_plan must be arrays.")

    total = token_input + token_output
    cost = round(total / 1000 * 0.002, 6)
    return {
        "overall_score": round(overall_score, 2),
        "dimension_scores": dimension_scores,
        "summary": str(payload["summary"]),
        "strengths": str(payload["strengths"]),
        "weaknesses": str(payload["weaknesses"]),
        "key_issues": [str(v) for v in key_issues],
        "revision_plan": [str(v) for v in revision_plan],
        "token_input": token_input,
        "token_output": token_output,
        "cost": cost,
        "latency_ms": latency_ms,
        "raw_result_json": {
            "scoring_standard": scoring_standard,
            "provider_output": payload,
        },
    }


def generate_heuristic_report(
    *,
    question_text: str,
    essay_text: str,
    scoring_standard: str,
    target_score: float | None,
) -> dict:
    started = time.perf_counter()
    paragraphs = _safe_split_paragraphs(essay_text)
    word_count = estimate_word_count(essay_text)

    topic_keywords = {"基层", "治理", "创新", "群众", "发展", "服务", "改革", "落实", "效率"}
    hit_count = sum(1 for kw in topic_keywords if kw in essay_text)

    structure_score = min(100.0, 60 + len(paragraphs) * 6)
    argument_score = min(100.0, 58 + hit_count * 4)
    language_score = min(100.0, 55 + min(word_count, 1200) / 25)
    relevance_score = min(100.0, 60 + (12 if any(k in question_text for k in ["基层", "治理"]) else 4) + hit_count)

    dimension_scores = {
        "立意": round(relevance_score, 2),
        "结构": round(structure_score, 2),
        "论证": round(argument_score, 2),
        "语言": round(language_score, 2),
    }
    overall_score = round(sum(dimension_scores.values()) / len(dimension_scores), 2)

    key_issues = []
    if word_count < 600:
        key_issues.append("篇幅偏短，论证展开不足。")
    if len(paragraphs) < 4:
        key_issues.append("段落层次偏少，建议拆分为“提出问题-分析原因-对策建议-总结提升”。")
    if hit_count < 3:
        key_issues.append("与题干核心关键词呼应不足，建议增强政策语境和问题导向。")
    if not key_issues:
        key_issues.append("论点完整度较好，可进一步增强案例细节和数据支撑。")

    revision_plan = [
        "先重写开头 120-150 字，明确总论点和价值导向。",
        "中间段每段补充 1 个具体场景或政策案例，并加一句因果分析。",
        "结尾增加可执行对策清单（主体、动作、落地方式）。",
    ]
    if target_score and target_score > overall_score:
        revision_plan.append(f"按目标分 {target_score:.0f} 分，优先提升“论证”和“语言”两项。")

    elapsed_ms = int((time.perf_counter() - started) * 1000) + 1
    token_input = max(256, int((len(question_text) + len(essay_text)) / 1.7))
    token_output = max(180, int(len("".join(key_issues + revision_plan)) / 1.7))
    total = token_input + token_output
    cost = round(total / 1000 * 0.002, 6)

    summary = f"按 {scoring_standard} 评估，文章框架基本完整，但论证细节和关键词呼应仍有提升空间。"

    return {
        "overall_score": overall_score,
        "dimension_scores": dimension_scores,
        "summary": summary,
        "strengths": "结构框架清晰，具备政策表达意识。",
        "weaknesses": "论据密度偏低，段内推理可再深化。",
        "key_issues": key_issues,
        "revision_plan": revision_plan,
        "token_input": token_input,
        "token_output": token_output,
        "cost": cost,
        "latency_ms": elapsed_ms,
        "raw_result_json": {
            "scoring_standard": scoring_standard,
            "paragraph_count": len(paragraphs),
            "word_count": word_count,
            "keyword_hits": hit_count,
        },
    }


def generate_openai_report(
    *,
    question_text: str,
    essay_text: str,
    scoring_standard: str,
    target_score: float | None,
    prompt_template: str,
    model_name: str,
    api_key: str,
    base_url: str,
    timeout_seconds: float,
) -> dict:
    started = time.perf_counter()
    user_content = {
        "scoring_standard": scoring_standard,
        "target_score": target_score,
        "question_text": question_text,
        "essay_text": essay_text,
    }
    request_body = {
        "model": model_name,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt_template},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ],
    }

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=request_body,
        timeout=timeout_seconds,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Model API failed with {response.status_code}: {response.text}")

    payload = response.json()
    choices = payload.get("choices")
    if not choices:
        raise ValueError("Model API response missing choices.")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise ValueError("Model API response missing message content.")

    result = json.loads(content)
    usage = payload.get("usage", {})
    token_input = int(usage.get("prompt_tokens") or 0)
    token_output = int(usage.get("completion_tokens") or 0)
    if token_input == 0:
        token_input = max(256, int((len(question_text) + len(essay_text)) / 1.7))
    if token_output == 0:
        token_output = max(180, int(len(content) / 1.7))

    elapsed_ms = int((time.perf_counter() - started) * 1000) + 1
    return _normalize_llm_payload(result, scoring_standard, elapsed_ms, token_input, token_output)


def generate_grading_report(
    *,
    provider: str,
    question_text: str,
    essay_text: str,
    scoring_standard: str,
    target_score: float | None,
    prompt_template: str,
    model_name: str,
    openai_api_key: str | None,
    openai_base_url: str,
    openai_timeout_seconds: float,
) -> dict:
    if provider == "mock":
        return generate_heuristic_report(
            question_text=question_text,
            essay_text=essay_text,
            scoring_standard=scoring_standard,
            target_score=target_score,
        )
    if provider in {"openai", "deepseek"}:
        if not openai_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY or OPENAI_API_KEY is required when provider is "
                f"'{provider}'."
            )
        return generate_openai_report(
            question_text=question_text,
            essay_text=essay_text,
            scoring_standard=scoring_standard,
            target_score=target_score,
            prompt_template=prompt_template,
            model_name=model_name,
            api_key=openai_api_key,
            base_url=openai_base_url,
            timeout_seconds=openai_timeout_seconds,
        )
    raise ValueError(f"Unsupported provider: {provider}")
