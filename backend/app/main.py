from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.static_files import NoCacheStaticFiles
from app.routers import auth as auth_router
from app.routers import books as books_router
from app.routers import chapters as chapters_router
from app.routers import citations as citations_router
from app.routers import config as config_router
from app.routers import figures as figures_router
from app.routers import assistant as assistant_router
from app.routers import review as review_router
from app.routers import literature as literature_router
from app.routers import outline as outline_router
from app.routers import preface as preface_router
from app.routers import references as references_router
from app.routers import library as library_router
from app.routers import book_jobs as book_jobs_router
from app.routers import notifications as notifications_router
from app.routers import feedback as feedback_router
from app.routers import optimization as optimization_router
from app.routers import assets as assets_router
from app.routers import intake as intake_router
from app.routers import review_stage as review_stage_router
from app.routers import review_workspace as review_workspace_router
from app.routers import writing_basis as writing_basis_router
from app.routers import project_assistant as project_assistant_router
from app.routers import format_strategy as format_strategy_router
from app.routers import sources as sources_router
from app.routers import memories as memories_router

app = FastAPI(title="AutoBooker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(books_router.router)
app.include_router(references_router.router)
app.include_router(literature_router.router)
app.include_router(config_router.router)
app.include_router(citations_router.router)
app.include_router(review_router.router)
app.include_router(outline_router.router)
app.include_router(chapters_router.router)
app.include_router(figures_router.router)
app.include_router(assistant_router.router)
app.include_router(preface_router.router)
app.include_router(library_router.router)
app.include_router(book_jobs_router.router)
app.include_router(notifications_router.router)
app.include_router(feedback_router.router)
app.include_router(optimization_router.router)
app.include_router(assets_router.router)
app.include_router(intake_router.router)
app.include_router(writing_basis_router.router)
app.include_router(project_assistant_router.router)
app.include_router(sources_router.router)
app.include_router(format_strategy_router.router)
app.include_router(review_stage_router.router)
app.include_router(review_workspace_router.router)
app.include_router(memories_router.router)

if settings.ASSETS_COMPAT_STATIC:
    settings.figures_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/figures",
        NoCacheStaticFiles(directory=str(settings.figures_path)),
        name="figures",
    )


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
