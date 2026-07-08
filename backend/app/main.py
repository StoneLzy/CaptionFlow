from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.jobs import router as jobs_router
from app.api.settings import router as settings_router
from app.core.config import get_settings
from app.core.health import probe_dependencies

app = FastAPI(title="CaptionFlow")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^(tauri://localhost|https?://tauri\.localhost|https?://localhost(:\d+)?|"
        r"https?://127\.0\.0\.1(:\d+)?)$"
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)
app.include_router(settings_router)


@app.get("/api/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return probe_dependencies(settings)
