from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import logging
from datetime import datetime

from src.agents.master_agent import master_agent

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    user_id: int = 1  # Default user for demo
    context: Dict[str, Any] = {}

class ChatResponse(BaseModel):
    response: str
    success: bool
    agent_used: str
    suggestions: List[str] = []
    timestamp: str
    data: Dict[str, Any] = {}

# Store active WebSocket connections
active_connections: List[WebSocket] = []

@router.post("/message", response_model=ChatResponse)
async def send_chat_message(chat_message: ChatMessage):
    """Send a message to the AI and get response"""
    
    try:
        logger.info(f"Processing chat message from user {chat_message.user_id}: {chat_message.message}")
        
        # Process message with master agent
        response = await master_agent.process_user_message(
            user_id=chat_message.user_id,
            message=chat_message.message,
            context=chat_message.context
        )
        
        # Format response
        chat_response = ChatResponse(
            response=response.get("response", "I couldn't process your request."),
            success=response.get("success", False),
            agent_used=response.get("agent_used", "unknown"),
            suggestions=response.get("suggestions", []),
            timestamp=datetime.now().isoformat(),
            data=response.get("data", {})
        )
        
        logger.info(f"Chat response generated successfully for user {chat_message.user_id}")
        return chat_response
        
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )

@router.websocket("/ws/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time chat"""
    
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        logger.info(f"WebSocket connection established for user {user_id}")
        
        # Send welcome message
        welcome_message = {
            "type": "system",
            "message": "Connected to Grocery AI! How can I help you today?",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(welcome_message))
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_message = message_data.get("message", "")
            context = message_data.get("context", {})
            
            if not user_message.strip():
                continue
            
            logger.info(f"WebSocket message from user {user_id}: {user_message}")
            
            try:
                # Process with master agent
                response = await master_agent.process_user_message(
                    user_id=user_id,
                    message=user_message,
                    context=context
                )
                
                # Send response back
                ws_response = {
                    "type": "ai_response",
                    "message": response.get("response", "I couldn't process your request."),
                    "success": response.get("success", False),
                    "agent_used": response.get("agent_used", "unknown"),
                    "suggestions": response.get("suggestions", []),
                    "data": response.get("data", {}),
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send_text(json.dumps(ws_response))
                
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                
                error_response = {
                    "type": "error",
                    "message": "Sorry, I encountered an error processing your request.",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send_text(json.dumps(error_response))
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket connection closed for user {user_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@router.get("/history/{user_id}")
async def get_chat_history(user_id: int, limit: int = 20):
    """Get chat history for a user"""
    
    try:
        from src.core.memory import ConversationMemory
        
        memory = ConversationMemory(user_id)
        conversations = memory.get_recent_conversations(limit)
        
        return {
            "user_id": user_id,
            "conversations": conversations,
            "total": len(conversations),
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve chat history: {str(e)}"
        )

@router.delete("/history/{user_id}")
async def clear_chat_history(user_id: int):
    """Clear chat history for a user"""
    
    try:
        from src.core.memory import ConversationMemory
        
        memory = ConversationMemory(user_id)
        # Clear conversation history
        memory.conversation_history = []
        memory.save_memory()
        
        return {
            "message": f"Chat history cleared for user {user_id}",
            "cleared_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear chat history: {str(e)}"
        )

@router.post("/quick-actions")
async def quick_actions(user_id: int = 1):
    """Get suggested quick actions for the user"""
    
    try:
        # Get user's current status to suggest relevant actions
        from src.agents.planning_agent import planning_agent
        from src.agents.shopping_agent import shopping_agent
        
        planning_summary = await planning_agent.get_planning_summary(user_id)
        
        quick_actions = []
        
        # Suggest based on user's current state
        if not planning_summary.get("current_meal_plan", {}).get("exists"):
            quick_actions.append({
                "action": "create_meal_plan",
                "title": "Create Meal Plan",
                "description": "Plan your meals for the week",
                "icon": "calendar"
            })
        
        if planning_summary.get("inventory_status", {}).get("low_stock_items", 0) > 0:
            low_count = planning_summary["inventory_status"]["low_stock_items"]
            quick_actions.append({
                "action": "check_inventory",
                "title": "Check Low Stock",
                "description": f"{low_count} items running low",
                "icon": "alert"
            })
        
        # Always available actions
        quick_actions.extend([
            {
                "action": "find_deals",
                "title": "Find Deals",
                "description": "Discover grocery savings",
                "icon": "dollar"
            },
            {
                "action": "create_shopping_list",
                "title": "Shopping List",
                "description": "Create smart shopping list",
                "icon": "list"
            },
            {
                "action": "compare_prices",
                "title": "Compare Prices",
                "description": "Find best prices",
                "icon": "compare"
            }
        ])
        
        return {
            "user_id": user_id,
            "quick_actions": quick_actions[:6],  # Limit to 6 actions
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating quick actions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quick actions: {str(e)}"
        )