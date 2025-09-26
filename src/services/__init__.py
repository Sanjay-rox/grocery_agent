"""
Services for the grocery AI system

This module contains all the business logic services including web scraping,
price comparison, order management, and external API integrations.
"""

from .web_scraper import grocery_scraper, GroceryWebScraper
from .price_service import price_service, PriceComparisonService, PriceComparison
from .order_service import order_service, OrderManagementService

__all__ = [
    'grocery_scraper',
    'GroceryWebScraper',
    'price_service', 
    'PriceComparisonService',
    'PriceComparison',
    'order_service',
    'OrderManagementService'
]

__version__ = "1.0.0"