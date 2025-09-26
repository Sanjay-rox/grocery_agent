import json
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import logging

from src.core.llm_client import llm_client
from src.core.memory import ConversationMemory
from src.core.tools import tool_registry
from src.data.models import get_session, User, InventoryItem, MealPlan, Recipe, get_user, get_user_inventory
from src.core.config import Config

logger = logging.getLogger(__name__)

class PlanningAgent:
    """Agent responsible for meal planning and inventory management"""
    
    def __init__(self):
        self.name = "Planning Agent"
        self.description = "I handle meal planning, inventory tracking, and nutritional analysis"
        self.capabilities = [
            "weekly_meal_planning",
            "inventory_management",
            "recipe_recommendations",
            "nutritional_analysis",
            "shopping_list_generation"
        ]
        
    async def process_request(self, user_id: int, request: str, context: Dict = None) -> Dict[str, Any]:
        """Process user request related to meal planning"""
        
        memory = ConversationMemory(user_id)
        user_context = memory.generate_context_summary()
        
        # Determine the type of planning request
        request_type = await self._classify_request(request)
        
        response = {}
        
        try:
            if request_type == "meal_planning":
                response = await self.create_weekly_meal_plan(user_id, context)
            elif request_type == "inventory_check":
                response = await self.check_inventory_status(user_id)
            elif request_type == "recipe_suggestion":
                response = await self.suggest_recipes(user_id, request, context)
            elif request_type == "nutrition_analysis":
                response = await self.analyze_nutrition(user_id, context)
            elif request_type == "shopping_list":
                response = await self.generate_shopping_list(user_id, context)
            else:
                response = await self._handle_general_planning_query(user_id, request, context)
            
            # Save conversation to memory
            memory.add_conversation(request, str(response), "planning")
            
            return response
            
        except Exception as e:
            logger.error(f"Planning agent error: {e}")
            return {
                "error": "I encountered an issue with meal planning. Please try again.",
                "details": str(e)
            }
    
    async def _classify_request(self, request: str) -> str:
        """Classify the type of planning request"""
        
        classification_prompt = f"""
        Classify this user request into one of these categories:
        - meal_planning: Creating weekly meal plans, planning meals
        - inventory_check: Checking what's in stock, inventory status
        - recipe_suggestion: Finding recipes, recipe recommendations  
        - nutrition_analysis: Nutritional information, health analysis
        - shopping_list: Creating or updating shopping lists
        - general: Other planning-related queries
        
        User request: "{request}"
        
        Respond with just the category name.
        """
        
        classification = await llm_client.get_completion(
            classification_prompt,
            "You are a classification assistant. Respond with only the category name."
        )
        
        return classification.strip().lower()
    
    async def create_weekly_meal_plan(
        self, 
        user_id: int, 
        preferences: Dict = None,
        start_date: date = None
    ) -> Dict[str, Any]:
        """Create a comprehensive weekly meal plan"""
        
        logger.info(f"Creating meal plan for user {user_id}")
        
        # Get user information
        session = get_session()
        user = get_user(user_id, session)
        
        if not user:
            session.close()
            return {"error": "User not found"}
        
        # Get current inventory
        inventory = get_user_inventory(user_id, session)
        inventory_summary = [
            f"{item.item_name}: {item.quantity} {item.unit}"
            for item in inventory
        ]
        
        # Get user preferences from memory
        memory = ConversationMemory(user_id)
        user_preferences = {
            "dietary_restrictions": memory.get_preference("dietary_restrictions", []),
            "favorite_cuisines": memory.get_preference("favorite_cuisines", []),
            "budget_limit": memory.get_preference("budget_limit", user.budget_limit),
            "cooking_skill": memory.get_preference("cooking_skill", "intermediate"),
            "household_size": user.household_size
        }
        
        # Override with provided preferences
        if preferences:
            user_preferences.update(preferences)
        
        # Determine start date
        if not start_date:
            start_date = date.today()
            # Start from next Monday if it's already Wednesday or later
            if start_date.weekday() >= 2:  # Wednesday = 2
                days_until_monday = 7 - start_date.weekday()
                start_date = start_date + timedelta(days=days_until_monday)
        
        # Create meal plan using LLM
        meal_plan_prompt = f"""
        Create a comprehensive weekly meal plan for the following user:
        
        User Profile:
        - Household size: {user_preferences['household_size']} people
        - Budget limit: ${user_preferences['budget_limit']}/week
        - Dietary restrictions: {user_preferences['dietary_restrictions']}
        - Favorite cuisines: {user_preferences['favorite_cuisines']}
        - Cooking skill level: {user_preferences['cooking_skill']}
        
        Current Inventory:
        {chr(10).join(inventory_summary) if inventory_summary else "No current inventory"}
        
        Week starting: {start_date.strftime('%Y-%m-%d')}
        
        Please create a meal plan that:
        1. Uses existing inventory items when possible
        2. Provides nutritional balance
        3. Stays within budget
        4. Matches dietary preferences
        5. Varies cuisine types throughout the week
        6. Considers cooking skill level
        
        Include breakfast, lunch, and dinner for each day.
        Provide estimated prep time and difficulty for each meal.
        """
        
        system_prompt = """
        You are a professional meal planning nutritionist. Create detailed, practical meal plans.
        
        Respond with valid JSON in this exact format:
        {
            "meal_plan": {
                "monday": {
                    "breakfast": {"name": "...", "prep_time": 15, "difficulty": "easy", "serves": 2},
                    "lunch": {"name": "...", "prep_time": 20, "difficulty": "medium", "serves": 2},
                    "dinner": {"name": "...", "prep_time": 45, "difficulty": "medium", "serves": 2}
                },
                "tuesday": {...},
                "wednesday": {...},
                "thursday": {...},
                "friday": {...},
                "saturday": {...},
                "sunday": {...}
            },
            "shopping_list": [
                {"item": "ingredient name", "quantity": "amount", "unit": "unit", "estimated_cost": 0.0, "category": "produce/meat/dairy/etc"}
            ],
            "weekly_summary": {
                "total_estimated_cost": 0.0,
                "avg_prep_time_per_meal": 0,
                "nutritional_highlights": "Brief summary of nutritional balance",
                "variety_score": "Description of cuisine variety"
            },
            "tips": [
                "Practical cooking and prep tips for the week"
            ]
        }
        """
        
        try:
            # Get meal plan from LLM
            meal_plan_response = await llm_client.get_json_completion(
                meal_plan_prompt,
                system_prompt
            )
            
            if "error" in meal_plan_response:
                logger.error(f"LLM meal planning error: {meal_plan_response}")
                return {"error": "Failed to generate meal plan", "details": meal_plan_response}
            
            # Save meal plan to database
            end_date = start_date + timedelta(days=6)
            
            meal_plan = MealPlan(
                user_id=user_id,
                week_start_date=datetime.combine(start_date, datetime.min.time()),
                week_end_date=datetime.combine(end_date, datetime.min.time()),
                meal_data=json.dumps(meal_plan_response.get("meal_plan", {})),
                shopping_list_data=json.dumps(meal_plan_response.get("shopping_list", [])),
                total_cost=meal_plan_response.get("weekly_summary", {}).get("total_estimated_cost", 0),
                is_active=True
            )
            
            session.add(meal_plan)
            session.commit()
            
            # Learn from this meal plan
            memory.learn_pattern("meal_planning", {
                "cuisines_planned": user_preferences['favorite_cuisines'],
                "budget_used": meal_plan_response.get("weekly_summary", {}).get("total_estimated_cost", 0),
                "household_size": user_preferences['household_size']
            })
            
            logger.info(f"✅ Meal plan created successfully for user {user_id}")
            
            response = meal_plan_response.copy()
            response["meal_plan_id"] = meal_plan.id
            response["week_dates"] = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
            
            session.close()
            return response
            
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error creating meal plan: {e}")
            return {"error": "Failed to create meal plan", "details": str(e)}
    
    async def check_inventory_status(self, user_id: int) -> Dict[str, Any]:
        """Check current inventory status and identify needs"""
        
        logger.info(f"Checking inventory for user {user_id}")
        
        try:
            # Use tool registry to check inventory
            inventory_result = await tool_registry.execute_tool("check_inventory", user_id=user_id)
            
            if "error" in inventory_result:
                return inventory_result
            
            inventory_items = inventory_result.get("inventory", [])
            
            # Analyze inventory status
            analysis_prompt = f"""
            Analyze this inventory status and provide insights:
            
            Current Inventory:
            {json.dumps(inventory_items, indent=2)}
            
            Provide analysis on:
            1. Items running low (quantity < 2 or expiring soon)
            2. Items that might expire soon
            3. Recommended restocking priorities
            4. Potential meal suggestions based on available items
            """
            
            system_prompt = """
            You are an inventory management specialist. Provide practical insights about grocery inventory.
            
            Respond with valid JSON:
            {
                "status_summary": "Overall inventory status description",
                "low_stock_items": ["item1", "item2"],
                "expiring_soon": [{"item": "name", "days_until_expiry": 3}],
                "restock_priorities": [
                    {"item": "name", "priority": "high/medium/low", "reason": "why it's needed"}
                ],
                "meal_suggestions": [
                    {"meal": "meal name", "reason": "uses available ingredients"}
                ],
                "action_items": [
                    "Specific actions to take"
                ]
            }
            """
            
            analysis_response = await llm_client.get_json_completion(
                analysis_prompt,
                system_prompt
            )
            
            # Combine inventory data with analysis
            result = {
                "inventory_data": inventory_result,
                "analysis": analysis_response,
                "checked_at": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Inventory analysis completed for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error checking inventory: {e}")
            return {"error": "Failed to check inventory", "details": str(e)}
    
    async def suggest_recipes(
        self, 
        user_id: int, 
        request: str,
        context: Dict = None
    ) -> Dict[str, Any]:
        """Suggest recipes based on user request and available ingredients"""
        
        logger.info(f"Finding recipe suggestions for user {user_id}")
        
        try:
            # Get user's current inventory
            inventory_result = await tool_registry.execute_tool("check_inventory", user_id=user_id)
            available_ingredients = [
                item["name"] for item in inventory_result.get("inventory", [])
                if item["quantity"] > 0
            ]
            
            # Get user preferences
            memory = ConversationMemory(user_id)
            dietary_restrictions = memory.get_preference("dietary_restrictions", [])
            favorite_cuisines = memory.get_preference("favorite_cuisines", [])
            cooking_skill = memory.get_preference("cooking_skill", "intermediate")
            
            # Extract additional context from request
            recipe_request_prompt = f"""
            Analyze this recipe request and extract parameters:
            
            User request: "{request}"
            
            Extract:
            - Specific ingredients mentioned
            - Cuisine type preference  
            - Meal type (breakfast, lunch, dinner, snack)
            - Cooking time constraints
            - Difficulty preferences
            - Any other relevant parameters
            """
            
            context_analysis = await llm_client.get_json_completion(
                recipe_request_prompt,
                """Extract recipe parameters as JSON:
                {
                    "specific_ingredients": [],
                    "cuisine_preference": "cuisine or null",
                    "meal_type": "meal type or null", 
                    "max_cook_time": "time in minutes or null",
                    "difficulty_preference": "easy/medium/hard or null"
                }"""
            )
            
            # Find recipes using tool
            recipe_params = {
                "ingredients": available_ingredients + context_analysis.get("specific_ingredients", []),
                "dietary_restrictions": dietary_restrictions,
                "cuisine_type": context_analysis.get("cuisine_preference") or (favorite_cuisines[0] if favorite_cuisines else None),
                "max_cook_time": context_analysis.get("max_cook_time")
            }
            
            # Remove None values
            recipe_params = {k: v for k, v in recipe_params.items() if v is not None}
            
            recipe_result = await tool_registry.execute_tool("find_recipes", **recipe_params)
            
            if "error" in recipe_result:
                return recipe_result
            
            # Enhance suggestions with personalized recommendations
            enhancement_prompt = f"""
            Enhance these recipe suggestions with personalized recommendations:
            
            User Profile:
            - Cooking skill: {cooking_skill}
            - Dietary restrictions: {dietary_restrictions}
            - Available ingredients: {available_ingredients}
            
            Found Recipes:
            {json.dumps(recipe_result.get("recipes", []), indent=2)}
            
            For each recipe, add:
            1. Personal fit score (1-10) based on user profile
            2. What ingredients they already have vs need to buy
            3. Cooking tips for their skill level
            4. Nutritional highlights
            5. Why this recipe is recommended for them
            """
            
            system_prompt = """
            You are a personal recipe advisor. Enhance recipe suggestions with personalized insights.
            
            Respond with valid JSON:
            {
                "enhanced_recipes": [
                    {
                        "recipe": {...original recipe data...},
                        "personal_fit_score": 8,
                        "ingredients_you_have": ["ingredient1", "ingredient2"],
                        "ingredients_to_buy": ["ingredient3", "ingredient4"],
                        "cooking_tips": ["tip1", "tip2"],
                        "nutritional_highlights": "What makes this nutritious",
                        "recommendation_reason": "Why this is perfect for you"
                    }
                ],
                "overall_suggestions": [
                    "General cooking suggestions based on available ingredients"
                ]
            }
            """
            
            enhanced_result = await llm_client.get_json_completion(
                enhancement_prompt,
                system_prompt
            )
            
            # Learn from recipe preferences
            memory.learn_pattern("recipe_preferences", {
                "requested_cuisine": context_analysis.get("cuisine_preference"),
                "meal_type": context_analysis.get("meal_type"),
                "cooking_skill": cooking_skill
            })
            
            result = {
                "original_request": request,
                "search_parameters": recipe_params,
                "recipe_suggestions": enhanced_result,
                "available_ingredients": available_ingredients,
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Recipe suggestions generated for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error suggesting recipes: {e}")
            return {"error": "Failed to suggest recipes", "details": str(e)}
    
    async def analyze_nutrition(self, user_id: int, context: Dict = None) -> Dict[str, Any]:
        """Analyze nutrition for meal plans, recipes, or current diet"""
        
        logger.info(f"Analyzing nutrition for user {user_id}")
        
        try:
            session = get_session()
            user = get_user(user_id, session)
            
            # Get recent meal plan
            recent_meal_plan = session.query(MealPlan)\
                .filter(MealPlan.user_id == user_id)\
                .filter(MealPlan.is_active == True)\
                .order_by(MealPlan.created_at.desc())\
                .first()
            
            if not recent_meal_plan:
                session.close()
                return {"error": "No meal plan found for nutritional analysis"}
            
            meal_plan_data = json.loads(recent_meal_plan.meal_data)
            
            # Analyze nutrition for the meal plan
            nutrition_prompt = f"""
            Analyze the nutritional content of this weekly meal plan:
            
            User Profile:
            - Household size: {user.household_size} people
            - Health goals: {user.health_goals or 'general wellness'}
            
            Weekly Meal Plan:
            {json.dumps(meal_plan_data, indent=2)}
            
            Provide comprehensive nutritional analysis including:
            1. Daily average calories, macronutrients, and micronutrients
            2. Weekly nutritional balance assessment
            3. Areas of strength and improvement
            4. Specific recommendations for better nutrition
            5. How well it meets dietary guidelines
            """
            
            system_prompt = """
            You are a registered dietitian. Provide comprehensive nutritional analysis.
            
            Respond with valid JSON:
            {
                "daily_averages": {
                    "calories": 0,
                    "protein": 0,
                    "carbohydrates": 0,
                    "fat": 0,
                    "fiber": 0,
                    "sugar": 0,
                    "sodium": 0
                },
                "weekly_assessment": {
                    "overall_score": 8.5,
                    "balance_rating": "excellent/good/fair/poor",
                    "variety_score": 9,
                    "nutrient_density": "high/medium/low"
                },
                "strengths": [
                    "What the meal plan does well nutritionally"
                ],
                "areas_for_improvement": [
                    "Specific nutritional gaps or concerns"
                ],
                "recommendations": [
                    {
                        "category": "protein/vegetables/etc",
                        "suggestion": "specific actionable advice",
                        "priority": "high/medium/low"
                    }
                ],
                "dietary_guideline_compliance": {
                    "meets_fruit_vegetable_guidelines": true,
                    "appropriate_protein_intake": true,
                    "whole_grain_inclusion": false,
                    "sodium_level": "within_limits/too_high/too_low"
                },
                "meal_timing_suggestions": [
                    "Advice about meal timing and frequency"
                ]
            }
            """
            
            nutrition_analysis = await llm_client.get_json_completion(
                nutrition_prompt,
                system_prompt
            )
            
            # Get user's health patterns
            memory = ConversationMemory(user_id)
            health_patterns = memory.get_patterns("health_tracking")
            
            result = {
                "meal_plan_id": recent_meal_plan.id,
                "analysis_date": datetime.now().isoformat(),
                "nutritional_analysis": nutrition_analysis,
                "meal_plan_period": {
                    "start": recent_meal_plan.week_start_date.isoformat(),
                    "end": recent_meal_plan.week_end_date.isoformat()
                },
                "user_profile": {
                    "household_size": user.household_size,
                    "health_goals": json.loads(user.health_goals) if user.health_goals else []
                }
            }
            
            # Learn from nutrition analysis
            memory.learn_pattern("nutrition_focus", {
                "analysis_date": datetime.now().isoformat(),
                "overall_score": nutrition_analysis.get("weekly_assessment", {}).get("overall_score", 0),
                "main_concerns": nutrition_analysis.get("areas_for_improvement", [])
            })
            
            session.close()
            logger.info(f"✅ Nutritional analysis completed for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing nutrition: {e}")
            return {"error": "Failed to analyze nutrition", "details": str(e)}
    
    async def generate_shopping_list(
        self, 
        user_id: int, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Generate optimized shopping list based on meal plan and inventory"""
        
        logger.info(f"Generating shopping list for user {user_id}")
        
        try:
            session = get_session()
            
            # Get active meal plan
            meal_plan = session.query(MealPlan)\
                .filter(MealPlan.user_id == user_id)\
                .filter(MealPlan.is_active == True)\
                .order_by(MealPlan.created_at.desc())\
                .first()
            
            if not meal_plan:
                session.close()
                return {"error": "No active meal plan found. Please create a meal plan first."}
            
            meal_plan_data = json.loads(meal_plan.meal_data)
            
            # Use tool to create shopping list
            shopping_list_result = await tool_registry.execute_tool(
                "create_shopping_list",
                user_id=user_id,
                meal_plan=meal_plan_data,
                budget_limit=context.get("budget_limit") if context else None
            )
            
            if "error" in shopping_list_result:
                session.close()
                return shopping_list_result
            
            # Optimize shopping list with AI insights
            optimization_prompt = f"""
            Optimize this shopping list with smart suggestions:
            
            Shopping List:
            {json.dumps(shopping_list_result.get("shopping_list", []), indent=2)}
            
            Budget: ${shopping_list_result.get("budget_limit", "No limit")}
            Current Total: ${shopping_list_result.get("estimated_total_cost", 0)}
            
            Provide optimizations for:
            1. Bulk buying opportunities
            2. Seasonal substitutions for better prices
            3. Store recommendations based on item types
            4. Coupon/discount opportunities
            5. Alternative brands or products
            6. Shopping sequence for efficiency
            """
            
            system_prompt = """
            You are a smart shopping advisor. Optimize shopping lists for cost and efficiency.
            
            Respond with valid JSON:
            {
                "optimized_list": [
                    {
                        "item": "item name",
                        "quantity": 2,
                        "unit": "unit",
                        "estimated_price": 3.99,
                        "category": "produce",
                        "priority": "high/medium/low",
                        "optimization_notes": "why this optimization",
                        "alternative_options": ["alt1", "alt2"]
                    }
                ],
                "shopping_strategy": {
                    "recommended_stores": [
                        {"store": "store name", "items": ["item1", "item2"], "reason": "why shop here"}
                    ],
                    "shopping_order": ["category1", "category2"],
                    "estimated_time": 45
                },
                "cost_savings": {
                    "original_total": 75.50,
                    "optimized_total": 68.25,
                    "savings": 7.25,
                    "savings_tips": ["tip1", "tip2"]
                },
                "bulk_opportunities": [
                    {"item": "item", "savings": 2.50, "reason": "bulk discount available"}
                ],
                "seasonal_substitutions": [
                    {"original": "item1", "substitute": "item2", "reason": "in season, cheaper"}
                ]
            }
            """
            
            optimization_result = await llm_client.get_json_completion(
                optimization_prompt,
                system_prompt
            )
            
            # Combine original list with optimizations
            final_result = {
                "meal_plan_id": meal_plan.id,
                "generated_at": datetime.now().isoformat(),
                "original_shopping_list": shopping_list_result,
                "optimizations": optimization_result,
                "status": "ready_for_shopping"
            }
            
            # Save shopping list preferences
            memory = ConversationMemory(user_id)
            memory.learn_pattern("shopping_preferences", {
                "budget_conscious": shopping_list_result.get("estimated_total_cost", 0) < 100,
                "preferred_stores": [store["store"] for store in optimization_result.get("shopping_strategy", {}).get("recommended_stores", [])],
                "bulk_buying": len(optimization_result.get("bulk_opportunities", [])) > 0
            })
            
            session.close()
            logger.info(f"✅ Shopping list generated and optimized for user {user_id}")
            return final_result
            
        except Exception as e:
            logger.error(f"Error generating shopping list: {e}")
            return {"error": "Failed to generate shopping list", "details": str(e)}
    
    async def _handle_general_planning_query(
        self, 
        user_id: int, 
        request: str, 
        context: Dict = None
    ) -> Dict[str, Any]:
        """Handle general planning queries that don't fit specific categories"""
        
        try:
            # Get user context
            memory = ConversationMemory(user_id)
            user_context = memory.generate_context_summary()
            
            # Get recent planning data
            session = get_session()
            user = get_user(user_id, session)
            
            recent_meal_plan = session.query(MealPlan)\
                .filter(MealPlan.user_id == user_id)\
                .order_by(MealPlan.created_at.desc())\
                .first()
            
            inventory = get_user_inventory(user_id, session)
            
            # Prepare context for LLM
            planning_context = {
                "user_profile": user.to_dict() if user else {},
                "recent_meal_plan": recent_meal_plan.to_dict() if recent_meal_plan else None,
                "inventory_count": len(inventory),
                "user_context": user_context
            }
            
            response_prompt = f"""
            You are a meal planning and grocery management assistant. Help the user with their request:
            
            User Request: "{request}"
            
            User Context:
            {json.dumps(planning_context, indent=2, default=str)}
            
            Provide a helpful, actionable response that addresses their request.
            If they need specific meal plans, recipes, or shopping lists, guide them on how to get those.
            """
            
            system_prompt = """
            You are a friendly, knowledgeable meal planning assistant. Provide practical, actionable advice.
            Be conversational but informative. If you need more information, ask specific questions.
            
            Always suggest concrete next steps when appropriate.
            """
            
            response = await llm_client.get_completion(
                response_prompt,
                system_prompt
            )
            
            session.close()
            
            return {
                "response": response,
                "type": "general_planning_assistance",
                "generated_at": datetime.now().isoformat(),
                "context_used": planning_context
            }
            
        except Exception as e:
            logger.error(f"Error handling general planning query: {e}")
            return {"error": "I had trouble processing your request. Could you please rephrase it?"}
    
    async def get_planning_summary(self, user_id: int) -> Dict[str, Any]:
        """Get a summary of current planning status"""
        
        try:
            session = get_session()
            
            # Get current meal plan
            current_meal_plan = session.query(MealPlan)\
                .filter(MealPlan.user_id == user_id)\
                .filter(MealPlan.is_active == True)\
                .order_by(MealPlan.created_at.desc())\
                .first()
            
            # Get inventory status
            inventory = get_user_inventory(user_id, session)
            low_stock_items = get_user_inventory(user_id, low_stock_only=True, session=session)
            
            # Get user preferences
            memory = ConversationMemory(user_id)
            
            summary = {
                "current_meal_plan": {
                    "exists": current_meal_plan is not None,
                    "week_start": current_meal_plan.week_start_date.isoformat() if current_meal_plan else None,
                    "estimated_cost": current_meal_plan.total_cost if current_meal_plan else 0
                },
                "inventory_status": {
                    "total_items": len(inventory),
                    "low_stock_items": len(low_stock_items),
                    "low_stock_item_names": [item.item_name for item in low_stock_items]
                },
                "recent_patterns": {
                    "meal_planning": memory.get_patterns("meal_planning")[-3:],  # Last 3
                    "shopping_preferences": memory.get_patterns("shopping_preferences")[-3:]
                },
                "summary_generated_at": datetime.now().isoformat()
            }
            
            session.close()
            return summary
            
        except Exception as e:
            logger.error(f"Error getting planning summary: {e}")
            return {"error": "Failed to generate planning summary"}

# Create global instance
planning_agent = PlanningAgent()