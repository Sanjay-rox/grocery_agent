import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from src.core.llm_client import llm_client
from src.core.memory import ConversationMemory
from src.agents.planning_agent import planning_agent
# Added import for shopping agent
from src.agents.shopping_agent import shopping_agent
from src.core.config import Config

logger = logging.getLogger(__name__)

class MasterAgent:
    """Central coordinator for all grocery AI operations"""
    
    def __init__(self):
        self.name = "Grocery AI Assistant"
        self.description = "I'm your personal grocery and meal planning AI assistant"
        self.version = "1.0.0"
        
        # Available agents
        self.agents = {
            "planning": planning_agent,
            # "shopping": shopping_agent,  # Will be implemented later
            # "nutrition": nutrition_agent,  # Will be implemented later
            # "learning": learning_agent  # Will be implemented later
            "shopping": shopping_agent  # Placeholder for shopping agent
        }
        
        self.capabilities = [
            "meal_planning",
            "inventory_management", 
            "recipe_suggestions",
            "shopping_list_generation",
            "price_comparison",
            "nutritional_analysis",
            "automated_ordering",
            "personalized_recommendations"
        ]
        
    async def process_user_message(
        self, 
        user_id: int, 
        message: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Main entry point for processing user messages"""
        
        logger.info(f"Processing message from user {user_id}: {message[:100]}...")
        
        try:
            # Load user memory and context
            memory = ConversationMemory(user_id)
            user_context = memory.generate_context_summary()
            
            # Determine intent and route to appropriate agent
            intent_analysis = await self._analyze_user_intent(message, user_context)
            
            if intent_analysis.get("error"):
                return {
                    "response": "I'm having trouble understanding your request. Could you please rephrase it?",
                    "error": intent_analysis["error"],
                    "success": False
                }
            
            # Route to appropriate agent
            agent_response = await self._route_to_agent(
                user_id, 
                message, 
                intent_analysis, 
                context
            )
            
            # Generate final response
            final_response = await self._generate_final_response(
                user_id,
                message,
                intent_analysis,
                agent_response
            )
            
            # Save conversation to memory
            memory.add_conversation(message, str(final_response.get("response", "")), "master")
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "error": str(e),
                "success": False
            }
    
    async def _analyze_user_intent(self, message: str, user_context: str) -> Dict[str, Any]:
        """Analyze user message to determine intent and routing"""
        
        intent_prompt = f"""
        Analyze this user message and determine their intent and requirements:
        
        User Message: "{message}"
        
        User Context:
        {user_context}
        
        Determine:
        1. Primary intent (what they want to accomplish)
        2. Which agent should handle this (planning, shopping, nutrition, learning, or general)
        3. Urgency level (low, medium, high)
        4. Any specific parameters or requirements
        5. Whether multiple agents might be needed
        
        Available capabilities:
        - meal_planning: Create meal plans, suggest weekly menus
        - inventory_management: Check what's in stock, track expiration dates
        - recipe_suggestions: Find recipes based on ingredients or preferences  
        - shopping_list_generation: Create optimized shopping lists
        - price_comparison: Compare prices across stores
        - nutritional_analysis: Analyze nutritional content and health aspects
        - automated_ordering: Place orders automatically
        - personalized_recommendations: AI-powered suggestions based on history
        """
        
        system_prompt = """
        You are an intent analysis specialist for a grocery AI assistant.
        
        Respond with valid JSON:
        {
            "primary_intent": "clear description of what user wants",
            "intent_category": "meal_planning|inventory_management|recipe_suggestions|shopping_list_generation|price_comparison|nutritional_analysis|automated_ordering|personalized_recommendations|general_inquiry",
            "target_agent": "planning|shopping|nutrition|learning|master",
            "urgency": "low|medium|high",
            "parameters": {
                "key": "extracted parameters from the message"
            },
            "requires_multiple_agents": false,
            "confidence_score": 0.95,
            "suggested_clarifications": []
        }
        """
        
        try:
            intent_response = await llm_client.get_json_completion(
                intent_prompt,
                system_prompt
            )
            
            return intent_response
            
        except Exception as e:
            logger.error(f"Error analyzing user intent: {e}")
            return {"error": f"Intent analysis failed: {str(e)}"}
    
    async def _route_to_agent(
        self,
        user_id: int,
        message: str,
        intent_analysis: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Route request to appropriate specialized agent"""
        
        target_agent = intent_analysis.get("target_agent", "master")
        intent_category = intent_analysis.get("intent_category", "general_inquiry")
        
        try:
            # Add extracted parameters to context
            if context is None:
                context = {}
            context.update(intent_analysis.get("parameters", {}))
            
            if target_agent == "planning":
                return await self.agents["planning"].process_request(user_id, message, context)
            
            elif target_agent == "shopping":
                 return await self.agents["shopping"].process_request(user_id, message, context)
            
            # elif target_agent == "nutrition":
            #     return await self.agents["nutrition"].process_request(user_id, message, context)
            
            # elif target_agent == "learning":
            #     return await self.agents["learning"].process_request(user_id, message, context)
            
            else:
                # Handle with master agent
                return await self._handle_general_query(user_id, message, intent_analysis, context)
        
        except Exception as e:
            logger.error(f"Error routing to agent {target_agent}: {e}")
            return {
                "error": f"Agent {target_agent} encountered an error: {str(e)}",
                "fallback_response": "I had trouble processing that specific request. How else can I help you with meal planning or grocery management?"
            }
    
    async def _handle_general_query(
        self,
        user_id: int,
        message: str,
        intent_analysis: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle general queries that don't require specialized agents"""
        
        # Get user information for context
        memory = ConversationMemory(user_id)
        user_context = memory.generate_context_summary()
        
        # Check if this is a greeting, help request, or general conversation
        if any(word in message.lower() for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            return await self._handle_greeting(user_id, message)
        
        elif any(word in message.lower() for word in ["help", "what can you do", "capabilities", "features"]):
            return await self._handle_help_request(user_id)
        
        elif any(word in message.lower() for word in ["status", "summary", "dashboard", "overview"]):
            return await self._handle_status_request(user_id)
        
        else:
            # General AI assistant response
            general_prompt = f"""
            You are a helpful grocery and meal planning AI assistant. Respond to this user message:
            
            User Message: "{message}"
            
            User Context:
            {user_context}
            
            Intent Analysis:
            {json.dumps(intent_analysis, indent=2)}
            
            Available Capabilities:
            {', '.join(self.capabilities)}
            
            Provide a helpful, conversational response. If they need specific functionality,
            guide them toward the appropriate capability.
            """
            
            system_prompt = """
            You are a friendly, knowledgeable grocery and meal planning AI assistant.
            Be conversational, helpful, and proactive in suggesting ways you can assist.
            Always end with an offer to help with something specific.
            """
            
            response_text = await llm_client.get_completion(general_prompt, system_prompt)
            
            return {
                "response": response_text,
                "type": "general_assistance",
                "suggestions": [
                    "Ask me to create a meal plan",
                    "Check your inventory status", 
                    "Find recipes based on what you have",
                    "Generate a shopping list"
                ]
            }
    
    async def _handle_greeting(self, user_id: int, message: str) -> Dict[str, Any]:
        """Handle greeting messages"""
        
        memory = ConversationMemory(user_id)
        user_name = memory.get_preference("name", "there")
        
        # Get quick status
        try:
            planning_summary = await planning_agent.get_planning_summary(user_id)
            has_meal_plan = planning_summary.get("current_meal_plan", {}).get("exists", False)
            low_stock_count = planning_summary.get("inventory_status", {}).get("low_stock_items", 0)
        except:
            has_meal_plan = False
            low_stock_count = 0
        
        greeting_options = [
            f"Hello {user_name}! I'm your grocery AI assistant. How can I help you today?",
            f"Hi {user_name}! Ready to plan some great meals or manage your grocery needs?",
            f"Hey {user_name}! I'm here to help with meal planning, shopping, and nutrition."
        ]
        
        import random
        greeting = random.choice(greeting_options)
        
        suggestions = []
        if not has_meal_plan:
            suggestions.append("Create your weekly meal plan")
        if low_stock_count > 0:
            suggestions.append(f"Check {low_stock_count} items running low")
        suggestions.extend([
            "Find recipes with ingredients you have",
            "Generate an optimized shopping list"
        ])
        
        return {
            "response": greeting,
            "type": "greeting",
            "suggestions": suggestions[:3],  # Limit to 3 suggestions
            "quick_stats": {
                "has_active_meal_plan": has_meal_plan,
                "low_stock_items": low_stock_count
            }
        }
    
    async def _handle_help_request(self, user_id: int) -> Dict[str, Any]:
        """Handle help and capability requests"""
        
        help_response = f"""
I'm your personal grocery AI assistant! Here's what I can help you with:

🍽️ **Meal Planning**
- Create weekly meal plans based on your preferences
- Suggest recipes using ingredients you already have
- Plan meals within your budget

🏠 **Inventory Management**  
- Track what's in your pantry, fridge, and freezer
- Alert you when items are running low
- Monitor expiration dates

🛒 **Smart Shopping**
- Generate optimized shopping lists
- Compare prices across stores
- Find the best deals and discounts

🥗 **Nutrition & Health**
- Analyze nutritional content of your meals
- Suggest healthier alternatives
- Track dietary goals

🤖 **Automation** 
- Learn your preferences over time
- Automate routine grocery tasks
- Send helpful reminders

Just tell me what you'd like to do! For example:
- "Create a meal plan for this week"
- "What ingredients am I running low on?"
- "Find recipes with chicken and rice"
- "Generate a shopping list"
        """
        
        return {
            "response": help_response,
            "type": "help",
            "capabilities": self.capabilities,
            "quick_actions": [
                "Create meal plan",
                "Check inventory", 
                "Find recipes",
                "Generate shopping list"
            ]
        }
    
    async def _handle_status_request(self, user_id: int) -> Dict[str, Any]:
        """Handle status and dashboard requests"""
        
        try:
            # Get comprehensive status from planning agent
            planning_summary = await planning_agent.get_planning_summary(user_id)
            
            # Create dashboard response
            status_prompt = f"""
            Create a user-friendly status dashboard based on this data:
            
            {json.dumps(planning_summary, indent=2, default=str)}
            
            Present it as a clear, organized status report with:
            1. Current meal plan status
            2. Inventory highlights
            3. Suggested actions
            4. Quick wins or recommendations
            """
            
            system_prompt = """
            Create a friendly, informative status dashboard. Use emojis and clear formatting.
            Focus on actionable insights and next steps.
            """
            
            status_response = await llm_client.get_completion(status_prompt, system_prompt)
            
            return {
                "response": status_response,
                "type": "status_dashboard",
                "raw_data": planning_summary,
                "quick_actions": self._generate_status_actions(planning_summary)
            }
            
        except Exception as e:
            logger.error(f"Error generating status: {e}")
            return {
                "response": "I'm having trouble gathering your status right now. Let me know what specific information you'd like to see!",
                "error": str(e)
            }
    
    def _generate_status_actions(self, planning_summary: Dict) -> List[str]:
        """Generate quick actions based on status"""
        actions = []
        
        if not planning_summary.get("current_meal_plan", {}).get("exists"):
            actions.append("Create your first meal plan")
        
        low_stock = planning_summary.get("inventory_status", {}).get("low_stock_items", 0)
        if low_stock > 0:
            actions.append(f"Restock {low_stock} low inventory items")
        
        if planning_summary.get("current_meal_plan", {}).get("exists"):
            actions.append("Generate shopping list for meal plan")
        
        actions.extend([
            "Find new recipe suggestions",
            "Update inventory status"
        ])
        
        return actions[:3]  # Return top 3 actions
    
    async def _generate_final_response(
        self,
        user_id: int,
        original_message: str,
        intent_analysis: Dict[str, Any],
        agent_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate final formatted response for the user"""
        
        try:
            # If agent response has an error, provide fallback
            if agent_response.get("error"):
                return {
                    "response": agent_response.get("fallback_response", "I encountered an issue processing your request. Please try again or ask for help."),
                    "success": False,
                    "error": agent_response["error"],
                    "suggestions": [
                        "Ask me for help to see what I can do",
                        "Try rephrasing your request",
                        "Check your current status"
                    ]
                }
            
            # Extract response text from agent response
            response_text = ""
            if isinstance(agent_response, dict):
                if "response" in agent_response:
                    response_text = agent_response["response"]
                elif "meal_plan" in agent_response:
                    # Format meal plan response
                    response_text = self._format_meal_plan_response(agent_response)
                elif "analysis" in agent_response:
                    # Format analysis response
                    response_text = self._format_analysis_response(agent_response)
                elif "recipe_suggestions" in agent_response:
                    # Format recipe response
                    response_text = self._format_recipe_response(agent_response)
                else:
                    # Generic formatting
                    response_text = f"I've processed your request successfully!"
            else:
                response_text = str(agent_response)
            
            # Generate follow-up suggestions
            follow_up_suggestions = await self._generate_follow_up_suggestions(
                user_id, 
                intent_analysis, 
                agent_response
            )
            
            final_response = {
                "response": response_text,
                "success": True,
                "type": intent_analysis.get("intent_category", "general"),
                "agent_used": intent_analysis.get("target_agent", "master"),
                "suggestions": follow_up_suggestions,
                "data": agent_response,
                "timestamp": datetime.now().isoformat()
            }
            
            return final_response
            
        except Exception as e:
            logger.error(f"Error generating final response: {e}")
            return {
                "response": "I processed your request, but had trouble formatting the response. The operation may have been successful.",
                "success": True,
                "error": f"Response formatting error: {str(e)}",
                "raw_data": agent_response
            }
    
    def _format_meal_plan_response(self, response: Dict[str, Any]) -> str:
        """Format meal plan response for user"""
        
        try:
            meal_plan = response.get("meal_plan", {})
            weekly_summary = response.get("weekly_summary", {})
            
            formatted = "🍽️ **Your Weekly Meal Plan**\n\n"
            
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for day, day_name in zip(days, day_names):
                if day in meal_plan:
                    formatted += f"**{day_name}:**\n"
                    meals = meal_plan[day]
                    for meal_type, meal_info in meals.items():
                        if isinstance(meal_info, dict):
                            name = meal_info.get("name", "Unnamed meal")
                            prep_time = meal_info.get("prep_time", "Unknown")
                            formatted += f"  • {meal_type.title()}: {name} ({prep_time} min)\n"
                        else:
                            formatted += f"  • {meal_type.title()}: {meal_info}\n"
                    formatted += "\n"
            
            if weekly_summary:
                formatted += "📊 **Weekly Summary:**\n"
                if "total_estimated_cost" in weekly_summary:
                    formatted += f"• Estimated cost: ${weekly_summary['total_estimated_cost']:.2f}\n"
                if "nutritional_highlights" in weekly_summary:
                    formatted += f"• Nutrition: {weekly_summary['nutritional_highlights']}\n"
                if "variety_score" in weekly_summary:
                    formatted += f"• Variety: {weekly_summary['variety_score']}\n"
            
            shopping_list = response.get("shopping_list", [])
            if shopping_list:
                formatted += f"\n🛒 **Shopping List:** {len(shopping_list)} items to buy\n"
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting meal plan: {e}")
            return "I created your meal plan! Use 'show my meal plan' to see the details."
    
    def _format_recipe_response(self, response: Dict[str, Any]) -> str:
        """Format recipe suggestions response"""
        
        try:
            suggestions = response.get("recipe_suggestions", {})
            enhanced_recipes = suggestions.get("enhanced_recipes", [])
            
            if not enhanced_recipes:
                return "I couldn't find any recipes matching your criteria. Try adjusting your preferences or ingredients."
            
            formatted = f"🍳 **Recipe Suggestions** ({len(enhanced_recipes)} found)\n\n"
            
            for i, recipe_data in enumerate(enhanced_recipes[:3], 1):  # Show top 3
                recipe = recipe_data.get("recipe", {})
                fit_score = recipe_data.get("personal_fit_score", 0)
                ingredients_you_have = recipe_data.get("ingredients_you_have", [])
                ingredients_to_buy = recipe_data.get("ingredients_to_buy", [])
                
                formatted += f"**{i}. {recipe.get('title', 'Unnamed Recipe')}** (Fit: {fit_score}/10)\n"
                formatted += f"⏱️ {recipe.get('readyInMinutes', 'Unknown')} minutes | "
                formatted += f"👥 Serves {recipe.get('servings', 'Unknown')}\n"
                
                if ingredients_you_have:
                    formatted += f"✅ You have: {', '.join(ingredients_you_have[:3])}{'...' if len(ingredients_you_have) > 3 else ''}\n"
                
                if ingredients_to_buy:
                    formatted += f"🛒 Need to buy: {', '.join(ingredients_to_buy[:3])}{'...' if len(ingredients_to_buy) > 3 else ''}\n"
                
                recommendation = recipe_data.get("recommendation_reason", "")
                if recommendation:
                    formatted += f"💡 {recommendation[:100]}...\n"
                
                formatted += "\n"
            
            if len(enhanced_recipes) > 3:
                formatted += f"... and {len(enhanced_recipes) - 3} more recipes available!\n"
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting recipe response: {e}")
            return "I found some recipe suggestions for you! Ask me to show recipe details for more information."
    
    def _format_analysis_response(self, response: Dict[str, Any]) -> str:
        """Format analysis response (inventory, nutrition, etc.)"""
        
        try:
            analysis = response.get("analysis", {})
            
            if "status_summary" in analysis:
                # Inventory analysis
                formatted = "📦 **Inventory Status**\n\n"
                formatted += f"{analysis['status_summary']}\n\n"
                
                low_stock = analysis.get("low_stock_items", [])
                if low_stock:
                    formatted += f"⚠️ **Low Stock:** {', '.join(low_stock)}\n\n"
                
                expiring = analysis.get("expiring_soon", [])
                if expiring:
                    formatted += "⏰ **Expiring Soon:**\n"
                    for item in expiring:
                        days = item.get("days_until_expiry", "Unknown")
                        formatted += f"  • {item.get('item', 'Unknown')} ({days} days)\n"
                    formatted += "\n"
                
                actions = analysis.get("action_items", [])
                if actions:
                    formatted += "✅ **Recommended Actions:**\n"
                    for action in actions[:3]:  # Top 3 actions
                        formatted += f"  • {action}\n"
                
                return formatted
                
            elif "weekly_assessment" in analysis:
                # Nutrition analysis
                weekly = analysis["weekly_assessment"]
                daily = analysis.get("daily_averages", {})
                
                formatted = "🥗 **Nutritional Analysis**\n\n"
                formatted += f"Overall Score: {weekly.get('overall_score', 'N/A')}/10\n"
                formatted += f"Balance Rating: {weekly.get('balance_rating', 'N/A').title()}\n\n"
                
                formatted += "📊 **Daily Averages:**\n"
                formatted += f"• Calories: {daily.get('calories', 0):.0f}\n"
                formatted += f"• Protein: {daily.get('protein', 0):.1f}g\n"
                formatted += f"• Carbs: {daily.get('carbohydrates', 0):.1f}g\n"
                formatted += f"• Fat: {daily.get('fat', 0):.1f}g\n\n"
                
                improvements = analysis.get("areas_for_improvement", [])
                if improvements:
                    formatted += "🎯 **Areas to Improve:**\n"
                    for improvement in improvements[:3]:
                        formatted += f"  • {improvement}\n"
                
                return formatted
            
            else:
                return f"Analysis completed! Here are the key findings:\n\n{str(analysis)[:200]}..."
                
        except Exception as e:
            logger.error(f"Error formatting analysis: {e}")
            return "I completed the analysis! Ask me for specific details if you'd like more information."
    
    async def _generate_follow_up_suggestions(
        self,
        user_id: int,
        intent_analysis: Dict[str, Any],
        agent_response: Dict[str, Any]
    ) -> List[str]:
        """Generate contextual follow-up suggestions"""
        
        try:
            intent_category = intent_analysis.get("intent_category", "")
            suggestions = []
            
            if intent_category == "meal_planning":
                suggestions = [
                    "Generate shopping list for this meal plan",
                    "Analyze nutrition for this week",
                    "Find alternative recipes"
                ]
            
            elif intent_category == "recipe_suggestions":
                suggestions = [
                    "Add ingredients to shopping list",
                    "Plan meals with these recipes",
                    "Find similar recipes"
                ]
            
            elif intent_category == "inventory_management":
                suggestions = [
                    "Create shopping list for low items",
                    "Find recipes with available ingredients",
                    "Set up restock alerts"
                ]
            
            elif intent_category == "shopping_list_generation":
                suggestions = [
                    "Compare prices across stores",
                    "Find coupons and deals",
                    "Optimize shopping route"
                ]
            
            else:
                # Generic suggestions
                suggestions = [
                    "Create a meal plan",
                    "Check inventory status",
                    "Find recipe suggestions"
                ]
            
            return suggestions[:3]  # Return top 3 suggestions
            
        except Exception as e:
            logger.error(f"Error generating follow-up suggestions: {e}")
            return ["Ask me for help", "Try another request", "Check your status"]
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status and health"""
        
        try:
            # Check LLM client status
            llm_status = llm_client.get_status()
            
            # Check available agents
            agent_status = {}
            for name, agent in self.agents.items():
                agent_status[name] = {
                    "available": True,
                    "name": getattr(agent, 'name', name),
                    "capabilities": getattr(agent, 'capabilities', [])
                }
            
            return {
                "system_name": self.name,
                "version": self.version,
                "status": "operational",
                "llm_client": llm_status,
                "agents": agent_status,
                "capabilities": self.capabilities,
                "last_checked": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "system_name": self.name,
                "status": "error",
                "error": str(e),
                "last_checked": datetime.now().isoformat()
            }
    
    async def initialize_system(self) -> Dict[str, Any]:
        """Initialize the grocery AI system"""
        
        try:
            logger.info("Initializing Grocery AI System...")
            
            # Initialize database
            from src.data.models import init_db
            init_db()
            
            # Check LLM client
            llm_status = llm_client.get_status()
            if not llm_status["groq_available"] and not llm_status["ollama_available"]:
                logger.warning("No LLM services available!")
            
            # Initialize agents
            agent_init_results = {}
            for name, agent in self.agents.items():
                try:
                    if hasattr(agent, 'initialize'):
                        await agent.initialize()
                    agent_init_results[name] = "initialized"
                except Exception as e:
                    agent_init_results[name] = f"error: {str(e)}"
            
            logger.info("✅ Grocery AI System initialized successfully")
            
            return {
                "status": "initialized",
                "system_name": self.name,
                "version": self.version,
                "llm_client": llm_status,
                "agents": agent_init_results,
                "capabilities": self.capabilities,
                "initialized_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
            return {
                "status": "initialization_failed",
                "error": str(e),
                "attempted_at": datetime.now().isoformat()
            }

# Create global master agent instance
master_agent = MasterAgent()