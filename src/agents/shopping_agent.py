import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

from src.core.llm_client import llm_client
from src.core.memory import ConversationMemory
from src.core.tools import tool_registry
from src.data.models import (
    get_session, User, ShoppingList, MealPlan, InventoryItem, 
    get_user, get_user_inventory
)
from src.services.price_service import price_service
from src.core.config import Config

logger = logging.getLogger(__name__)

class ShoppingAgent:
    """Agent responsible for shopping list management and optimization"""
    
    def __init__(self):
        self.name = "Shopping Agent"
        self.description = "I handle shopping list creation, optimization, and smart purchasing decisions"
        self.capabilities = [
            "shopping_list_generation",
            "price_optimization", 
            "store_route_planning",
            "deal_finding",
            "substitution_suggestions",
            "automated_reordering"
        ]
        
        # Loop prevention
        self.active_operations = set()
        self.operation_timeout = 60  # seconds
    
    async def process_request(self, user_id: int, request: str, context: Dict = None) -> Dict[str, Any]:
        """Process user request related to shopping"""
        
        # Initialize context if None
        if context is None:
            context = {}
        
        operation_id = f"shopping_{user_id}_{datetime.now().timestamp()}"
        
        # Check if similar operation is already running
        if any(op.startswith(f"shopping_{user_id}") for op in self.active_operations):
            logger.warning(f"Shopping operation already in progress for user {user_id}")
            return {
                "response": "I'm already working on a shopping request for you. Please wait a moment.",
                "type": "rate_limited"
            }
        
        self.active_operations.add(operation_id)
        
        try:
            memory = ConversationMemory(user_id)
            user_context = memory.generate_context_summary()
            
            # Determine the type of shopping request
            request_type = await self._classify_shopping_request(request)
            
            response = {}
            
            if request_type == "create_shopping_list":
                response = await self.create_smart_shopping_list(user_id, context)
            elif request_type == "optimize_existing_list":
                response = await self.optimize_shopping_list(user_id, context)
            elif request_type == "find_deals":
                response = await self.find_current_deals(user_id, context)
            elif request_type == "plan_shopping_route":
                response = await self.plan_shopping_route(user_id, context)
            elif request_type == "substitute_products":
                response = await self.suggest_substitutions(user_id, context)
            elif request_type == "track_spending":
                response = await self.track_spending_patterns(user_id, context)
            else:
                response = await self._handle_general_shopping_query(user_id, request, context)
            
            # Save conversation to memory
            memory.add_conversation(request, str(response), "shopping")
            
            return response
            
        except Exception as e:
            logger.error(f"Shopping agent error: {e}")
            return {
                "error": "I encountered an issue with shopping assistance. Please try again.",
                "details": str(e)
            }
        finally:
            # Always remove operation from active set
            self.active_operations.discard(operation_id)
    
    async def _classify_shopping_request(self, request: str) -> str:
        """Classify the type of shopping request"""
        
        classification_prompt = f"""
        Classify this user request into one of these categories:
        - create_shopping_list: Creating new shopping lists, generating lists from meal plans
        - optimize_existing_list: Optimizing existing lists for cost, route, or efficiency
        - find_deals: Finding deals, discounts, coupons, best prices
        - plan_shopping_route: Planning which stores to visit, route optimization
        - substitute_products: Finding product alternatives, cheaper options
        - track_spending: Analyzing spending patterns, budget tracking
        - general: Other shopping-related queries
        
        User request: "{request}"
        
        Respond with just the category name.
        """
        
        classification = await llm_client.get_completion(
            classification_prompt,
            "You are a classification assistant. Respond with only the category name."
        )
        
        return classification.strip().lower()
    
    async def create_smart_shopping_list(
        self, 
        user_id: int, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Create an intelligent shopping list based on meal plan and inventory"""
        
        logger.info(f"Creating smart shopping list for user {user_id}")
        
        # Initialize context if None
        if context is None:
            context = {}
        
        session = get_session()
        
        try:
            # Get user and their current meal plan
            user = get_user(user_id, session)
            if not user:
                return {"error": "User not found"}
            
            # Get active meal plan
            meal_plan = session.query(MealPlan)\
                .filter(MealPlan.user_id == user_id)\
                .filter(MealPlan.is_active == True)\
                .order_by(MealPlan.created_at.desc())\
                .first()
            
            # Get current inventory
            inventory = get_user_inventory(user_id, session)
            
            if not meal_plan:
                return await self._create_basic_shopping_list(user_id, inventory, context)
            
            # Extract needed ingredients from meal plan
            meal_data = json.loads(meal_plan.meal_data)
            shopping_list_data = json.loads(meal_plan.shopping_list_data) if meal_plan.shopping_list_data else []
            
            # Get current inventory levels
            current_stock = {}
            for item in inventory:
                current_stock[item.item_name.lower()] = {
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'running_low': item.is_running_low
                }
            
            # Create intelligent shopping list using AI
            shopping_prompt = f"""
            Create an intelligent shopping list based on the following information:
            
            User Profile:
            - Household size: {user.household_size}
            - Budget limit: ${user.budget_limit}
            - Preferred stores: {user.preferred_stores}
            
            Current Meal Plan Needs:
            {json.dumps(shopping_list_data, indent=2) if shopping_list_data else "No specific meal plan items"}
            
            Current Inventory:
            {json.dumps(current_stock, indent=2) if current_stock else "No current inventory"}
            
            Create a smart shopping list that:
            1. Prioritizes items needed for the meal plan
            2. Accounts for current inventory levels
            3. Includes household essentials that might be running low
            4. Suggests quantities based on household size
            5. Categorizes items for efficient shopping
            6. Stays within budget constraints
            """
            
            system_prompt = """
            You are a smart shopping assistant. Create practical, organized shopping lists.
            
            Respond with valid JSON in this format:
            {
                "shopping_list": [
                    {
                        "item": "product name",
                        "quantity": 2,
                        "unit": "pieces/lbs/etc",
                        "category": "produce/dairy/meat/pantry/etc",
                        "priority": "high/medium/low",
                        "estimated_cost": 3.99,
                        "reason": "needed for meal plan/running low/household essential"
                    }
                ],
                "list_summary": {
                    "total_items": 15,
                    "estimated_total_cost": 85.50,
                    "categories": ["produce", "dairy", "meat"],
                    "within_budget": true
                },
                "shopping_strategy": {
                    "recommended_stores": ["walmart", "target"],
                    "estimated_shopping_time": 45,
                    "best_shopping_day": "Tuesday or Wednesday for deals"
                },
                "notes": [
                    "Practical shopping tips and suggestions"
                ]
            }
            """
            
            ai_response = await llm_client.get_json_completion(
                shopping_prompt,
                system_prompt
            )
            
            if "error" in ai_response:
                return {"error": "Failed to generate shopping list", "details": ai_response}
            
            # LOOP PREVENTION: Limit price enhancement to prevent recursive calls
            price_comparisons = {}
            
            # Only get price data if explicitly requested and not already processing
            if context.get("include_price_data", False) and not context.get("skip_price_enhancement", False):
                try:
                    # Limit to 5 items max for price checking
                    items_for_pricing = [item["item"] for item in ai_response["shopping_list"]][:5]
                    logger.info(f"Getting price data for {len(items_for_pricing)} items")
                    
                    # Add flag to prevent recursive calls
                    price_context = {"skip_price_enhancement": True}
                    price_comparisons = await price_service.compare_prices(items_for_pricing, force_refresh=False)
                    
                    logger.info(f"Price data retrieved for {len(price_comparisons)} items")
                except Exception as e:
                    logger.warning(f"Price enhancement failed, continuing without: {e}")
                    price_comparisons = {}
            else:
                logger.info("Skipping price enhancement to prevent loops")
            
            # Enhance shopping list with price data if available
            enhanced_list = ai_response["shopping_list"]
            if price_comparisons:
                enhanced_list = await self._enhance_with_price_data(
                    ai_response["shopping_list"], 
                    price_comparisons
                )
            
            # Save shopping list to database
            shopping_list = ShoppingList(
                user_id=user_id,
                meal_plan_id=meal_plan.id,
                list_name=f"Smart List - {datetime.now().strftime('%Y-%m-%d')}",
                items_data=json.dumps(enhanced_list),
                estimated_total=ai_response["list_summary"]["estimated_total_cost"],
                budget_limit=user.budget_limit,
                preferred_stores=user.preferred_stores,
                status="ready"
            )
            
            session.add(shopping_list)
            session.commit()
            
            # Learn from this shopping list
            memory = ConversationMemory(user_id)
            memory.learn_pattern("shopping_preferences", {
                "total_cost": ai_response["list_summary"]["estimated_total_cost"],
                "item_count": ai_response["list_summary"]["total_items"],
                "categories": ai_response["list_summary"]["categories"]
            })
            
            result = ai_response.copy()
            result["shopping_list_id"] = shopping_list.id
            result["enhanced_with_prices"] = len(price_comparisons) > 0
            result["created_at"] = datetime.now().isoformat()
            
            session.close()
            logger.info(f"✅ Smart shopping list created for user {user_id}")
            return result
            
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error creating shopping list: {e}")
            return {"error": "Failed to create shopping list", "details": str(e)}
    
    async def _enhance_with_price_data(
        self, 
        shopping_list: List[Dict], 
        price_comparisons: Dict
    ) -> List[Dict]:
        """Enhance shopping list with real price data"""
        
        enhanced_list = []
        
        for item in shopping_list:
            item_name = item["item"]
            enhanced_item = item.copy()
            
            # Find matching price comparison
            matching_comparison = None
            for product, comparison in price_comparisons.items():
                if any(word in product.lower() for word in item_name.lower().split()):
                    matching_comparison = comparison
                    break
            
            if matching_comparison:
                enhanced_item.update({
                    "real_price_data": {
                        "cheapest_price": matching_comparison.cheapest_price,
                        "cheapest_store": matching_comparison.cheapest_store,
                        "average_price": matching_comparison.average_price,
                        "savings_opportunity": matching_comparison.savings_opportunity,
                        "confidence": matching_comparison.confidence
                    },
                    "estimated_cost": matching_comparison.cheapest_price * item.get("quantity", 1)
                })
            
            enhanced_list.append(enhanced_item)
        
        return enhanced_list
    
    async def _create_basic_shopping_list(
        self, 
        user_id: int, 
        inventory: List[InventoryItem], 
        context: Dict
    ) -> Dict[str, Any]:
        """Create basic shopping list when no meal plan exists"""
        
        # Get user preferences
        memory = ConversationMemory(user_id)
        
        basic_essentials = [
            {"item": "milk", "quantity": 1, "unit": "gallon", "category": "dairy", "priority": "high"},
            {"item": "bread", "quantity": 1, "unit": "loaf", "category": "bakery", "priority": "high"},
            {"item": "eggs", "quantity": 12, "unit": "pieces", "category": "dairy", "priority": "high"},
            {"item": "bananas", "quantity": 1, "unit": "bunch", "category": "produce", "priority": "medium"},
            {"item": "chicken breast", "quantity": 2, "unit": "lbs", "category": "meat", "priority": "medium"}
        ]
        
        # Filter out items user already has
        current_items = {item.item_name.lower() for item in inventory if item.quantity > 1}
        needed_items = [
            item for item in basic_essentials 
            if item["item"].lower() not in current_items
        ]
        
        return {
            "shopping_list": needed_items,
            "list_summary": {
                "total_items": len(needed_items),
                "estimated_total_cost": sum(3.99 for _ in needed_items),  # Mock pricing
                "categories": list(set(item["category"] for item in needed_items))
            },
            "message": "Created basic essentials list. Create a meal plan for more personalized shopping lists.",
            "suggestion": "Try asking: 'Create a meal plan for this week' for better shopping recommendations"
        }
    
    async def optimize_shopping_list(
        self, 
        user_id: int, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Optimize existing shopping list for cost and efficiency"""
        
        logger.info(f"Optimizing shopping list for user {user_id}")
        
        # Initialize context if None
        if context is None:
            context = {}
        
        session = get_session()
        
        try:
            # Get most recent shopping list
            shopping_list = session.query(ShoppingList)\
                .filter(ShoppingList.user_id == user_id)\
                .filter(ShoppingList.status.in_(["ready", "draft"]))\
                .order_by(ShoppingList.created_at.desc())\
                .first()
            
            if not shopping_list:
                session.close()
                return {"error": "No shopping list found to optimize. Create a shopping list first."}
            
            items_data = json.loads(shopping_list.items_data)
            
            # LOOP PREVENTION: Add context to prevent recursive calls
            context["skip_price_enhancement"] = True
            
            # Use the shopping list optimization tool with limited items
            optimization_items = [
                {"item": item["item"], "quantity": item.get("quantity", 1)} 
                for item in items_data[:10]  # Limit to 10 items
            ]
            
            optimization_result = await tool_registry.execute_tool(
                "optimize_shopping_list",
                shopping_list=optimization_items
            )
            
            if "error" in optimization_result:
                session.close()
                return optimization_result
            
            # Get additional optimization suggestions
            optimization_prompt = f"""
            Provide additional shopping optimization advice based on this data:
            
            Shopping List: {len(items_data)} items
            Optimization Results: {json.dumps(optimization_result, indent=2)}
            
            Provide specific, actionable advice for:
            1. Which items to prioritize for maximum savings
            2. Shopping timing recommendations
            3. Bulk buying opportunities
            4. Potential substitutions for expensive items
            5. Store-specific strategies
            """
            
            system_prompt = """
            You are a shopping optimization expert. Provide practical, money-saving advice.
            
            Respond with JSON:
            {
                "priority_items": ["items that offer biggest savings"],
                "timing_advice": "best time to shop for deals",
                "bulk_opportunities": [{"item": "product", "savings": "amount", "reason": "why"}],
                "substitutions": [{"original": "expensive item", "substitute": "cheaper option", "savings": "amount"}],
                "store_strategy": "specific advice for shopping at recommended stores",
                "weekly_savings_potential": "estimated weekly savings amount"
            }
            """
            
            ai_optimization = await llm_client.get_json_completion(
                optimization_prompt,
                system_prompt
            )
            
            # Update shopping list status
            shopping_list.status = "optimized"
            shopping_list.updated_at = datetime.now()
            session.commit()
            
            result = {
                "shopping_list_id": shopping_list.id,
                "optimization_results": optimization_result,
                "ai_recommendations": ai_optimization,
                "optimized_at": datetime.now().isoformat(),
                "next_steps": [
                    "Review the recommended store for best total cost",
                    "Consider the bulk buying opportunities",
                    "Check substitution suggestions for additional savings"
                ]
            }
            
            session.close()
            logger.info(f"✅ Shopping list optimized for user {user_id}")
            return result
            
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error optimizing shopping list: {e}")
            return {"error": "Failed to optimize shopping list", "details": str(e)}
    
    async def find_current_deals(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Find current deals and money-saving opportunities"""
        
        logger.info(f"Finding deals for user {user_id}")
        
        # Initialize context if None
        if context is None:
            context = {}
        
        try:
            # Get user preferences
            memory = ConversationMemory(user_id)
            user_preferences = {
                "favorite_products": memory.get_preference("favorite_products", []),
                "dietary_restrictions": memory.get_preference("dietary_restrictions", []),
                "budget_limit": memory.get_preference("budget_limit", 100)
            }
            
            # Get common grocery items to check for deals
            common_items = [
                "milk", "bread", "eggs", "chicken", "rice", "pasta", 
                "tomatoes", "bananas", "cheese", "yogurt"
            ]
            
            # Add user's favorite products if any
            items_to_check = common_items + user_preferences["favorite_products"]
            items_to_check = list(set(items_to_check))  # Remove duplicates
            
            # LOOP PREVENTION: Limit items and add context
            items_to_check = items_to_check[:10]  # Limit to 10 items
            context["skip_price_enhancement"] = True
            
            # Find best deals using the tool
            deals_result = await tool_registry.execute_tool(
                "find_best_deals",
                product_names=items_to_check,
                min_savings=0.5
            )
            
            if "error" in deals_result:
                return deals_result
            
            # Get additional deal analysis
            deals_analysis_prompt = f"""
            Analyze these deals and provide smart shopping advice:
            
            Found Deals: {json.dumps(deals_result, indent=2)}
            User Budget: ${user_preferences['budget_limit']}
            Dietary Restrictions: {user_preferences['dietary_restrictions']}
            
            Provide:
            1. Top 3 deals worth pursuing
            2. Weekly meal ideas using these deals
            3. Bulk buying recommendations
            4. Timing advice for maximum savings
            """
            
            system_prompt = """
            You are a deal-finding expert. Provide practical advice for maximizing grocery savings.
            
            Respond with JSON:
            {
                "top_deals": [
                    {"item": "product", "savings": "amount", "store": "store", "why_great": "explanation"}
                ],
                "meal_ideas": ["meals you can make with these deals"],
                "bulk_recommendations": [{"item": "product", "bulk_savings": "amount", "storage_tips": "advice"}],
                "timing_advice": "when to shop for best deals",
                "total_weekly_savings": "estimated savings if user follows advice"
            }
            """
            
            analysis = await llm_client.get_json_completion(
                deals_analysis_prompt,
                system_prompt
            )
            
            # Learn about deals user might be interested in
            memory.learn_pattern("deal_preferences", {
                "deals_found": len(deals_result.get("best_deals", [])),
                "total_savings": deals_result.get("total_potential_savings", 0),
                "favorite_categories": list(set(
                    deal.get("product_name", "").split()[0] 
                    for deal in deals_result.get("best_deals", [])
                ))
            })
            
            return {
                "deals_summary": deals_result,
                "analysis": analysis,
                "search_date": datetime.now().isoformat(),
                "items_checked": len(items_to_check),
                "personalized_for": f"Budget: ${user_preferences['budget_limit']}, Restrictions: {user_preferences['dietary_restrictions']}"
            }
            
        except Exception as e:
            logger.error(f"Error finding deals: {e}")
            return {"error": "Failed to find deals", "details": str(e)}
    
    async def plan_shopping_route(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Plan optimal shopping route and timing"""
        
        # This is a simplified version - in a full implementation, 
        # you'd integrate with Google Maps API or similar
        
        session = get_session()
        
        try:
            user = get_user(user_id, session)
            if not user:
                return {"error": "User not found"}
            
            # Get preferred stores
            preferred_stores = json.loads(user.preferred_stores) if user.preferred_stores else ["walmart", "target"]
            
            route_planning_prompt = f"""
            Create an efficient shopping route plan for:
            
            Preferred Stores: {preferred_stores}
            Household Size: {user.household_size}
            Shopping Frequency: {user.shopping_frequency}
            
            Provide a practical shopping strategy including:
            1. Which stores to visit in what order
            2. Best days/times to shop at each store
            3. What to buy at each store for maximum efficiency
            4. Time estimates for each stop
            """
            
            system_prompt = """
            You are a shopping efficiency expert. Create practical route plans.
            
            Respond with JSON:
            {
                "optimal_route": [
                    {
                        "store": "store name",
                        "order": 1,
                        "best_time": "Tuesday 10am",
                        "categories_to_buy": ["produce", "dairy"],
                        "estimated_time": "30 minutes",
                        "tips": "specific advice for this store"
                    }
                ],
                "weekly_schedule": {
                    "primary_shop": "best day for main shopping",
                    "quick_trips": "days for quick restocks"
                },
                "efficiency_tips": ["general shopping efficiency advice"],
                "estimated_total_time": "75 minutes per week"
            }
            """
            
            route_plan = await llm_client.get_json_completion(
                route_planning_prompt,
                system_prompt
            )
            
            session.close()
            return {
                "route_plan": route_plan,
                "created_for": user.name,
                "preferences_used": {
                    "stores": preferred_stores,
                    "frequency": user.shopping_frequency
                },
                "plan_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error planning shopping route: {e}")
            return {"error": "Failed to plan shopping route", "details": str(e)}
    
    async def suggest_substitutions(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Suggest product substitutions for savings or dietary needs"""
        
        # Initialize context if None
        if context is None:
            context = {}
        
        # This would integrate with the price service for finding cheaper alternatives
        product_name = context.get("product_name", "expensive items") if context else "common groceries"
        
        substitution_prompt = f"""
        Suggest smart product substitutions for: {product_name}
        
        Focus on:
        1. Cheaper alternatives that maintain quality
        2. Healthier options at similar prices
        3. Store brands vs name brands
        4. Bulk vs individual packaging
        5. Seasonal alternatives
        """
        
        system_prompt = """
        You are a smart shopping advisor. Suggest practical substitutions.
        
        Respond with JSON:
        {
            "substitutions": [
                {
                    "original": "expensive product",
                    "substitute": "cheaper alternative", 
                    "savings": "$2.50 per purchase",
                    "quality_notes": "maintains same quality",
                    "where_to_find": "store sections"
                }
            ],
            "general_tips": ["broader substitution strategies"],
            "seasonal_advice": "seasonal alternatives to consider"
        }
        """
        
        try:
            substitutions = await llm_client.get_json_completion(
                substitution_prompt,
                system_prompt
            )
            
            return {
                "substitution_advice": substitutions,
                "for_product": product_name,
                "advice_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error suggesting substitutions: {e}")
            return {"error": "Failed to suggest substitutions", "details": str(e)}
    
    async def track_spending_patterns(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Track and analyze spending patterns"""
        
        session = get_session()
        
        try:
            # Get user's shopping history
            shopping_lists = session.query(ShoppingList)\
                .filter(ShoppingList.user_id == user_id)\
                .filter(ShoppingList.created_at > datetime.now() - timedelta(days=30))\
                .order_by(ShoppingList.created_at.desc())\
                .all()
            
            if not shopping_lists:
                session.close()
                return {
                    "message": "No recent shopping data available",
                    "suggestion": "Create some shopping lists to start tracking spending patterns"
                }
            
            # Analyze spending patterns
            spending_data = []
            for shopping_list in shopping_lists:
                spending_data.append({
                    "date": shopping_list.created_at.isoformat(),
                    "estimated_total": shopping_list.estimated_total,
                    "actual_total": shopping_list.actual_total,
                    "item_count": len(json.loads(shopping_list.items_data)),
                    "store": shopping_list.preferred_stores
                })
            
            analysis_prompt = f"""
            Analyze these spending patterns and provide insights:
            
            Spending Data (Last 30 days): {json.dumps(spending_data, indent=2)}
            
            Provide analysis on:
            1. Average spending per trip
            2. Spending trends (increasing/decreasing)
            3. Most expensive categories
            4. Money-saving opportunities
            5. Budget optimization suggestions
            """
            
            system_prompt = """
            You are a financial advisor for grocery spending. Provide actionable insights.
            
            Respond with JSON:
            {
                "spending_summary": {
                    "average_per_trip": "dollar amount",
                    "monthly_total": "estimated monthly spending",
                    "trend": "increasing/decreasing/stable"
                },
                "insights": [
                    "key observations about spending patterns"
                ],
                "savings_opportunities": [
                    {"area": "category", "potential_savings": "amount", "how": "method"}
                ],
                "budget_recommendations": "advice for staying within budget"
            }
            """
            
            analysis = await llm_client.get_json_completion(
                analysis_prompt,
                system_prompt
            )
            
            session.close()
            return {
                "spending_analysis": analysis,
                "data_period": "Last 30 days",
                "shopping_trips": len(spending_data),
                "analysis_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error tracking spending: {e}")
            return {"error": "Failed to track spending patterns", "details": str(e)}
    
    async def _handle_general_shopping_query(
        self, 
        user_id: int, 
        request: str, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Handle general shopping queries"""
        
        try:
            memory = ConversationMemory(user_id)
            user_context = memory.generate_context_summary()
            
            general_prompt = f"""
            You are a helpful shopping assistant. Respond to this user request:
            
            User Request: "{request}"
            
            User Context: {user_context}
            
            Provide helpful shopping advice, suggestions, or guidance.
            """
            
            system_prompt = """
            You are a knowledgeable shopping assistant. Be helpful, practical, and money-conscious.
            Always suggest concrete next steps when appropriate.
            """
            
            response = await llm_client.get_completion(general_prompt, system_prompt)
            
            return {
                "response": response,
                "type": "general_shopping_assistance",
                "generated_at": datetime.now().isoformat(),
                "suggestions": [
                    "Create a smart shopping list",
                    "Find current grocery deals",
                    "Optimize your shopping route"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error handling general shopping query: {e}")
            return {"error": "I had trouble processing your shopping request. Could you please rephrase it?"}
    
    async def get_shopping_summary(self, user_id: int) -> Dict[str, Any]:
        """Get summary of user's shopping activity"""
        
        try:
            session = get_session()
            
            # Get recent shopping lists
            recent_lists = session.query(ShoppingList)\
                .filter(ShoppingList.user_id == user_id)\
                .order_by(ShoppingList.created_at.desc())\
                .limit(5)\
                .all()
            
            # Get memory patterns
            memory = ConversationMemory(user_id)
            
            summary = {
                "recent_shopping_lists": len(recent_lists),
                "total_estimated_spending": sum(sl.estimated_total or 0 for sl in recent_lists),
                "preferred_stores": [sl.preferred_stores for sl in recent_lists if sl.preferred_stores],
                "shopping_patterns": {
                    "deal_preferences": memory.get_patterns("deal_preferences")[-3:],
                    "shopping_preferences": memory.get_patterns("shopping_preferences")[-3:]
                },
                "summary_generated_at": datetime.now().isoformat()
            }
            
            session.close()
            return summary
            
        except Exception as e:
            logger.error(f"Error getting shopping summary: {e}")
            return {"error": "Failed to generate shopping summary"}

# Create global instance
shopping_agent = ShoppingAgent()