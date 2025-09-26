import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
from src.core.config import Config

logger = logging.getLogger(__name__)

class ConversationMemory:
    """Manages conversation history and user preferences"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.memory_file = os.path.join(Config.CACHE_DIR, f"memory_{user_id}.json")
        self.conversation_history = []
        self.user_preferences = {}
        self.learned_patterns = {}
        self.load_memory()
    
    def load_memory(self):
        """Load memory from file"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.conversation_history = data.get('conversation_history', [])
                    self.user_preferences = data.get('user_preferences', {})
                    self.learned_patterns = data.get('learned_patterns', {})
                logger.info(f"✅ Memory loaded for user {self.user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to load memory: {e}")
            self.conversation_history = []
            self.user_preferences = {}
            self.learned_patterns = {}
    
    def save_memory(self):
        """Save memory to file"""
        try:
            memory_data = {
                'user_id': self.user_id,
                'last_updated': datetime.now().isoformat(),
                'conversation_history': self.conversation_history[-50:],  # Keep last 50 interactions
                'user_preferences': self.user_preferences,
                'learned_patterns': self.learned_patterns
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(memory_data, f, indent=2)
            
            logger.info(f"✅ Memory saved for user {self.user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save memory: {e}")
    
    def add_conversation(self, user_message: str, agent_response: str, agent_type: str = "master"):
        """Add conversation to memory"""
        conversation_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'agent_response': agent_response,
            'agent_type': agent_type
        }
        
        self.conversation_history.append(conversation_entry)
        self.save_memory()
    
    def get_recent_conversations(self, limit: int = 5) -> List[Dict]:
        """Get recent conversations"""
        return self.conversation_history[-limit:]
    
    def update_preference(self, key: str, value: Any):
        """Update user preference"""
        self.user_preferences[key] = value
        self.save_memory()
        logger.info(f"Updated preference {key} for user {self.user_id}")
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get user preference"""
        return self.user_preferences.get(key, default)
    
    def learn_pattern(self, pattern_type: str, pattern_data: Dict):
        """Learn and store user patterns"""
        if pattern_type not in self.learned_patterns:
            self.learned_patterns[pattern_type] = []
        
        # Add timestamp to pattern
        pattern_data['learned_at'] = datetime.now().isoformat()
        
        self.learned_patterns[pattern_type].append(pattern_data)
        
        # Keep only last 20 patterns per type
        if len(self.learned_patterns[pattern_type]) > 20:
            self.learned_patterns[pattern_type] = self.learned_patterns[pattern_type][-20:]
        
        self.save_memory()
    
    def get_patterns(self, pattern_type: str) -> List[Dict]:
        """Get learned patterns of specific type"""
        return self.learned_patterns.get(pattern_type, [])
    
    def generate_context_summary(self) -> str:
        """Generate context summary for LLM"""
        context = []
        
        # Add user preferences
        if self.user_preferences:
            context.append("User Preferences:")
            for key, value in self.user_preferences.items():
                context.append(f"- {key}: {value}")
        
        # Add recent patterns
        if self.learned_patterns:
            context.append("\nLearned Patterns:")
            for pattern_type, patterns in self.learned_patterns.items():
                if patterns:
                    latest_pattern = patterns[-1]  # Get most recent
                    context.append(f"- {pattern_type}: {latest_pattern}")
        
        # Add recent conversation context
        recent_conversations = self.get_recent_conversations(3)
        if recent_conversations:
            context.append("\nRecent Context:")
            for conv in recent_conversations:
                context.append(f"User: {conv['user_message'][:100]}...")
                context.append(f"Agent: {conv['agent_response'][:100]}...")
        
        return "\n".join(context) if context else "No previous context available."

class GlobalMemory:
    """Manages global patterns and insights across all users"""
    
    def __init__(self):
        self.memory_file = os.path.join(Config.CACHE_DIR, "global_memory.json")
        self.price_trends = {}
        self.seasonal_patterns = {}
        self.popular_recipes = {}
        self.load_global_memory()
    
    def load_global_memory(self):
        """Load global memory from file"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.price_trends = data.get('price_trends', {})
                    self.seasonal_patterns = data.get('seasonal_patterns', {})
                    self.popular_recipes = data.get('popular_recipes', {})
                logger.info("✅ Global memory loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load global memory: {e}")
    
    def save_global_memory(self):
        """Save global memory to file"""
        try:
            global_data = {
                'last_updated': datetime.now().isoformat(),
                'price_trends': self.price_trends,
                'seasonal_patterns': self.seasonal_patterns,
                'popular_recipes': self.popular_recipes
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(global_data, f, indent=2)
            
            logger.info("✅ Global memory saved")
        except Exception as e:
            logger.error(f"❌ Failed to save global memory: {e}")
    
    def update_price_trend(self, item: str, store: str, price: float):
        """Update price trend data"""
        if item not in self.price_trends:
            self.price_trends[item] = {}
        if store not in self.price_trends[item]:
            self.price_trends[item][store] = []
        
        # Add price point with timestamp
        price_point = {
            'price': price,
            'timestamp': datetime.now().isoformat()
        }
        
        self.price_trends[item][store].append(price_point)
        
        # Keep only last 30 price points per store per item
        if len(self.price_trends[item][store]) > 30:
            self.price_trends[item][store] = self.price_trends[item][store][-30:]
        
        self.save_global_memory()
    
    def get_price_trend(self, item: str, store: str = None) -> Dict:
        """Get price trend for item"""
        if item not in self.price_trends:
            return {}
        
        if store:
            return self.price_trends[item].get(store, [])
        else:
            return self.price_trends[item]
    
    def update_seasonal_pattern(self, item: str, month: int, popularity_score: float):
        """Update seasonal popularity patterns"""
        if item not in self.seasonal_patterns:
            self.seasonal_patterns[item] = {}
        
        self.seasonal_patterns[item][str(month)] = popularity_score
        self.save_global_memory()
    
    def get_seasonal_recommendations(self, current_month: int) -> List[str]:
        """Get seasonally popular items for current month"""
        recommendations = []
        
        for item, months in self.seasonal_patterns.items():
            month_score = months.get(str(current_month), 0)
            if month_score > 0.7:  # High seasonal popularity
                recommendations.append(item)
        
        return recommendations
    
    def update_recipe_popularity(self, recipe_name: str, user_rating: float):
        """Update recipe popularity based on user ratings"""
        if recipe_name not in self.popular_recipes:
            self.popular_recipes[recipe_name] = {
                'total_rating': 0,
                'rating_count': 0,
                'average_rating': 0
            }
        
        recipe_data = self.popular_recipes[recipe_name]
        recipe_data['total_rating'] += user_rating
        recipe_data['rating_count'] += 1
        recipe_data['average_rating'] = recipe_data['total_rating'] / recipe_data['rating_count']
        
        self.save_global_memory()
    
    def get_popular_recipes(self, limit: int = 10) -> List[Dict]:
        """Get most popular recipes"""
        recipes = []
        
        for name, data in self.popular_recipes.items():
            if data['rating_count'] >= 3:  # Minimum 3 ratings
                recipes.append({
                    'name': name,
                    'average_rating': data['average_rating'],
                    'rating_count': data['rating_count']
                })
        
        # Sort by average rating
        recipes.sort(key=lambda x: x['average_rating'], reverse=True)
        
        return recipes[:limit]

# Global memory instance
global_memory = GlobalMemory()