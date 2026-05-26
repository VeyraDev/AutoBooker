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
from app.routers import references as references_router

app = FastAPI(title="AutoBooker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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

settings.figures_path.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/figures",
    NoCacheStaticFiles(directory=str(settings.figures_path)),
    name="figures",
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
