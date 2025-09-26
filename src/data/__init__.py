"""
Grocery AI Data Layer

Database models and data access utilities.
"""

from .models import (
    # Models
    User, InventoryItem, Recipe, MealPlan, ShoppingList, 
    PriceData, Order, AutomationRule, NotificationLog, Analytics,
    
    # Database functions
    get_engine, get_session, init_db, reset_db, seed_db,
    
    # Utility functions
    get_user, get_user_inventory, get_price_comparison, update_inventory_item
)

__all__ = [
    # Models
    'User', 'InventoryItem', 'Recipe', 'MealPlan', 'ShoppingList',
    'PriceData', 'Order', 'AutomationRule', 'NotificationLog', 'Analytics',
    
    # Database functions  
    'get_engine', 'get_session', 'init_db', 'reset_db', 'seed_db',
    
    # Utility functions
    'get_user', 'get_user_inventory', 'get_price_comparison', 'update_inventory_item'
]

__version__ = "1.0.0"