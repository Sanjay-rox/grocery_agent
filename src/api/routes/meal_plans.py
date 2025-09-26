from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import json

from src.agents.planning_agent import planning_agent
from src.data.models import get_session, MealPlan

logger = logging.getLogger(__name__)

router = APIRouter()

class CreateMealPlanRequest(BaseModel):
    user_id: int = 1
    preferences: Dict[str, Any] = {}
    start_date: Optional[str] = None

@router.post("/")
async def create_meal_plan(request: CreateMealPlanRequest):
    """Create a new meal plan"""
    
    try:
        start_date = None
        if request.start_date:
            from datetime import date
            start_date = date.fromisoformat(request.start_date)
        
        result = await planning_agent.create_weekly_meal_plan(
            user_id=request.user_id,
            preferences=request.preferences,
            start_date=start_date
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Meal plan created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating meal plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create meal plan: {str(e)}"
        )

@router.get("/{user_id}")
async def get_meal_plans(user_id: int):
    """Get meal plans for user"""
    
    try:
        session = get_session()
        
        meal_plans = session.query(MealPlan)\
            .filter(MealPlan.user_id == user_id)\
            .order_by(MealPlan.created_at.desc())\
            .limit(10)\
            .all()
        
        plans_data = []
        for mp in meal_plans:
            plans_data.append({
                "id": mp.id,
                "week_start": mp.week_start_date.isoformat(),
                "week_end": mp.week_end_date.isoformat(),
                "total_cost": mp.total_cost,
                "is_active": mp.is_active,
                "status": mp.completion_status,
                "created_at": mp.created_at.isoformat()
            })
        
        session.close()
        
        return {
            "success": True,
            "data": plans_data
        }
        
    except Exception as e:
        logger.error(f"Error retrieving meal plans: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve meal plans: {str(e)}"
        )

@router.get("/{user_id}/{plan_id}")
async def get_meal_plan_details(user_id: int, plan_id: int):
    """Get detailed meal plan"""
    
    try:
        session = get_session()
        
        meal_plan = session.query(MealPlan)\
            .filter(MealPlan.id == plan_id)\
            .filter(MealPlan.user_id == user_id)\
            .first()
        
        if not meal_plan:
            raise HTTPException(status_code=404, detail="Meal plan not found")
        
        meal_data = json.loads(meal_plan.meal_data) if meal_plan.meal_data else {}
        shopping_data = json.loads(meal_plan.shopping_list_data) if meal_plan.shopping_list_data else []
        
        result = {
            "id": meal_plan.id,
            "week_start": meal_plan.week_start_date.isoformat(),
            "week_end": meal_plan.week_end_date.isoformat(),
            "meals": meal_data,
            "shopping_list": shopping_data,
            "total_cost": meal_plan.total_cost,
            "is_active": meal_plan.is_active,
            "status": meal_plan.completion_status,
            "created_at": meal_plan.created_at.isoformat()
        }
        
        session.close()
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving meal plan details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve meal plan details: {str(e)}"
        )