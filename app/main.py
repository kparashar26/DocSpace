
from fastapi import FastAPI

from app.api.routes.auth import router as auth_router


app = FastAPI(
    title="DocSpace API",
    description="Backend API for DocSpace document management and authentication.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Register API routers
app.include_router(auth_router)


# Health check
@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
