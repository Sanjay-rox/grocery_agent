import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class Config:
    """Configuration manager for the Grocery AI Agent"""
    
    # LLM Configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "llama-3.1-8b-instant")  # Updated to current model
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "llama3.2:3b")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/grocery_agent.db")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "localhost")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Free API Keys
    SPOONACULAR_API_KEY: str = os.getenv("SPOONACULAR_API_KEY", "")
    USDA_API_KEY: str = os.getenv("USDA_API_KEY", "")  # Optional, USDA is free without key
    
    # Cache Configuration
    CACHE_DIR: str = os.getenv("CACHE_DIR", "./data/cache")
    CACHE_EXPIRY_HOURS: int = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))
    
    # Web Scraping Configuration
    SCRAPING_DELAY: float = float(os.getenv("SCRAPING_DELAY", "1.0"))
    USER_AGENT: str = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Notification Configuration
    NOTIFICATION_EMAIL: str = os.getenv("NOTIFICATION_EMAIL", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    
    # AI Agent Configuration
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "2048"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    
    # Store Configuration
    SUPPORTED_STORES: Dict[str, Dict] = {
        "walmart": {
            "base_url": "https://www.walmart.com",
            "search_endpoint": "/search",
            "enabled": True
        },
        "target": {
            "base_url": "https://www.target.com",
            "search_endpoint": "/s",
            "enabled": True
        },
        "instacart": {
            "base_url": "https://www.instacart.com",
            "search_endpoint": "/store",
            "enabled": False  # Requires special handling
        }
    }
    
    # Budget and Planning Defaults
    DEFAULT_BUDGET_LIMIT: float = 150.0
    DEFAULT_HOUSEHOLD_SIZE: int = 2
    MEAL_PLAN_DAYS: int = 7
    
    # Health and Nutrition
    DAILY_CALORIE_TARGETS: Dict[str, int] = {
        "adult_male": 2500,
        "adult_female": 2000,
        "child": 1500,
        "elderly": 1800
    }
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate essential configuration"""
        if not cls.GROQ_API_KEY:
            print("Warning: GROQ_API_KEY not found. LLM functionality may be limited.")
            return False
        return True
    
    @classmethod
    def get_store_config(cls, store_name: str) -> Optional[Dict]:
        """Get configuration for a specific store"""
        return cls.SUPPORTED_STORES.get(store_name.lower())
    
    @classmethod
    def create_directories(cls) -> None:
        """Create necessary directories"""
        import os
        directories = [
            cls.CACHE_DIR,
            "./data",
            "./data/store_data",
            "./logs"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert config to dictionary for debugging"""
        return {
            "groq_configured": bool(cls.GROQ_API_KEY),
            "database_url": cls.DATABASE_URL,
            "debug_mode": cls.DEBUG,
            "supported_stores": list(cls.SUPPORTED_STORES.keys()),
            "cache_dir": cls.CACHE_DIR
        }

# Initialize configuration and create directories
Config.create_directories()
config_valid = Config.validate_config()

if not config_valid:
    print("⚠️  Configuration validation failed. Please check your .env file.")