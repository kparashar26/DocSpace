
from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router


app = FastAPI(
    title="DocSpace API",
    description=(
        "Backend API for DocSpace document management, "
        "authentication and document processing."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
