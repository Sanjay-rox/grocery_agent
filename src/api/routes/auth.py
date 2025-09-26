from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
import logging
from datetime import datetime

from src.data.models import get_session, User, get_user

logger = logging.getLogger(__name__)

router = APIRouter()

class UserProfile(BaseModel):
    name: str
    email: EmailStr
    household_size: int = 2
    dietary_preferences: dict = {}
    budget_limit: float = 150.0

class LoginRequest(BaseModel):
    email: EmailStr

# Simple auth for demo - in production use JWT tokens
current_user_id = 1

@router.post("/login")
async def login(login_request: LoginRequest):
    """Simple demo login - just returns user info"""
    
    try:
        session = get_session()
        
        # Find or create user
        user = session.query(User).filter(User.email == login_request.email).first()
        
        if not user:
            # Create new user for demo
            user = User(
                name=login_request.email.split('@')[0].title(),
                email=login_request.email,
                household_size=2,
                dietary_preferences='{}',
                budget_limit=150.0,
                created_at=datetime.now()
            )
            session.add(user)
            session.commit()
            logger.info(f"Created new user: {user.email}")
        
        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "household_size": user.household_size,
            "budget_limit": user.budget_limit,
            "created_at": user.created_at.isoformat()
        }
        
        session.close()
        
        return {
            "success": True,
            "user": user_data,
            "token": f"demo_token_{user.id}",  # Demo token
            "message": "Login successful"
        }
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )

@router.get("/profile/{user_id}")
async def get_profile(user_id: int):
    """Get user profile"""
    
    try:
        session = get_session()
        user = get_user(user_id, session)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        import json
        
        profile = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "household_size": user.household_size,
            "dietary_preferences": json.loads(user.dietary_preferences) if user.dietary_preferences else {},
            "budget_limit": user.budget_limit,
            "preferred_stores": json.loads(user.preferred_stores) if user.preferred_stores else [],
            "shopping_frequency": user.shopping_frequency,
            "cooking_skill_level": user.cooking_skill_level,
            "created_at": user.created_at.isoformat()
        }
        
        session.close()
        
        return {
            "success": True,
            "profile": profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve profile: {str(e)}"
        )

@router.put("/profile/{user_id}")
async def update_profile(user_id: int, profile_data: UserProfile):
    """Update user profile"""
    
    try:
        session = get_session()
        user = get_user(user_id, session)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user fields
        user.name = profile_data.name
        user.email = profile_data.email
        user.household_size = profile_data.household_size
        user.dietary_preferences = json.dumps(profile_data.dietary_preferences)
        user.budget_limit = profile_data.budget_limit
        user.updated_at = datetime.now()
        
        session.commit()
        session.close()
        
        return {
            "success": True,
            "message": "Profile updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile: {str(e)}"
        )