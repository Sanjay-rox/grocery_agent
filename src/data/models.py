from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
import json
from src.core.config import Config

Base = declarative_base()

class User(Base):
    """User profile and preferences"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Household information
    household_size = Column(Integer, default=2)
    household_composition = Column(Text, nullable=True)  # JSON: {"adults": 2, "children": 1}
    
    # Dietary preferences and restrictions
    dietary_preferences = Column(Text, nullable=True)  # JSON string
    allergies = Column(Text, nullable=True)  # JSON array
    health_goals = Column(Text, nullable=True)  # JSON array
    
    # Budget and shopping preferences
    budget_limit = Column(Float, default=150.0)
    preferred_stores = Column(Text, nullable=True)  # JSON array
    shopping_frequency = Column(String(20), default="weekly")  # weekly, biweekly, monthly
    
    # Preferences
    favorite_cuisines = Column(Text, nullable=True)  # JSON array
    cooking_skill_level = Column(String(20), default="intermediate")  # beginner, intermediate, advanced
    preferred_meal_prep_time = Column(Integer, default=30)  # minutes
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    inventory_items = relationship("InventoryItem", back_populates="user")
    meal_plans = relationship("MealPlan", back_populates="user")
    shopping_lists = relationship("ShoppingList", back_populates="user")
    orders = relationship("Order", back_populates="user")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "household_size": self.household_size,
            "dietary_preferences": json.loads(self.dietary_preferences) if self.dietary_preferences else {},
            "budget_limit": self.budget_limit,
            "preferred_stores": json.loads(self.preferred_stores) if self.preferred_stores else [],
            "created_at": self.created_at.isoformat()
        }

class InventoryItem(Base):
    """Home inventory tracking"""
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Item information
    item_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)  # produce, dairy, meat, pantry, etc.
    brand = Column(String(100), nullable=True)
    
    # Quantity information
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)  # lbs, oz, pieces, liters, etc.
    
    # Date information
    purchase_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    
    # Usage tracking
    estimated_consumption_rate = Column(Float, nullable=True)  # units per day
    last_used_date = Column(DateTime, nullable=True)
    
    # Cost tracking
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    store_purchased_from = Column(String(100), nullable=True)
    
    # Status
    is_running_low = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="inventory_items")
    
    def to_dict(self):
        return {
            "id": self.id,
            "item_name": self.item_name,
            "category": self.category,
            "quantity": self.quantity,
            "unit": self.unit,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "is_running_low": self.is_running_low,
            "is_expired": self.is_expired
        }
    
    @property
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - datetime.now()).days
        return None

class Recipe(Base):
    """Recipe database"""
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True)
    
    # Basic recipe information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cuisine_type = Column(String(100), nullable=True)
    meal_type = Column(String(50), nullable=True)  # breakfast, lunch, dinner, snack
    
    # Cooking information
    prep_time = Column(Integer, nullable=True)  # minutes
    cook_time = Column(Integer, nullable=True)  # minutes
    total_time = Column(Integer, nullable=True)  # minutes
    servings = Column(Integer, default=4)
    difficulty_level = Column(String(20), default="medium")  # easy, medium, hard
    
    # Recipe data
    ingredients = Column(Text, nullable=False)  # JSON array
    instructions = Column(Text, nullable=False)  # JSON array
    
    # Nutritional information (per serving)
    calories = Column(Float, nullable=True)
    protein = Column(Float, nullable=True)  # grams
    carbs = Column(Float, nullable=True)  # grams
    fat = Column(Float, nullable=True)  # grams
    fiber = Column(Float, nullable=True)  # grams
    
    # Dietary labels
    dietary_labels = Column(Text, nullable=True)  # JSON array: vegetarian, vegan, gluten-free, etc.
    allergens = Column(Text, nullable=True)  # JSON array
    
    # Ratings and usage
    average_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)
    
    # External source information
    source_url = Column(String(500), nullable=True)
    source_api_id = Column(String(100), nullable=True)  # Spoonacular ID, etc.
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "cuisine_type": self.cuisine_type,
            "total_time": self.total_time,
            "servings": self.servings,
            "difficulty_level": self.difficulty_level,
            "ingredients": json.loads(self.ingredients) if self.ingredients else [],
            "instructions": json.loads(self.instructions) if self.instructions else [],
            "calories": self.calories,
            "dietary_labels": json.loads(self.dietary_labels) if self.dietary_labels else [],
            "average_rating": self.average_rating
        }

class MealPlan(Base):
    """Weekly meal planning"""
    __tablename__ = "meal_plans"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Planning period
    week_start_date = Column(DateTime, nullable=False)
    week_end_date = Column(DateTime, nullable=False)
    
    # Meal plan data
    meal_data = Column(Text, nullable=False)  # JSON: {"monday": {"breakfast": recipe_id, ...}, ...}
    
    # Generated shopping list
    shopping_list_data = Column(Text, nullable=True)  # JSON array of items
    
    # Nutritional summary
    total_calories = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    completion_status = Column(String(20), default="planned")  # planned, in_progress, completed
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="meal_plans")
    
    def to_dict(self):
        return {
            "id": self.id,
            "week_start_date": self.week_start_date.isoformat(),
            "week_end_date": self.week_end_date.isoformat(),
            "meal_data": json.loads(self.meal_data) if self.meal_data else {},
            "total_calories": self.total_calories,
            "total_cost": self.total_cost,
            "completion_status": self.completion_status
        }

class ShoppingList(Base):
    """Shopping list management"""
    __tablename__ = "shopping_lists"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    meal_plan_id = Column(Integer, ForeignKey("meal_plans.id"), nullable=True)
    
    # List information
    list_name = Column(String(255), default="Weekly Shopping")
    list_type = Column(String(50), default="meal_plan")  # meal_plan, restock, special_occasion
    
    # Items data
    items_data = Column(Text, nullable=False)  # JSON array of items with quantities, prices, etc.
    
    # Budget and cost
    budget_limit = Column(Float, nullable=True)
    estimated_total = Column(Float, nullable=True)
    actual_total = Column(Float, nullable=True)
    
    # Shopping information
    preferred_stores = Column(Text, nullable=True)  # JSON array
    shopping_date = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(20), default="draft")  # draft, ready, shopping, completed, cancelled
    completion_percentage = Column(Float, default=0.0)
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="shopping_lists")
    
    def to_dict(self):
        return {
            "id": self.id,
            "list_name": self.list_name,
            "items_data": json.loads(self.items_data) if self.items_data else [],
            "estimated_total": self.estimated_total,
            "status": self.status,
            "completion_percentage": self.completion_percentage,
            "created_at": self.created_at.isoformat()
        }

class PriceData(Base):
    """Price tracking across stores"""
    __tablename__ = "price_data"
    
    id = Column(Integer, primary_key=True)
    
    # Product information
    product_name = Column(String(255), nullable=False)
    product_category = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    product_size = Column(String(100), nullable=True)  # 1lb, 500ml, etc.
    
    # Store information
    store_name = Column(String(100), nullable=False)
    store_location = Column(String(255), nullable=True)
    
    # Price information
    price = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    price_per_unit = Column(Float, nullable=True)  # calculated price per standard unit
    
    # Availability
    availability = Column(Boolean, default=True)
    in_stock = Column(Boolean, default=True)
    
    # Discount information
    is_on_sale = Column(Boolean, default=False)
    original_price = Column(Float, nullable=True)
    discount_percentage = Column(Float, nullable=True)
    sale_end_date = Column(DateTime, nullable=True)
    
    # Data source
    data_source = Column(String(100), nullable=True)  # web_scraping, api, manual
    source_url = Column(String(500), nullable=True)
    
    # System fields
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "product_name": self.product_name,
            "store_name": self.store_name,
            "price": self.price,
            "unit": self.unit,
            "availability": self.availability,
            "is_on_sale": self.is_on_sale,
            "scraped_at": self.scraped_at.isoformat()
        }

class Order(Base):
    """Order tracking for automated purchases"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shopping_list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=True)
    
    # Order information
    order_number = Column(String(100), nullable=True)
    store_name = Column(String(100), nullable=False)
    order_type = Column(String(50), default="delivery")  # delivery, pickup, in_store
    
    # Items and pricing
    items_data = Column(Text, nullable=False)  # JSON array of ordered items
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, default=0.0)
    delivery_fee = Column(Float, default=0.0)
    tip = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    
    # Delivery information
    delivery_address = Column(Text, nullable=True)  # JSON with address details
    delivery_date = Column(DateTime, nullable=True)
    delivery_time_slot = Column(String(50), nullable=True)  # "10:00-12:00"
    
    # Payment information
    payment_method = Column(String(50), nullable=True)  # credit_card, paypal, etc.
    payment_status = Column(String(20), default="pending")  # pending, completed, failed, refunded
    
    # Order status
    order_status = Column(String(20), default="placed")  # placed, confirmed, preparing, delivered, cancelled
    tracking_number = Column(String(100), nullable=True)
    
    # Automation flags
    auto_ordered = Column(Boolean, default=False)
    recurring_order = Column(Boolean, default=False)
    
    # System fields
    placed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    
    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "store_name": self.store_name,
            "order_type": self.order_type,
            "total_amount": self.total_amount,
            "order_status": self.order_status,
            "auto_ordered": self.auto_ordered,
            "placed_at": self.placed_at.isoformat()
        }

