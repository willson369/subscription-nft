from pathlib import Path

from fastapi.testclient import TestClient
from app.main import create_app


def test_submit_and_fetch_correction(tmp_path: Path):
    db_file = tmp_path / "grading.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    app = create_app(database_url=db_url)
    client = TestClient(app)

    user_resp = client.post("/api/v1/users", json={"phone": "13800000000"})
    assert user_resp.status_code == 200
    user_id = user_resp.json()["id"]

    assignment_resp = client.post(
        "/api/v1/assignments",
        json={
            "user_id": user_id,
            "title": "基层治理题",
            "question_text": "请围绕基层治理现代化写一篇申论文章，谈谈你的理解与建议。",
            "essay_text": (
                "基层治理是国家治理体系的重要基础，需要以群众需求为导向推进改革与创新。"
                "在实践中，部分地区仍存在服务流程复杂、部门协同不足、数字化能力薄弱等问题。"
                "要提升治理效能，首先要优化权责边界，构建跨部门协同机制，其次要完善数字平台，"
                "推动数据共享和流程再造，最后要强化干部能力建设和群众参与，形成共建共治共享格局。"
            ),
        },
    )
    assert assignment_resp.status_code == 200
    assignment_body = assignment_resp.json()
    assignment_id = assignment_body["id"]
    assert assignment_body["word_count"] > 50

    strategy_resp = client.post(
        "/api/v1/admin/grading-strategies",
        json={
            "name": "自定义申论模板",
            "scoring_standard": "shenlun_custom_v1",
            "prompt_template": "你是资深申论阅卷老师，请严格输出 JSON。",
            "model_provider": "mock",
            "model_name": "shenlun-heuristic-v1",
            "is_active": True,
        },
    )
    assert strategy_resp.status_code == 200

    list_strategy_resp = client.get("/api/v1/admin/grading-strategies")
    assert list_strategy_resp.status_code == 200
    assert len(list_strategy_resp.json()) == 1

    submit_payload = {
        "assignment_id": assignment_id,
        "essay_text": (
            "基层治理是国家治理现代化的关键一环。围绕群众关切推进服务创新，"
            "能够提升政策落实效率。当前基层在资源统筹、数字协同和治理韧性方面"
            "仍有短板。建议通过制度协同、技术赋能和干部能力提升三方面发力，"
            "形成问题发现、响应、反馈的闭环机制，从而提升群众满意度与治理公信力。"
            "同时，要把改革成效转化为可持续的制度成果，持续优化公共服务供给。"
        ),
        "question_text": "请围绕基层治理现代化写一篇申论文章，谈谈你的理解与建议。",
        "scoring_standard": "shenlun_custom_v1",
        "target_score": 78,
    }

    submit_resp = client.post("/api/v1/ai/corrections", json=submit_payload)
    assert submit_resp.status_code == 200
    task_id = submit_resp.json()["task_id"]
    assert submit_resp.json()["status"] == "queued"

    history_resp = client.get(f"/api/v1/users/{user_id}/assignments")
    assert history_resp.status_code == 200
    history_list = history_resp.json()
    assert len(history_list) == 1
    assert history_list[0]["assignment_id"] == assignment_id

    assignment_detail_resp = client.get(f"/api/v1/assignments/{assignment_id}")
    assert assignment_detail_resp.status_code == 200
    assert assignment_detail_resp.json()["status"] in {"grading", "graded"}

    status_resp = client.get(f"/api/v1/ai/corrections/{task_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()

    assert body["status"] in {"succeeded", "processing"}
    if body["status"] == "succeeded":
        assert isinstance(body["overall_score"], (float, int))
        assert "立意" in body["dimension_scores"]
        assert len(body["revision_plan"]) >= 3
        assert body["token_usage"]["total"] >= body["token_usage"]["input"]
