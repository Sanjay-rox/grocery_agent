import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import logging

from src.data.models import get_session, User, ShoppingList, Order, get_user
from src.core.config import Config

logger = logging.getLogger(__name__)

class OrderManagementService:
    """Service for managing automated grocery orders"""
    
    def __init__(self):
        self.supported_services = {
            "instacart": {
                "name": "Instacart",
                "api_available": False,  # Would require business partnership
                "supports_automation": True,
                "delivery_fee": 3.99,
                "min_order": 35.00
            },
            "walmart_delivery": {
                "name": "Walmart Grocery Delivery",
                "api_available": False,  # Would require API access
                "supports_automation": True,
                "delivery_fee": 7.95,
                "min_order": 35.00
            },
            "amazon_fresh": {
                "name": "Amazon Fresh",
                "api_available": False,  # Would require Amazon API
                "supports_automation": True,
                "delivery_fee": 0.00,  # Free with Prime
                "min_order": 50.00
            }
        }
        
        # For demo purposes, we'll simulate order management
        self.demo_mode = True
    
    async def create_order_from_shopping_list(
        self,
        user_id: int,
        shopping_list_id: int,
        delivery_service: str = "instacart",
        delivery_date: Optional[datetime] = None,
        auto_confirm: bool = False
    ) -> Dict[str, Any]:
        """Create an order from a shopping list"""
        
        logger.info(f"Creating order for user {user_id}, list {shopping_list_id}")
        
        session = get_session()
        
        try:
            # Get shopping list
            shopping_list = session.query(ShoppingList).filter(
                ShoppingList.id == shopping_list_id,
                ShoppingList.user_id == user_id
            ).first()
            
            if not shopping_list:
                return {"error": "Shopping list not found"}
            
            # Get user
            user = get_user(user_id, session)
            if not user:
                return {"error": "User not found"}
            
            # Parse shopping list items
            items_data = json.loads(shopping_list.items_data)
            
            # Check service availability
            if delivery_service not in self.supported_services:
                return {"error": f"Delivery service {delivery_service} not supported"}
            
            service_info = self.supported_services[delivery_service]
            
            # Calculate order totals
            subtotal = sum(
                item.get("estimated_cost", 0) * item.get("quantity", 1)
                for item in items_data
            )
            
            delivery_fee = service_info["delivery_fee"]
            tax = subtotal * 0.08  # 8% tax estimate
            total = subtotal + delivery_fee + tax
            
            # Check minimum order
            if subtotal < service_info["min_order"]:
                return {
                    "error": f"Order below minimum ${service_info['min_order']} for {service_info['name']}",
                    "current_subtotal": subtotal,
                    "need_to_add": service_info["min_order"] - subtotal
                }
            
            # Set delivery date if not provided
            if not delivery_date:
                delivery_date = datetime.now() + timedelta(days=1)
            
            # In demo mode, simulate the order process
            if self.demo_mode:
                return await self._simulate_order_creation(
                    user, shopping_list, items_data, service_info, 
                    subtotal, delivery_fee, tax, total, delivery_date, auto_confirm, session
                )
            else:
                # Real implementation would integrate with actual APIs
                return await self._create_real_order(
                    user, shopping_list, delivery_service, items_data, 
                    total, delivery_date, session
                )
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating order: {e}")
            return {"error": "Failed to create order", "details": str(e)}
        finally:
            session.close()
    
    async def _simulate_order_creation(
        self,
        user,
        shopping_list,
        items_data,
        service_info,
        subtotal,
        delivery_fee,
        tax,
        total,
        delivery_date,
        auto_confirm,
        session
    ) -> Dict[str, Any]:
        """Simulate order creation for demo purposes"""
        
        # Create order record
        order = Order(
            user_id=user.id,
            shopping_list_id=shopping_list.id,
            order_number=f"DEMO-{datetime.now().strftime('%Y%m%d')}-{user.id}",
            store_name=service_info["name"],
            order_type="delivery",
            items_data=json.dumps(items_data),
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            tax=tax,
            total_amount=total,
            delivery_date=delivery_date,
            payment_status="pending" if not auto_confirm else "completed",
            order_status="placed" if auto_confirm else "pending_confirmation",
            auto_ordered=True
        )
        
        session.add(order)
        session.commit()
        
        # Update shopping list status
        shopping_list.status = "ordered"
        session.commit()
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "status": "demo_order_created",
            "service": service_info["name"],
            "order_summary": {
                "subtotal": subtotal,
                "delivery_fee": delivery_fee,
                "tax": round(tax, 2),
                "total": round(total, 2),
                "item_count": len(items_data)
            },
            "delivery_info": {
                "delivery_date": delivery_date.isoformat(),
                "estimated_time": "2-4 hours",
                "delivery_address": "User's registered address"
            },
            "next_steps": [
                "Order confirmation sent to email" if auto_confirm else "Please confirm order to proceed",
                "Track order status in your dashboard",
                "Prepare for delivery"
            ],
            "note": "This is a demo order - no real purchase was made"
        }
    
    async def _create_real_order(
        self,
        user,
        shopping_list,
        delivery_service,
        items_data,
        total,
        delivery_date,
        session
    ) -> Dict[str, Any]:
        """Create real order via API (placeholder for actual implementation)"""
        
        # This would integrate with real APIs like:
        # - Instacart Partner API
        # - Walmart Grocery API
        # - Amazon Fresh API
        
        return {
            "error": "Real API integration not implemented yet",
            "message": "This would connect to actual grocery delivery services"
        }
    
    async def track_order(self, user_id: int, order_id: int) -> Dict[str, Any]:
        """Track order status"""
        
        session = get_session()
        
        try:
            order = session.query(Order).filter(
                Order.id == order_id,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {"error": "Order not found"}
            
            # In demo mode, simulate order progress
            if self.demo_mode:
                return self._simulate_order_tracking(order)
            else:
                return await self._track_real_order(order)
            
        finally:
            session.close()
    
    def _simulate_order_tracking(self, order) -> Dict[str, Any]:
        """Simulate order tracking for demo"""
        
        # Simulate order progression based on time since order
        time_since_order = datetime.now() - order.placed_at
        hours_elapsed = time_since_order.total_seconds() / 3600
        
        if hours_elapsed < 1:
            status = "confirmed"
            message = "Order confirmed and being prepared"
        elif hours_elapsed < 2:
            status = "preparing"
            message = "Items are being picked and packed"
        elif hours_elapsed < 3:
            status = "out_for_delivery"
            message = "Order is out for delivery"
        else:
            status = "delivered"
            message = "Order has been delivered"
        
        return {
            "order_number": order.order_number,
            "current_status": status,
            "status_message": message,
            "estimated_delivery": order.delivery_date.isoformat() if order.delivery_date else None,
            "items_count": len(json.loads(order.items_data)),
            "total_amount": order.total_amount,
            "tracking_updates": [
                {"time": "1 hour ago", "status": "confirmed", "message": "Order confirmed"},
                {"time": "30 min ago", "status": "preparing", "message": "Items being picked"},
                {"time": "10 min ago", "status": status, "message": message}
            ],
            "demo_note": "This is simulated tracking data"
        }
    
    async def _track_real_order(self, order) -> Dict[str, Any]:
        """Track real order via API (placeholder)"""
        
        return {
            "error": "Real order tracking not implemented yet",
            "message": "This would connect to actual delivery service APIs"
        }
    
    async def cancel_order(self, user_id: int, order_id: int, reason: str = "") -> Dict[str, Any]:
        """Cancel an order"""
        
        session = get_session()
        
        try:
            order = session.query(Order).filter(
                Order.id == order_id,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {"error": "Order not found"}
            
            # Check if order can be cancelled
            if order.order_status in ["delivered", "cancelled"]:
                return {"error": f"Cannot cancel order with status: {order.order_status}"}
            
            # Update order status
            order.order_status = "cancelled"
            order.updated_at = datetime.now()
            
            session.commit()
            
            return {
                "order_number": order.order_number,
                "status": "cancelled",
                "cancellation_reason": reason,
                "refund_amount": order.total_amount,
                "cancelled_at": datetime.now().isoformat(),
                "message": "Order successfully cancelled. Refund will be processed within 3-5 business days."
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error cancelling order: {e}")
            return {"error": "Failed to cancel order", "details": str(e)}
        finally:
            session.close()
    
    async def schedule_recurring_order(
        self,
        user_id: int,
        shopping_list_id: int,
        frequency: str = "weekly",
        delivery_service: str = "instacart"
    ) -> Dict[str, Any]:
        """Schedule recurring automated orders"""
        
        session = get_session()
        
        try:
            # Get shopping list
            shopping_list = session.query(ShoppingList).filter(
                ShoppingList.id == shopping_list_id,
                ShoppingList.user_id == user_id
            ).first()
            
            if not shopping_list:
                return {"error": "Shopping list not found"}
            
            # For demo purposes, create automation rule
            from src.data.models import AutomationRule
            
            rule = AutomationRule(
                user_id=user_id,
                rule_name=f"Recurring Order - {frequency}",
                rule_type="automated_ordering",
                description=f"Automatically order from shopping list {shopping_list_id} {frequency}",
                trigger_conditions=json.dumps({
                    "frequency": frequency,
                    "shopping_list_id": shopping_list_id,
                    "delivery_service": delivery_service
                }),
                actions=json.dumps({
                    "action": "create_order",
                    "shopping_list_id": shopping_list_id,
                    "delivery_service": delivery_service,
                    "auto_confirm": True
                }),
                is_active=True,
                priority=5
            )
            
            session.add(rule)
            session.commit()
            
            return {
                "automation_rule_id": rule.id,
                "frequency": frequency,
                "shopping_list_id": shopping_list_id,
                "delivery_service": delivery_service,
                "status": "scheduled",
                "next_order_estimate": self._calculate_next_order_date(frequency).isoformat(),
                "message": f"Recurring {frequency} orders scheduled successfully",
                "note": "This is a demo automation - no real recurring charges will occur"
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error scheduling recurring order: {e}")
            return {"error": "Failed to schedule recurring order", "details": str(e)}
        finally:
            session.close()
    
    def _calculate_next_order_date(self, frequency: str) -> datetime:
        """Calculate next order date based on frequency"""
        
        now = datetime.now()
        
        if frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "biweekly":
            return now + timedelta(weeks=2)
        elif frequency == "monthly":
            return now + timedelta(days=30)
        else:
            return now + timedelta(weeks=1)  # Default to weekly
    
    async def get_order_history(self, user_id: int, limit: int = 10) -> Dict[str, Any]:
        """Get user's order history"""
        
        session = get_session()
        
        try:
            orders = session.query(Order)\
                .filter(Order.user_id == user_id)\
                .order_by(Order.placed_at.desc())\
                .limit(limit)\
                .all()
            
            if not orders:
                return {
                    "message": "No order history found",
                    "suggestion": "Create your first order from a shopping list"
                }
            
            order_history = []
            total_spent = 0
            
            for order in orders:
                order_data = {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "store": order.store_name,
                    "total": order.total_amount,
                    "status": order.order_status,
                    "order_date": order.placed_at.isoformat(),
                    "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                    "item_count": len(json.loads(order.items_data))
                }
                order_history.append(order_data)
                total_spent += order.total_amount
            
            return {
                "order_history": order_history,
                "total_orders": len(orders),
                "total_spent": round(total_spent, 2),
                "average_order": round(total_spent / len(orders), 2) if orders else 0,
                "period": "All time"
            }
            
        finally:
            session.close()
    
    async def estimate_delivery_cost(
        self,
        shopping_list_id: int,
        delivery_service: str = "instacart"
    ) -> Dict[str, Any]:
        """Estimate delivery cost for a shopping list"""
        
        if delivery_service not in self.supported_services:
            return {"error": f"Delivery service {delivery_service} not supported"}
        
        service_info = self.supported_services[delivery_service]
        
        session = get_session()
        
        try:
            shopping_list = session.query(ShoppingList).filter(
                ShoppingList.id == shopping_list_id
            ).first()
            
            if not shopping_list:
                return {"error": "Shopping list not found"}
            
            subtotal = shopping_list.estimated_total or 0
            delivery_fee = service_info["delivery_fee"]
            tax = subtotal * 0.08
            total = subtotal + delivery_fee + tax
            
            return {
                "service": service_info["name"],
                "cost_breakdown": {
                    "subtotal": subtotal,
                    "delivery_fee": delivery_fee,
                    "tax": round(tax, 2),
                    "total": round(total, 2)
                },
                "meets_minimum": subtotal >= service_info["min_order"],
                "minimum_order": service_info["min_order"],
                "estimated_delivery_time": "2-4 hours"
            }
            
        finally:
            session.close()

# Global order service instance
order_service = OrderManagementService()