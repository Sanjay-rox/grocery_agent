"""
Grocery AI Agent System

This module contains all the specialized AI agents for the grocery management system.
Each agent handles specific aspects of grocery and meal planning automation.
"""

from .master_agent import master_agent, MasterAgent
from .planning_agent import planning_agent, PlanningAgent
from .shopping_agent import shopping_agent, ShoppingAgent

# Export main agents for easy import
__all__ = [
    'master_agent',
    'MasterAgent', 
    'planning_agent',
    'PlanningAgent',
    'shopping_agent',
    'ShoppingAgent'
]

# Agent registry for dynamic access
AVAILABLE_AGENTS = {
    'master': master_agent,
    'planning': planning_agent,
    'shopping': shopping_agent
}

def get_agent(agent_name: str):
    """Get agent by name"""
    return AVAILABLE_AGENTS.get(agent_name.lower())

def list_agents():
    """List all available agents"""
    return list(AVAILABLE_AGENTS.keys())

# Version info
__version__ = "1.0.0"
__author__ = "Grocery AI Team"