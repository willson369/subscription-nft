from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import DEFAULT_PROMPT_TEMPLATE, settings
from .database import Base, build_engine, build_session_factory
from .models import (
    Assignment,
    AssignmentStatus,
    CorrectionRecord,
    CorrectionStatus,
    GradingStrategy,
    User,
    UserRole,
    UserStatus,
)
from .schemas import (
    AssignmentCreateRequest,
    AssignmentCreateResponse,
    AssignmentDetailResponse,
    AssignmentHistoryItem,
    CorrectionStatusResponse,
    CorrectionSubmitRequest,
    CorrectionSubmitResponse,
    GradingStrategyCreateRequest,
    GradingStrategyResponse,
    ModelInfo,
    TokenUsage,
    UserCreateRequest,
    UserCreateResponse,
)
from .services.grading import generate_grading_report
from .utils.text import estimate_word_count

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Shenlun AI Grading API", version="0.2.0")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = build_engine(database_url or settings.database_url)
    session_factory = build_session_factory(engine)
    Base.metadata.create_all(bind=engine)

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def run_grading(task_id: str):
        db: Session = session_factory()
        try:
            record = db.query(CorrectionRecord).filter(CorrectionRecord.task_id == task_id).first()
            if not record:
                return

            assignment = db.query(Assignment).filter(Assignment.id == record.assignment_id).first()
            if not assignment:
                record.status = CorrectionStatus.failed
                record.error_message = "Assignment not found."
                record.finished_at = now_utc()
                db.commit()
                return

            record.status = CorrectionStatus.processing
            db.commit()

            report = generate_grading_report(
                provider=record.model_provider,
                question_text=assignment.question_text,
                essay_text=assignment.essay_text,
                scoring_standard=record.prompt_version,
                target_score=record.target_score,
                prompt_template=record.prompt_template,
                model_name=record.model_name,
                openai_api_key=settings.openai_api_key,
                openai_base_url=settings.openai_base_url,
                openai_timeout_seconds=settings.openai_timeout_seconds,
            )

            record.overall_score = report["overall_score"]
            record.dimension_scores = report["dimension_scores"]
            record.summary = report["summary"]
            record.strengths = report["strengths"]
            record.weaknesses = report["weaknesses"]
            record.revision_suggestions = report["revision_plan"]
            record.key_issues = report["key_issues"]
            record.token_input = report["token_input"]
            record.token_output = report["token_output"]
            record.cost = report["cost"]
            record.latency_ms = report["latency_ms"]
            record.raw_result_json = report["raw_result_json"]
            record.status = CorrectionStatus.succeeded
            record.finished_at = now_utc()

            assignment.status = AssignmentStatus.graded
            assignment.latest_correction_id = record.id
            db.commit()
        except (ValueError, RuntimeError, httpx.HTTPError) as exc:
            # 后台任务失败时必须落库可追踪错误，避免状态悬挂。
            record = db.query(CorrectionRecord).filter(CorrectionRecord.task_id == task_id).first()
            if record:
                record.status = CorrectionStatus.failed
                record.error_message = str(exc)
                record.finished_at = now_utc()
                db.commit()
        finally:
            db.close()

    @app.post("/api/v1/ai/corrections", response_model=CorrectionSubmitResponse)
    def submit_correction(
        payload: CorrectionSubmitRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
    ):
        assignment = db.query(Assignment).filter(Assignment.id == payload.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found.")

        if payload.essay_text.strip() != assignment.essay_text.strip():
            assignment.essay_text = payload.essay_text.strip()
            assignment.word_count = estimate_word_count(assignment.essay_text)

        if payload.question_text.strip() != assignment.question_text.strip():
            assignment.question_text = payload.question_text.strip()

        assignment.status = AssignmentStatus.grading
        strategy = (
            db.query(GradingStrategy)
            .filter(GradingStrategy.scoring_standard == payload.scoring_standard, GradingStrategy.is_active.is_(True))
            .first()
        )

        if strategy:
            model_provider = strategy.model_provider
            model_name = strategy.model_name
            prompt_template = strategy.prompt_template
        elif payload.scoring_standard == "shenlun_v1":
            model_provider = settings.grading_model_provider
            model_name = settings.grading_model_name
            prompt_template = DEFAULT_PROMPT_TEMPLATE
        else:
            raise HTTPException(status_code=404, detail="Scoring standard not configured.")

        record = CorrectionRecord(
            assignment_id=assignment.id,
            status=CorrectionStatus.queued,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=payload.scoring_standard,
            prompt_template=prompt_template,
            target_score=payload.target_score,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        background_tasks.add_task(run_grading, record.task_id)
        return CorrectionSubmitResponse(
            task_id=record.task_id,
            status="queued",
            estimated_seconds=8,
            created_at=record.created_at,
        )

    @app.post("/api/v1/users", response_model=UserCreateResponse)
    def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)):
        if not payload.phone and not payload.email:
            raise HTTPException(status_code=400, detail="Either phone or email is required.")

        if payload.phone:
            exists_phone = db.query(User).filter(User.phone == payload.phone).first()
            if exists_phone:
                raise HTTPException(status_code=409, detail="Phone already exists.")
        if payload.email:
            exists_email = db.query(User).filter(User.email == payload.email).first()
            if exists_email:
                raise HTTPException(status_code=409, detail="Email already exists.")

        user = User(
            phone=payload.phone,
            email=payload.email,
            password_hash=payload.password_hash,
            role=UserRole.student,
            status=UserStatus.active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return UserCreateResponse(
            id=user.id,
            phone=user.phone,
            email=user.email,
            role=user.role.value,
            status=user.status.value,
            created_at=user.created_at,
        )

    @app.post("/api/v1/assignments", response_model=AssignmentCreateResponse)
    def create_assignment(payload: AssignmentCreateRequest, db: Session = Depends(get_db)):
        user = db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        assignment = Assignment(
            user_id=payload.user_id,
            title=payload.title.strip(),
            question_text=payload.question_text.strip(),
            essay_text=payload.essay_text.strip(),
            word_count=estimate_word_count(payload.essay_text),
            status=AssignmentStatus.submitted,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        return AssignmentCreateResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            title=assignment.title,
            status=assignment.status.value,
            word_count=assignment.word_count,
            submitted_at=assignment.submitted_at,
        )

    @app.get("/api/v1/assignments/{assignment_id}", response_model=AssignmentDetailResponse)
    def get_assignment(assignment_id: str, db: Session = Depends(get_db)):
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found.")

        return AssignmentDetailResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            title=assignment.title,
            question_text=assignment.question_text,
            essay_text=assignment.essay_text,
            word_count=assignment.word_count,
            status=assignment.status.value,
            latest_correction_id=assignment.latest_correction_id,
            submitted_at=assignment.submitted_at,
        )

    @app.get("/api/v1/users/{user_id}/assignments", response_model=list[AssignmentHistoryItem])
    def list_user_assignments(user_id: str, db: Session = Depends(get_db)):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        assignments = db.query(Assignment).filter(Assignment.user_id == user_id).order_by(Assignment.submitted_at.desc()).all()
        results: list[AssignmentHistoryItem] = []
        for item in assignments:
            latest_score = None
            if item.latest_correction_id:
                latest = db.query(CorrectionRecord).filter(CorrectionRecord.id == item.latest_correction_id).first()
                if latest and latest.overall_score is not None:
                    latest_score = latest.overall_score

            results.append(
                AssignmentHistoryItem(
                    assignment_id=item.id,
                    title=item.title,
                    status=item.status.value,
                    word_count=item.word_count,
                    latest_score=latest_score,
                    submitted_at=item.submitted_at,
                )
            )

        return results

    @app.post("/api/v1/admin/grading-strategies", response_model=GradingStrategyResponse)
    def create_grading_strategy(payload: GradingStrategyCreateRequest, db: Session = Depends(get_db)):
        exists = db.query(GradingStrategy).filter(GradingStrategy.scoring_standard == payload.scoring_standard).first()
        if exists:
            raise HTTPException(status_code=409, detail="Scoring standard already exists.")

        strategy = GradingStrategy(
            name=payload.name.strip(),
            scoring_standard=payload.scoring_standard.strip(),
            prompt_template=payload.prompt_template.strip(),
            model_provider=payload.model_provider.strip(),
            model_name=payload.model_name.strip(),
            is_active=payload.is_active,
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)

        return GradingStrategyResponse(
            id=strategy.id,
            name=strategy.name,
            scoring_standard=strategy.scoring_standard,
            prompt_template=strategy.prompt_template,
            model_provider=strategy.model_provider,
            model_name=strategy.model_name,
            is_active=strategy.is_active,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )

    @app.get("/api/v1/admin/grading-strategies", response_model=list[GradingStrategyResponse])
    def list_grading_strategies(db: Session = Depends(get_db)):
        items = db.query(GradingStrategy).order_by(GradingStrategy.created_at.desc()).all()
        return [
            GradingStrategyResponse(
                id=item.id,
                name=item.name,
                scoring_standard=item.scoring_standard,
                prompt_template=item.prompt_template,
                model_provider=item.model_provider,
                model_name=item.model_name,
                is_active=item.is_active,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]

    @app.get("/api/v1/ai/corrections/{task_id}", response_model=CorrectionStatusResponse)
    def get_correction_status(task_id: str, db: Session = Depends(get_db)):
        record = db.query(CorrectionRecord).filter(CorrectionRecord.task_id == task_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Task not found.")

        token_usage = None
        if record.token_input is not None and record.token_output is not None:
            token_usage = TokenUsage(
                input=record.token_input,
                output=record.token_output,
                total=record.token_input + record.token_output,
            )

        status_text = (
            "failed"
            if record.status == CorrectionStatus.failed
            else "succeeded"
            if record.status == CorrectionStatus.succeeded
            else "processing"
        )

        return CorrectionStatusResponse(
            task_id=record.task_id,
            status=status_text,
            correction_id=record.id if status_text == "succeeded" else None,
            overall_score=record.overall_score,
            dimension_scores=record.dimension_scores,
            summary=record.summary,
            key_issues=record.key_issues,
            revision_plan=record.revision_suggestions,
            model_info=ModelInfo(
                provider=record.model_provider,
                model=record.model_name,
                prompt_version=record.prompt_version,
            ),
            token_usage=token_usage,
            latency_ms=record.latency_ms,
            finished_at=record.finished_at,
            error_message=record.error_message,
        )

    @app.get("/healthz")
    def healthz():
        return {
            "status": "ok",
            "provider": settings.grading_model_provider,
            "model": settings.grading_model_name,
            "api_key_configured": bool(settings.openai_api_key),
        }

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

        @app.get("/")
        def index():
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
