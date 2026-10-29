from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import check_db_connection
from app.api.categories import router as categories_router
from app.api.menu_items import router as menu_items_router
from app.api.tables import router as tables_router
from app.api.orders import router as orders_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.public import router as public_router
from app.api.inventory import router as inventory_router
from app.api.payments import router as payments_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for the Restaurant Management System",
    version="0.1.0",
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Configure Cross-Origin Resource Sharing (CORS) for frontend client
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(menu_items_router)
app.include_router(tables_router)
app.include_router(orders_router)
app.include_router(public_router)
app.include_router(inventory_router)
app.include_router(payments_router)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint returning basic service information."""
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "docs_url": "/docs" if settings.DEBUG else None,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint used by frontend and monitoring services."""
    return {
        "status": "healthy",
        "version": "0.1.0",
    }


@app.get("/health/db", tags=["Health"])
async def db_health_check():
    """Database connectivity check executing SELECT 1 using SQLAlchemy."""
    result = check_db_connection()
    if not result["success"]:
        return {
            "status": "unhealthy",
            "database": result["database_url"],
            "error": result["error"],
        }
    return {
        "status": "healthy",
        "database": result["database_url"],
        "result": result["result"],
    }
