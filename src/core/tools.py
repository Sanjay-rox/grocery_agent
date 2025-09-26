import json
import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
import logging
from src.core.config import Config

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for agent tools and functions"""
    
    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self.register_default_tools()
    
    def register_tool(
        self, 
        name: str, 
        function: Callable,
        description: str,
        parameters: Dict[str, Any] = None,
        category: str = "general"
    ):
        """Register a new tool"""
        self.tools[name] = {
            "function": function,
            "description": description,
            "parameters": parameters or {},
            "category": category,
            "registered_at": datetime.now().isoformat()
        }
        logger.info(f"✅ Tool registered: {name}")
    
    def get_tool(self, name: str) -> Optional[Dict]:
        """Get tool by name"""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: str) -> Dict[str, Dict]:
        """Get all tools in a category"""
        return {
            name: tool for name, tool in self.tools.items()
            if tool.get("category") == category
        }
    
    def get_all_tools(self) -> Dict[str, Dict]:
        """Get all registered tools"""
        return self.tools.copy()
    
    async def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool by name"""
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")
        
        tool = self.tools[name]
        function = tool["function"]
        
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(function):
                result = await function(**kwargs)
            else:
                result = function(**kwargs)
            
            logger.info(f"✅ Tool executed successfully: {name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {name} - {e}")
            raise e
    
    def generate_tools_schema(self) -> List[Dict]:
        """Generate OpenAI-style function calling schema"""
        schema = []
        
        for name, tool in self.tools.items():
            tool_schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            schema.append(tool_schema)
        
        return schema
    
    def register_default_tools(self):
        """Register default tools for the grocery agent"""
        
        # Inventory management tools
        self.register_tool(
            "check_inventory",
            self._check_inventory,
            "Check current inventory levels for specific items",
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of items to check"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "User ID to check inventory for"
                    }
                },
                "required": ["user_id"]
            },
            "inventory"
        )
        
        # Price comparison tools
        self.register_tool(
            "compare_prices",
            self._compare_prices,
            "Compare prices of items across different stores",
            {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of items to compare prices for"
                    },
                    "stores": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stores to compare (optional)"
                    }
                },
                "required": ["items"]
            },
            "shopping"
        )
        
        # Recipe and meal planning tools
        self.register_tool(
            "find_recipes",
            self._find_recipes,
            "Find recipes based on ingredients, dietary preferences, or cuisine type",
            {
                "type": "object",
                "properties": {
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Available ingredients"
                    },
                    "dietary_restrictions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Dietary restrictions (vegetarian, vegan, gluten-free, etc.)"
                    },
                    "cuisine_type": {
                        "type": "string",
                        "description": "Cuisine type (italian, indian, mexican, etc.)"
                    },
                    "max_cook_time": {
                        "type": "integer",
                        "description": "Maximum cooking time in minutes"
                    }
                }
            },
            "meal_planning"
        )
        
        # Nutrition analysis tools
        self.register_tool(
            "analyze_nutrition",
            self._analyze_nutrition,
            "Analyze nutritional information for recipes or ingredients",
            {
                "type": "object",
                "properties": {
                    "recipe_name": {
                        "type": "string",
                        "description": "Name of the recipe to analyze"
                    },
                    "ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ingredients with quantities"
                    },
                    "servings": {
                        "type": "integer",
                        "description": "Number of servings",
                        "default": 4
                    }
                }
            },
            "nutrition"
        )
        
        # Shopping list tools
        self.register_tool(
            "create_shopping_list",
            self._create_shopping_list,
            "Create optimized shopping list based on meal plan and current inventory",
            {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "User ID"
                    },
                    "meal_plan": {
                        "type": "object",
                        "description": "Weekly meal plan data"
                    },
                    "budget_limit": {
                        "type": "number",
                        "description": "Budget limit for shopping"
                    }
                },
                "required": ["user_id", "meal_plan"]
            },
            "shopping"
        )
        
        # Notification tools
        self.register_tool(
            "send_notification",
            self._send_notification,
            "Send notification to user via available channels",
            {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Notification message"
                    },
                    "notification_type": {
                        "type": "string",
                        "enum": ["info", "warning", "success", "error"],
                        "description": "Type of notification"
                    },
                    "channels": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["email", "discord", "console"]
                        },
                        "description": "Notification channels to use"
                    }
                },
                "required": ["message"]
            },
            "notifications"
        )
        
        # Price comparison tools
        self.register_tool(
            "compare_product_prices",
            self._compare_product_prices,
            "Compare prices of products across different stores with live price data",
            {
                "type": "object",
                "properties": {
                    "product_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of product names to compare prices for"
                    },
                    "stores": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stores to compare (walmart, target, kroger)"
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Force refresh price data from web scraping",
                        "default": False
                    }
                },
                "required": ["product_names"]
            },
            "price_comparison"
        )
        
        self.register_tool(
            "find_best_deals",
            self._find_best_deals,
            "Find products with the biggest savings opportunities",
            {
                "type": "object",
                "properties": {
                    "product_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of product names to find deals for"
                    },
                    "min_savings": {
                        "type": "number",
                        "description": "Minimum savings amount to consider (default: $1.00)",
                        "default": 1.0
                    }
                },
                "required": ["product_names"]
            },
            "price_comparison"
        )
        
        self.register_tool(
            "optimize_shopping_list",
            self._optimize_shopping_list,
            "Optimize shopping list to find best store and total cost",
            {
                "type": "object",
                "properties": {
                    "shopping_list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item": {"type": "string"},
                                "quantity": {"type": "number"}
                            }
                        },
                        "description": "Shopping list with items and quantities"
                    }
                },
                "required": ["shopping_list"]
            },
            "price_comparison"
        )

    # Tool implementation methods
    
    async def _check_inventory(self, user_id: int, items: List[str] = None) -> Dict[str, Any]:
        """Check inventory levels"""
        try:
            from src.data.models import get_session, InventoryItem
            
            session = get_session()
            query = session.query(InventoryItem).filter(InventoryItem.user_id == user_id)
            
            if items:
                query = query.filter(InventoryItem.item_name.in_(items))
            
            inventory_items = query.all()
            
            result = {
                "user_id": user_id,
                "checked_at": datetime.now().isoformat(),
                "inventory": []
            }
            
            for item in inventory_items:
                item_data = {
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                    "days_until_expiry": (item.expiry_date - datetime.now()).days if item.expiry_date else None,
                    "low_stock": item.quantity < 2  # Simple low stock threshold
                }
                result["inventory"].append(item_data)
            
            session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error checking inventory: {e}")
            return {"error": str(e)}
    
    async def _compare_prices(self, items: List[str], stores: List[str] = None) -> Dict[str, Any]:
        """Compare prices across stores"""
        try:
            from src.data.models import get_session, PriceData
            
            session = get_session()
            query = session.query(PriceData).filter(PriceData.product_name.in_(items))
            
            if stores:
                query = query.filter(PriceData.store_name.in_(stores))
            
            price_data = query.all()
            
            result = {
                "compared_at": datetime.now().isoformat(),
                "items": {}
            }
            
            for item in items:
                item_prices = [p for p in price_data if p.product_name == item]
                
                if item_prices:
                    prices_by_store = {}
                    for price_entry in item_prices:
                        prices_by_store[price_entry.store_name] = {
                            "price": price_entry.price,
                            "unit": price_entry.unit,
                            "available": price_entry.availability,
                            "last_updated": price_entry.scraped_at.isoformat()
                        }
                    
                    # Find best price
                    available_prices = {k: v for k, v in prices_by_store.items() if v["available"]}
                    best_price = min(available_prices.values(), key=lambda x: x["price"]) if available_prices else None
                    best_store = next((k for k, v in available_prices.items() if v == best_price), None) if best_price else None
                    
                    result["items"][item] = {
                        "prices_by_store": prices_by_store,
                        "best_price": best_price["price"] if best_price else None,
                        "best_store": best_store,
                        "average_price": sum(p["price"] for p in available_prices.values()) / len(available_prices) if available_prices else None
                    }
                else:
                    result["items"][item] = {
                        "prices_by_store": {},
                        "best_price": None,
                        "best_store": None,
                        "average_price": None,
                        "note": "No price data available"
                    }
            
            session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error comparing prices: {e}")
            return {"error": str(e)}
    
    async def _find_recipes(
        self, 
        ingredients: List[str] = None, 
        dietary_restrictions: List[str] = None,
        cuisine_type: str = None,
        max_cook_time: int = None
    ) -> Dict[str, Any]:
        """Find recipes based on criteria"""
        try:
            # This would typically call Spoonacular API or local recipe database
            # For now, return mock data structure
            
            mock_recipes = [
                {
                    "id": 1,
                    "title": "Vegetarian Pasta",
                    "readyInMinutes": 30,
                    "servings": 4,
                    "ingredients_needed": ["pasta", "tomatoes", "basil", "olive oil"],
                    "missing_ingredients": [],
                    "cuisines": ["italian"],
                    "diets": ["vegetarian"],
                    "summary": "A delicious and easy vegetarian pasta dish",
                    "instructions": ["Boil pasta", "Make sauce", "Combine and serve"]
                },
                {
                    "id": 2,
                    "title": "Chicken Stir Fry",
                    "readyInMinutes": 25,
                    "servings": 3,
                    "ingredients_needed": ["chicken", "vegetables", "soy sauce", "rice"],
                    "missing_ingredients": [],
                    "cuisines": ["asian"],
                    "diets": [],
                    "summary": "Quick and healthy chicken stir fry",
                    "instructions": ["Cook chicken", "Add vegetables", "Serve with rice"]
                }
            ]
            
            # Filter recipes based on criteria
            filtered_recipes = mock_recipes
            
            if dietary_restrictions:
                filtered_recipes = [
                    recipe for recipe in filtered_recipes
                    if any(diet in recipe["diets"] for diet in dietary_restrictions)
                ]
            
            if cuisine_type:
                filtered_recipes = [
                    recipe for recipe in filtered_recipes
                    if cuisine_type.lower() in [c.lower() for c in recipe["cuisines"]]
                ]
            
            if max_cook_time:
                filtered_recipes = [
                    recipe for recipe in filtered_recipes
                    if recipe["readyInMinutes"] <= max_cook_time
                ]
            
            # If ingredients provided, calculate missing ingredients
            if ingredients:
                for recipe in filtered_recipes:
                    recipe["missing_ingredients"] = [
                        ing for ing in recipe["ingredients_needed"]
                        if not any(available.lower() in ing.lower() for available in ingredients)
                    ]
            
            return {
                "search_criteria": {
                    "ingredients": ingredients,
                    "dietary_restrictions": dietary_restrictions,
                    "cuisine_type": cuisine_type,
                    "max_cook_time": max_cook_time
                },
                "found_recipes": len(filtered_recipes),
                "recipes": filtered_recipes
            }
            
        except Exception as e:
            logger.error(f"Error finding recipes: {e}")
            return {"error": str(e)}
    
    async def _analyze_nutrition(
        self, 
        recipe_name: str = None,
        ingredients: List[str] = None,
        servings: int = 4
    ) -> Dict[str, Any]:
        """Analyze nutritional information"""
        try:
            # Mock nutritional analysis - in real implementation, 
            # this would use USDA API or Spoonacular nutrition endpoint
            
            mock_nutrition = {
                "recipe_name": recipe_name,
                "servings": servings,
                "per_serving": {
                    "calories": 320,
                    "protein": 15.2,
                    "carbohydrates": 45.8,
                    "fat": 8.6,
                    "fiber": 6.2,
                    "sugar": 12.4,
                    "sodium": 480
                },
                "total_recipe": {
                    "calories": 320 * servings,
                    "protein": 15.2 * servings,
                    "carbohydrates": 45.8 * servings,
                    "fat": 8.6 * servings,
                    "fiber": 6.2 * servings,
                    "sugar": 12.4 * servings,
                    "sodium": 480 * servings
                },
                "health_score": 85,
                "diet_labels": ["vegetarian"],
                "allergens": ["gluten"],
                "vitamins_minerals": {
                    "vitamin_c": 25,
                    "iron": 12,
                    "calcium": 8
                }
            }
            
            return mock_nutrition
            
        except Exception as e:
            logger.error(f"Error analyzing nutrition: {e}")
            return {"error": str(e)}
    
    async def _create_shopping_list(
        self,
        user_id: int,
        meal_plan: Dict[str, Any],
        budget_limit: float = None
    ) -> Dict[str, Any]:
        """Create optimized shopping list"""
        try:
            # Get current inventory
            inventory_result = await self._check_inventory(user_id)
            current_inventory = {item["name"]: item["quantity"] for item in inventory_result.get("inventory", [])}
            
            # Extract ingredients from meal plan
            needed_ingredients = []
            
            # Mock ingredient extraction (in real implementation, parse recipes)
            for day, meals in meal_plan.items():
                for meal_type, recipe in meals.items():
                    # Add mock ingredients
                    mock_ingredients = ["tomatoes", "pasta", "chicken", "vegetables", "rice"]
                    needed_ingredients.extend(mock_ingredients)
            
            # Remove duplicates and check against inventory
            unique_ingredients = list(set(needed_ingredients))
            shopping_list = []
            
            for ingredient in unique_ingredients:
                current_stock = current_inventory.get(ingredient, 0)
                needed_quantity = 2  # Mock needed quantity
                
                if current_stock < needed_quantity:
                    to_buy = needed_quantity - current_stock
                    shopping_list.append({
                        "item": ingredient,
                        "quantity": to_buy,
                        "unit": "units",
                        "estimated_price": 3.99,  # Mock price
                        "priority": "medium",
                        "category": "produce"  # Mock category
                    })
            
            # Calculate total cost
            total_cost = sum(item["estimated_price"] * item["quantity"] for item in shopping_list)
            
            # Check budget constraint
            within_budget = budget_limit is None or total_cost <= budget_limit
            
            return {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "shopping_list": shopping_list,
                "total_items": len(shopping_list),
                "estimated_total_cost": total_cost,
                "budget_limit": budget_limit,
                "within_budget": within_budget,
                "savings_opportunities": []  # Could include coupons, bulk discounts, etc.
            }
            
        except Exception as e:
            logger.error(f"Error creating shopping list: {e}")
            return {"error": str(e)}
    
    async def _send_notification(
        self,
        message: str,
        notification_type: str = "info",
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """Send notification via specified channels"""
        try:
            channels = channels or ["console"]
            results = {}
            
            for channel in channels:
                if channel == "console":
                    print(f"[{notification_type.upper()}] {message}")
                    results[channel] = "sent"
                elif channel == "discord" and Config.DISCORD_WEBHOOK_URL:
                    # Mock Discord webhook (implement with requests)
                    results[channel] = "sent"
                elif channel == "email" and Config.NOTIFICATION_EMAIL:
                    # Mock email sending (implement with smtplib or email service)
                    results[channel] = "sent"
                else:
                    results[channel] = "not_configured"
            
            return {
                "message": message,
                "notification_type": notification_type,
                "channels_attempted": channels,
                "results": results,
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {"error": str(e)}
    
    async def _compare_product_prices(
        self, 
        product_names: List[str], 
        stores: List[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Compare prices across stores using live price data"""
        
        try:
            from src.services.price_service import price_service
            
            # Get price comparisons
            comparisons = await price_service.compare_prices(
                product_names, 
                stores, 
                force_refresh
            )
            
            if not comparisons:
                return {"error": "No price data available for the requested products"}
            
            # Format results for user
            result = {
                "comparison_date": datetime.now().isoformat(),
                "products_compared": len(comparisons),
                "comparisons": {}
            }
            
            total_savings = 0
            
            for product_name, comparison in comparisons.items():
                result["comparisons"][product_name] = {
                    "cheapest_price": comparison.cheapest_price,
                    "cheapest_store": comparison.cheapest_store,
                    "average_price": comparison.average_price,
                    "price_range": {
                        "min": comparison.price_range[0],
                        "max": comparison.price_range[1]
                    },
                    "savings_opportunity": comparison.savings_opportunity,
                    "stores_compared": comparison.stores_compared,
                    "confidence": comparison.confidence,
                    "store_prices": {
                        store: {
                            "price": data["price"],
                            "product_name": data["product_name"]
                        }
                        for store, data in comparison.price_by_store.items()
                    }
                }
                
                total_savings += comparison.savings_opportunity
            
            result["total_potential_savings"] = round(total_savings, 2)
            result["average_confidence"] = self._calculate_average_confidence(comparisons)
            
            return result
            
        except Exception as e:
            logger.error(f"Error comparing product prices: {e}")
            return {"error": str(e)}
    
    async def _find_best_deals(
        self, 
        product_names: List[str], 
        min_savings: float = 1.0
    ) -> Dict[str, Any]:
        """Find best deals with significant savings"""
        
        try:
            from src.services.price_service import price_service
            
            deals = await price_service.get_best_deals(product_names, min_savings)
            
            if not deals:
                return {
                    "message": f"No deals found with savings of ${min_savings} or more",
                    "suggestion": "Try lowering the minimum savings amount or checking different products"
                }
            
            return {
                "deals_found": len(deals),
                "total_potential_savings": sum(deal["savings"] for deal in deals),
                "min_savings_threshold": min_savings,
                "best_deals": deals,
                "summary": f"Found {len(deals)} deals with total savings of ${sum(deal['savings'] for deal in deals):.2f}"
            }
            
        except Exception as e:
            logger.error(f"Error finding best deals: {e}")
            return {"error": str(e)}
    
    async def _optimize_shopping_list(self, shopping_list: List[Dict]) -> Dict[str, Any]:
        """Optimize shopping list for best total cost"""
        
        try:
            from src.services.price_service import price_service
            
            optimization = await price_service.get_shopping_list_comparison(shopping_list)
            
            if not optimization["best_store"]:
                return {
                    "error": "Could not find price data for shopping list items",
                    "coverage": optimization["coverage"],
                    "items_found": optimization["items_compared"]
                }
            
            # Calculate savings vs shopping at average prices
            store_totals = optimization["store_comparisons"]
            if len(store_totals) > 1:
                worst_total = max(data["total"] for data in store_totals.values())
                savings_vs_worst = worst_total - optimization["best_total"]
            else:
                savings_vs_worst = 0
            
            return {
                "optimization_summary": {
                    "best_store": optimization["best_store"],
                    "best_total": optimization["best_total"],
                    "savings_vs_worst_option": round(savings_vs_worst, 2),
                    "coverage": f"{optimization['coverage']}%"
                },
                "store_comparison": optimization["store_comparisons"],
                "recommendations": [
                    f"Shop at {optimization['best_store']} for the lowest total cost",
                    f"You'll save ${savings_vs_worst:.2f} compared to the most expensive option",
                    f"Price data available for {optimization['items_compared']} of {optimization['total_items']} items"
                ],
                "potential_additional_savings": optimization["potential_savings"]
            }
            
        except Exception as e:
            logger.error(f"Error optimizing shopping list: {e}")
            return {"error": str(e)}
    
    def _calculate_average_confidence(self, comparisons: Dict) -> str:
        """Calculate average confidence across comparisons"""
        confidence_values = {"high": 1.0, "medium": 0.6, "low": 0.3}
        
        if not comparisons:
            return "low"
        
        total_confidence = sum(
            confidence_values.get(comp.confidence, 0.3) 
            for comp in comparisons.values()
        )
        
        avg_confidence = total_confidence / len(comparisons)
        
        if avg_confidence >= 0.8:
            return "high"
        elif avg_confidence >= 0.5:
            return "medium"
        else:
            return "low"

    async def _save_user_preference(
        self,
        user_id: int,
        preference_key: str,
        preference_value: Any
    ) -> Dict[str, Any]:
        """Save user preference"""
        try:
            from src.core.memory import ConversationMemory
            
            memory = ConversationMemory(user_id)
            memory.update_preference(preference_key, preference_value)
            
            return {
                "user_id": user_id,
                "preference_key": preference_key,
                "preference_value": preference_value,
                "saved_at": datetime.now().isoformat(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error saving user preference: {e}")
            return {"error": str(e)}

# Global tool registry instance
tool_registry = ToolRegistry()