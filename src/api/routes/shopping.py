from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from src.agents.shopping_agent import shopping_agent
from src.services.order_service import order_service
from src.data.models import get_session, ShoppingList

logger = logging.getLogger(__name__)

router = APIRouter()

class CreateShoppingListRequest(BaseModel):
    user_id: int = 1
    include_price_data: bool = True
    context: Dict[str, Any] = {}

class OptimizeListRequest(BaseModel):
    user_id: int = 1
    shopping_list_id: Optional[int] = None

class FindDealsRequest(BaseModel):
    user_id: int = 1
    min_savings: float = 1.0
    product_names: List[str] = []

class CreateOrderRequest(BaseModel):
    user_id: int = 1
    shopping_list_id: int
    delivery_service: str = "instacart"
    delivery_date: Optional[str] = None
    auto_confirm: bool = False

@router.post("/lists")
async def create_shopping_list(request: CreateShoppingListRequest):
    """Create a smart shopping list"""
    
    try:
        logger.info(f"Creating shopping list for user {request.user_id}")
        
        # Add include_price_data to context
        context = request.context.copy()
        context["include_price_data"] = request.include_price_data
        
        result = await shopping_agent.create_smart_shopping_list(
            user_id=request.user_id,
            context=context
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Shopping list created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating shopping list: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create shopping list: {str(e)}"
        )

@router.get("/lists/{user_id}")
async def get_shopping_lists(user_id: int, limit: int = Query(10, ge=1, le=50)):
    """Get shopping lists for a user"""
    
    try:
        session = get_session()
        
        shopping_lists = session.query(ShoppingList)\
            .filter(ShoppingList.user_id == user_id)\
            .order_by(ShoppingList.created_at.desc())\
            .limit(limit)\
            .all()
        
        lists_data = []
        for sl in shopping_lists:
            lists_data.append({
                "id": sl.id,
                "name": sl.list_name,
                "status": sl.status,
                "estimated_total": sl.estimated_total,
                "item_count": len(sl.items_data) if sl.items_data else 0,
                "created_at": sl.created_at.isoformat()
            })
        
        session.close()
        
        return {
            "success": True,
            "data": lists_data,
            "total": len(lists_data)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving shopping lists: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shopping lists: {str(e)}"
        )

@router.get("/lists/{user_id}/{list_id}")
async def get_shopping_list_details(user_id: int, list_id: int):
    """Get detailed shopping list"""
    
    try:
        session = get_session()
        
        shopping_list = session.query(ShoppingList)\
            .filter(ShoppingList.id == list_id)\
            .filter(ShoppingList.user_id == user_id)\
            .first()
        
        if not shopping_list:
            raise HTTPException(status_code=404, detail="Shopping list not found")
        
        import json
        items_data = json.loads(shopping_list.items_data) if shopping_list.items_data else []
        
        result = {
            "id": shopping_list.id,
            "name": shopping_list.list_name,
            "status": shopping_list.status,
            "items": items_data,
            "estimated_total": shopping_list.estimated_total,
            "budget_limit": shopping_list.budget_limit,
            "preferred_stores": shopping_list.preferred_stores,
            "created_at": shopping_list.created_at.isoformat(),
            "updated_at": shopping_list.updated_at.isoformat() if shopping_list.updated_at else None
        }
        
        session.close()
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving shopping list details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shopping list details: {str(e)}"
        )

@router.post("/optimize")
async def optimize_shopping_list(request: OptimizeListRequest):
    """Optimize shopping list for cost and efficiency"""
    
    try:
        logger.info(f"Optimizing shopping list for user {request.user_id}")
        
        result = await shopping_agent.optimize_shopping_list(
            user_id=request.user_id,
            context={"shopping_list_id": request.shopping_list_id}
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Shopping list optimized successfully"
        }
        
    except Exception as e:
        logger.error(f"Error optimizing shopping list: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to optimize shopping list: {str(e)}"
        )

@router.post("/deals")
async def find_deals(request: FindDealsRequest):
    """Find current grocery deals"""
    
    try:
        logger.info(f"Finding deals for user {request.user_id}")
        
        context = {
            "min_savings": request.min_savings,
            "product_names": request.product_names
        }
        
        result = await shopping_agent.find_current_deals(
            user_id=request.user_id,
            context=context
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Deals found successfully"
        }
        
    except Exception as e:
        logger.error(f"Error finding deals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find deals: {str(e)}"
        )

@router.get("/route/{user_id}")
async def get_shopping_route(user_id: int):
    """Get optimized shopping route"""
    
    try:
        logger.info(f"Planning shopping route for user {user_id}")
        
        result = await shopping_agent.plan_shopping_route(user_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Shopping route planned successfully"
        }
        
    except Exception as e:
        logger.error(f"Error planning shopping route: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to plan shopping route: {str(e)}"
        )

@router.get("/spending/{user_id}")
async def get_spending_patterns(user_id: int):
    """Get spending patterns and analysis"""
    
    try:
        logger.info(f"Analyzing spending patterns for user {user_id}")
        
        result = await shopping_agent.track_spending_patterns(user_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Spending analysis completed"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing spending patterns: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze spending patterns: {str(e)}"
        )

@router.post("/orders")
async def create_order(request: CreateOrderRequest):
    """Create order from shopping list"""
    
    try:
        logger.info(f"Creating order for user {request.user_id}")
        
        # Parse delivery date if provided
        delivery_date = None
        if request.delivery_date:
            from datetime import datetime
            delivery_date = datetime.fromisoformat(request.delivery_date)
        
        result = await order_service.create_order_from_shopping_list(
            user_id=request.user_id,
            shopping_list_id=request.shopping_list_id,
            delivery_service=request.delivery_service,
            delivery_date=delivery_date,
            auto_confirm=request.auto_confirm
        )
        
        return {
            "success": True,
            "data": result,
            "message": "Order created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create order: {str(e)}"
        )

@router.get("/orders/{user_id}")
async def get_order_history(user_id: int, limit: int = Query(10, ge=1, le=50)):
    """Get order history for user"""
    
    try:
        logger.info(f"Retrieving order history for user {user_id}")
        
        result = await order_service.get_order_history(user_id, limit)
        
        return {
            "success": True,
            "data": result,
            "message": "Order history retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving order history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve order history: {str(e)}"
        )

@router.get("/orders/{user_id}/{order_id}")
async def track_order(user_id: int, order_id: int):
    """Track specific order"""
    
    try:
        logger.info(f"Tracking order {order_id} for user {user_id}")
        
        result = await order_service.track_order(user_id, order_id)
        
        return {
            "success": True,
            "data": result,
            "message": "Order tracking retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error tracking order: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to track order: {str(e)}"
        )

@router.delete("/orders/{user_id}/{order_id}")
async def cancel_order(user_id: int, order_id: int, reason: str = ""):
    """Cancel an order"""
    
    try:
        logger.info(f"Cancelling order {order_id} for user {user_id}")
        
        result = await order_service.cancel_order(user_id, order_id, reason)
        
        return {
            "success": True,
            "data": result,
            "message": "Order cancelled successfully"
        }
        
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel order: {str(e)}"
        )