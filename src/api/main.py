from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from datetime import datetime
import os

from src.core.config import Config
from src.data.models import init_db
from .routes import chat, meal_plans, shopping, inventory, auth
from .middleware import RateLimitMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Grocery AI API",
    description="Intelligent grocery management and meal planning AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (using the class now)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Chat"])
app.include_router(meal_plans.router, prefix="/api/v1/meal-plans", tags=["Meal Planning"])
app.include_router(shopping.router, prefix="/api/v1/shopping", tags=["Shopping"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])

# Conditionally serve static files if build directory exists
frontend_build_path = "frontend/build"
if os.path.exists(frontend_build_path) and os.path.isdir(frontend_build_path):
    app.mount("/", StaticFiles(directory=frontend_build_path, html=True), name="static")
    logger.info(f"Serving static files from {frontend_build_path}")
else:
    logger.warning(f"Frontend build directory not found: {frontend_build_path}")
    logger.info("Skipping static file serving. Frontend should run on separate port.")

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    logger.info("Starting Grocery AI API...")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    logger.info("Grocery AI API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Grocery AI API...")

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "grocery-ai-api",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/status")
async def system_status():
    """Get system status"""
    from src.agents.master_agent import master_agent
    
    try:
        status = await master_agent.get_system_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG,
        log_level="info"
    )