class AutomationRule(Base):
    """Automation rules for the AI agent"""
    __tablename__ = "automation_rules"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Rule information
    rule_name = Column(String(255), nullable=False)
    rule_type = Column(String(50), nullable=False)  # restock, meal_plan, budget, health
    description = Column(Text, nullable=True)
    
    # Rule conditions (JSON)
    trigger_conditions = Column(Text, nullable=False)  # {"inventory_below": 2, "item": "milk"}
    
    # Rule actions (JSON)
    actions = Column(Text, nullable=False)  # {"action": "add_to_shopping_list", "quantity": 1}
    
    # Rule settings
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=5)  # 1-10, higher = more important
    
    # Execution tracking
    last_executed = Column(DateTime, nullable=True)
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "rule_type": self.rule_type,
            "trigger_conditions": json.loads(self.trigger_conditions) if self.trigger_conditions else {},
            "actions": json.loads(self.actions) if self.actions else {},
            "is_active": self.is_active,
            "priority": self.priority,
            "execution_count": self.execution_count
        }

class NotificationLog(Base):
    """Log of all notifications sent"""
    __tablename__ = "notification_log"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Notification details
    notification_type = Column(String(50), nullable=False)  # info, warning, success, error
    title = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    
    # Delivery information
    channels = Column(Text, nullable=True)  # JSON array: ["email", "discord"]
    delivery_status = Column(Text, nullable=True)  # JSON: {"email": "sent", "discord": "failed"}
    
    # Context
    related_entity_type = Column(String(50), nullable=True)  # order, meal_plan, inventory
    related_entity_id = Column(Integer, nullable=True)
    
    # System fields
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "channels": json.loads(self.channels) if self.channels else [],
            "created_at": self.created_at.isoformat()
        }

