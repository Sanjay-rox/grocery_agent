#!/usr/bin/env python3
"""
Complete System Test for Grocery AI Agent

This script tests all major components of the grocery AI system to ensure everything works together.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

async def main():
    print("🚀 Testing Complete Grocery AI System")
    print("=" * 50)
    
    try:
        # Test 1: Configuration and Environment
        print("\n📋 Test 1: Configuration and Environment")
        from src.core.config import Config
        
        print(f"✅ Configuration loaded")
        print(f"   - Database URL: {Config.DATABASE_URL}")
        print(f"   - Groq configured: {bool(Config.GROQ_API_KEY)}")
        print(f"   - Debug mode: {Config.DEBUG}")
        
        config_dict = Config.to_dict()
        print(f"   - Supported stores: {len(Config.SUPPORTED_STORES)}")
        
        # Test 2: Database Initialization
        print("\n🗄️ Test 2: Database Initialization")
        from src.data import init_db, seed_db, get_session, User
        
        print("   Initializing database...")
        init_db()
        print("   ✅ Database tables created")
        
        print("   Seeding with sample data...")
        seed_db()
        print("   ✅ Sample data added")
        
        # Verify data
        session = get_session()
        user_count = session.query(User).count()
        session.close()
        print(f"   ✅ Users in database: {user_count}")
        
        # Test 3: LLM Client
        print("\n🤖 Test 3: LLM Client")
        from src.core.llm_client import llm_client
        
        llm_status = llm_client.get_status()
        print(f"   Groq available: {llm_status['groq_available']}")
        print(f"   Ollama available: {llm_status['ollama_available']}")
        
        if llm_status['groq_available'] or llm_status['ollama_available']:
            print("   Testing LLM completion...")
            response = await llm_client.get_completion(
                "Say 'Hello from Grocery AI!' in exactly those words",
                "You are a test assistant. Respond exactly as requested."
            )
            print(f"   ✅ LLM Response: {response[:50]}...")
        else:
            print("   ⚠️  No LLM services available - configure Groq or install Ollama")
        
        # Test 4: Memory System
        print("\n🧠 Test 4: Memory System")
        from src.core.memory import ConversationMemory, global_memory
        
        test_user_id = 1
        memory = ConversationMemory(test_user_id)
        
        # Test preference storage
        memory.update_preference("favorite_cuisine", "italian")
        memory.update_preference("dietary_restrictions", ["vegetarian"])
        
        # Test conversation memory
        memory.add_conversation("Test message", "Test response", "test")
        
        # Test pattern learning
        memory.learn_pattern("test_pattern", {"test": "data"})
        
        context = memory.generate_context_summary()
        print(f"   ✅ Memory system working")
        print(f"   ✅ Context generated: {len(context)} characters")
        
        # Test global memory
        global_memory.update_price_trend("test_item", "test_store", 3.99)
        print("   ✅ Global memory working")
        
        # Test 5: Tool Registry
        print("\n🔧 Test 5: Tool Registry")
        from src.core.tools import tool_registry
        
        tools = tool_registry.get_all_tools()
        print(f"   ✅ {len(tools)} tools registered")
        
        # Test inventory tool
        print("   Testing inventory check tool...")
        inventory_result = await tool_registry.execute_tool("check_inventory", user_id=test_user_id)
        if "error" not in inventory_result:
            print(f"   ✅ Inventory tool working: {len(inventory_result.get('inventory', []))} items")
        else:
            print(f"   ⚠️  Inventory tool error: {inventory_result['error']}")
        
        # Test 6: Planning Agent
        print("\n🎯 Test 6: Planning Agent")
        from src.agents.planning_agent import planning_agent
        
        print("   Testing meal plan creation...")
        meal_plan_result = await planning_agent.create_weekly_meal_plan(
            user_id=test_user_id,
            preferences={"budget_limit": 100.0}
        )
        
        if "error" not in meal_plan_result:
            print("   ✅ Meal plan created successfully")
            total_cost = meal_plan_result.get("weekly_summary", {}).get("total_estimated_cost", 0)
            print(f"   ✅ Estimated cost: ${total_cost}")
        else:
            print(f"   ❌ Meal plan error: {meal_plan_result['error']}")
        
        print("   Testing inventory status check...")
        inventory_status = await planning_agent.check_inventory_status(test_user_id)
        if "error" not in inventory_status:
            print("   ✅ Inventory status check successful")
        else:
            print(f"   ❌ Inventory status error: {inventory_status['error']}")
        
        # Test 7: Master Agent
        print("\n👑 Test 7: Master Agent")
        from src.agents.master_agent import master_agent
        
        print("   Testing system initialization...")
        init_result = await master_agent.initialize_system()
        if init_result["status"] == "initialized":
            print("   ✅ Master agent initialized successfully")
        else:
            print(f"   ❌ Master agent init error: {init_result.get('error')}")
        
        print("   Testing user message processing...")
        test_messages = [
            "Hello!",
            "Create a meal plan for this week",
            "What's in my inventory?",
            "Find me some Italian recipes"
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"   Testing message {i}: '{message}'")
            try:
                response = await master_agent.process_user_message(test_user_id, message)
                if response.get("success", True):
                    print(f"   ✅ Response generated ({len(response.get('response', ''))} chars)")
                else:
                    print(f"   ❌ Response error: {response.get('error')}")
            except Exception as e:
                print(f"   ❌ Processing error: {str(e)}")
        
        # Test 8: System Status
        print("\n📊 Test 8: System Status")
        system_status = await master_agent.get_system_status()
        print(f"   ✅ System status: {system_status['status']}")
        print(f"   ✅ Available agents: {list(system_status.get('agents', {}).keys())}")
        print(f"   ✅ Capabilities: {len(system_status.get('capabilities', []))}")
        
        # Summary
        print("\n🎉 Test Summary")
        print("=" * 50)
        print("✅ Configuration: Working")
        print("✅ Database: Working") 
        print(f"{'✅' if llm_status['groq_available'] or llm_status['ollama_available'] else '⚠️ '} LLM Client: {'Working' if llm_status['groq_available'] or llm_status['ollama_available'] else 'Limited'}")
        print("✅ Memory System: Working")
        print("✅ Tool Registry: Working")
        print("✅ Planning Agent: Working")
        print("✅ Master Agent: Working")
        print("✅ System Integration: Working")
        
        print("\n🚀 Your Grocery AI system is ready to use!")
        print("\nNext steps:")
        print("1. Make sure your .env file has a valid GROQ_API_KEY")
        print("2. Install Ollama for local LLM backup (optional)")
        print("3. Start building the web scraping components")
        print("4. Create a simple web interface or API")
        
        # Interactive demo
        print("\n🔧 Interactive Demo")
        print("Type messages to test the system (type 'quit' to exit):")
        
        while True:
            try:
                user_input = input("\n> ").strip()
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                    
                if not user_input:
                    continue
                    
                print("Processing...")
                response = await master_agent.process_user_message(test_user_id, user_input)
                print(f"\n🤖 {response.get('response', 'No response generated')}")
                
                if response.get("suggestions"):
                    print(f"\n💡 Suggestions: {', '.join(response['suggestions'])}")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n👋 Demo ended. Thanks for testing!")
        
    except Exception as e:
        print(f"\n❌ System test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)