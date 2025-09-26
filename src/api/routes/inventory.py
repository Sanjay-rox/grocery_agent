from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from src.agents.planning_agent import planning_agent
from src.data.models import get_session, InventoryItem, get_user_inventory

logger = logging.getLogger(__name__)

router = APIRouter()

class AddInventoryItemRequest(BaseModel):
    user_id: int = 1
    item_name: str
    quantity: float
    unit: str
    category: Optional[str] = None
    expiry_date: Optional[str] = None

@router.get("/{user_id}")
async def get_inventory(user_id: int):
    """Get user's inventory"""
    
    try:
        result = await planning_agent.check_inventory_status(user_id)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error retrieving inventory: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve inventory: {str(e)}"
        )

@router.post("/")
async def add_inventory_item(request: AddInventoryItemRequest):
    """Add item to inventory"""
    
    try:
        session = get_session()
        
        # Parse expiry date if provided
        expiry_date = None
        if request.expiry_date:
            from datetime import datetime
            expiry_date = datetime.fromisoformat(request.expiry_date)
        
        # Create inventory item
        inventory_item = InventoryItem(
            user_id=request.user_id,
            item_name=request.item_name,
            quantity=request.quantity,
            unit=request.unit,
            category=request.category,
            expiry_date=expiry_date,
            is_running_low=request.quantity < 2
        )
        
        session.add(inventory_item)
        session.commit()
        session.close()
        
        return {
            "success": True,
            "message": "Item added to inventory successfully",
            "item": {
                "name": request.item_name,
                "quantity": request.quantity,
                "unit": request.unit
            }
        }
        
    except Exception as e:
        logger.error(f"Error adding inventory item: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add inventory item: {str(e)}"
        )

@router.delete("/{user_id}/{item_id}")
async def remove_inventory_item(user_id: int, item_id: int):
    """Remove item from inventory"""
    
    try:
        session = get_session()
        
        inventory_item = session.query(InventoryItem)\
            .filter(InventoryItem.id == item_id)\
            .filter(InventoryItem.user_id == user_id)\
            .first()
        
        if not inventory_item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        session.delete(inventory_item)
        session.commit()
        session.close()
        
        return {
            "success": True,
            "message": "Item removed from inventory successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing inventory item: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove inventory item: {str(e)}"
        )