class Analytics(Base):
    """Analytics and insights tracking"""
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Analytics data
    metric_type = Column(String(100), nullable=False)  # spending, waste, nutrition, etc.
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50), nullable=True)
    
    # Time period
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Additional context
    category = Column(String(100), nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON with additional data
    
    # System fields
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "metric_type": self.metric_type,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat()
        }

# Database operations

def get_engine():
    """Get database engine"""
    return create_engine(Config.DATABASE_URL, echo=Config.DEBUG)

def get_session():
    """Get database session"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Initialize database with all tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database initialized successfully")
    return engine

def reset_db():
    """Reset database (drop and recreate all tables)"""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("✅ Database reset successfully")
    return engine

def seed_db():
    """Seed database with sample data"""
    session = get_session()
    
    try:
        # Create sample user
        sample_user = User(
            name="Sample User",
            email="sample@example.com",
            household_size=2,
            dietary_preferences='{"vegetarian": false, "gluten_free": false}',
            budget_limit=150.0,
            preferred_stores='["walmart", "target"]',
            favorite_cuisines='["italian", "mexican", "indian"]'
        )
        session.add(sample_user)
        session.commit()
        
        # Create sample inventory items
        sample_items = [
            InventoryItem(
                user_id=sample_user.id,
                item_name="Milk",
                category="dairy",
                quantity=0.5,
                unit="gallons",
                unit_cost=3.99,
                store_purchased_from="walmart",
                is_running_low=True
            ),
            InventoryItem(
                user_id=sample_user.id,
                item_name="Bread",
                category="bakery",
                quantity=1,
                unit="loaves",
                unit_cost=2.50,
                store_purchased_from="target"
            ),
            InventoryItem(
                user_id=sample_user.id,
                item_name="Eggs",
                category="dairy",
                quantity=6,
                unit="pieces",
                unit_cost=4.99,
                store_purchased_from="walmart"
            )
        ]
        
        for item in sample_items:
            session.add(item)
        
        # Create sample recipe
        sample_recipe = Recipe(
            title="Vegetarian Pasta",
            description="A delicious and easy vegetarian pasta dish",
            cuisine_type="italian",
            meal_type="dinner",
            prep_time=15,
            cook_time=20,
            total_time=35,
            servings=4,
            difficulty_level="easy",
            ingredients='["pasta", "tomatoes", "basil", "olive oil", "garlic", "parmesan cheese"]',
            instructions='["Boil pasta according to package directions", "Sauté garlic in olive oil", "Add tomatoes and cook until soft", "Toss with pasta and basil", "Serve with parmesan cheese"]',
            calories=350,
            protein=12,
            carbs=65,
            fat=8,
            dietary_labels='["vegetarian"]',
            average_rating=4.5,
            rating_count=12
        )
        session.add(sample_recipe)
        
        # Create sample price data
        sample_prices = [
            PriceData(
                product_name="Milk",
                product_category="dairy",
                store_name="walmart",
                price=3.99,
                unit="gallon",
                availability=True,
                data_source="web_scraping"
            ),
            PriceData(
                product_name="Milk",
                product_category="dairy",
                store_name="target",
                price=4.29,
                unit="gallon",
                availability=True,
                data_source="web_scraping"
            ),
            PriceData(
                product_name="Bread",
                product_category="bakery",
                store_name="walmart",
                price=2.50,
                unit="loaf",
                availability=True,
                is_on_sale=True,
                original_price=2.99,
                discount_percentage=16.4
            )
        ]
        
        for price in sample_prices:
            session.add(price)
        
        # Create sample automation rule
        sample_rule = AutomationRule(
            user_id=sample_user.id,
            rule_name="Auto Restock Milk",
            rule_type="restock",
            description="Automatically add milk to shopping list when running low",
            trigger_conditions='{"inventory_below": 0.25, "item": "milk", "unit": "gallons"}',
            actions='{"action": "add_to_shopping_list", "item": "milk", "quantity": 1, "unit": "gallon"}',
            is_active=True,
            priority=8
        )
        session.add(sample_rule)
        
        session.commit()
        print("✅ Database seeded with sample data")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
    finally:
        session.close()

# Utility functions for common database operations

def get_user(user_id: int, session=None):
    """Get user by ID"""
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        user = session.query(User).filter(User.id == user_id).first()
        return user
    finally:
        if should_close:
            session.close()

def get_user_inventory(user_id: int, low_stock_only=False, session=None):
    """Get user's inventory items"""
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        query = session.query(InventoryItem).filter(InventoryItem.user_id == user_id)
        if low_stock_only:
            query = query.filter(InventoryItem.is_running_low == True)
        
        items = query.all()
        return items
    finally:
        if should_close:
            session.close()

def get_price_comparison(product_name: str, limit=5, session=None):
    """Get price comparison for a product across stores"""
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        prices = session.query(PriceData)\
            .filter(PriceData.product_name.ilike(f"%{product_name}%"))\
            .filter(PriceData.availability == True)\
            .order_by(PriceData.price.asc())\
            .limit(limit)\
            .all()
        
        return prices
    finally:
        if should_close:
            session.close()

def update_inventory_item(user_id: int, item_name: str, quantity_change: float, session=None):
    """Update inventory item quantity"""
    if session is None:
        session = get_session()
        should_close = True
    else:
        should_close = False
    
    try:
        item = session.query(InventoryItem)\
            .filter(InventoryItem.user_id == user_id)\
            .filter(InventoryItem.item_name.ilike(f"%{item_name}%"))\
            .first()
        
        if item:
            item.quantity += quantity_change
            item.quantity = max(0, item.quantity)  # Don't go below 0
            item.is_running_low = item.quantity < 2  # Simple threshold
            item.updated_at = datetime.utcnow()
            
            if should_close:
                session.commit()
            
            return item
        else:
            return None
    
    except Exception as e:
        if should_close:
            session.rollback()
        raise e
    finally:
        if should_close:
            session.close()

# Initialize database on import
if __name__ == "__main__":
    init_db()
    seed_db()