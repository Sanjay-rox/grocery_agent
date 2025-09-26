import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import statistics

from src.data.models import get_session, PriceData, User
from src.services.web_scraper import grocery_scraper
from src.core.memory import global_memory

logger = logging.getLogger(__name__)

@dataclass
class PriceComparison:
    """Data class for price comparison results"""
    product_name: str
    cheapest_price: float
    cheapest_store: str
    average_price: float
    price_range: Tuple[float, float]  # (min, max)
    stores_compared: int
    savings_opportunity: float  # How much you save vs most expensive
    price_by_store: Dict[str, Dict[str, Any]]
    confidence: str  # "high", "medium", "low"
    last_updated: datetime

class PriceComparisonService:
    """Service for comparing prices across stores and managing price data"""
    
    def __init__(self):
        self.scraper = grocery_scraper
        self.cache_duration_hours = 6  # How long to consider price data fresh
    
    async def compare_prices(
        self, 
        product_names: List[str], 
        stores: List[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, PriceComparison]:
        """Compare prices for products across stores"""
        
        logger.info(f"Comparing prices for {len(product_names)} products")
        
        comparisons = {}
        
        for product_name in product_names:
            try:
                comparison = await self._compare_single_product(
                    product_name, 
                    stores, 
                    force_refresh
                )
                if comparison:
                    comparisons[product_name] = comparison
            except Exception as e:
                logger.error(f"Error comparing prices for {product_name}: {e}")
                continue
        
        return comparisons
    
    async def _compare_single_product(
        self, 
        product_name: str, 
        stores: List[str] = None,
        force_refresh: bool = False
    ) -> Optional[PriceComparison]:
        """Compare prices for a single product"""
        
        # Get existing price data
        existing_prices = await self._get_cached_prices(product_name, stores)
        
        # Check if we need fresh data
        need_refresh = force_refresh or self._needs_price_refresh(existing_prices)
        
        if need_refresh:
            logger.info(f"Refreshing price data for: {product_name}")
            await self._refresh_price_data(product_name, stores)
            existing_prices = await self._get_cached_prices(product_name, stores)
        
        if not existing_prices:
            logger.warning(f"No price data available for: {product_name}")
            return None
        
        return self._create_price_comparison(product_name, existing_prices)
    
    async def _get_cached_prices(
        self, 
        product_name: str, 
        stores: List[str] = None
    ) -> List[PriceData]:
        """Get cached price data from database"""
        
        session = get_session()
        
        try:
            query = session.query(PriceData).filter(
                PriceData.product_name.ilike(f"%{product_name}%"),
                PriceData.availability == True,
                PriceData.scraped_at > datetime.now() - timedelta(hours=self.cache_duration_hours)
            )
            
            if stores:
                query = query.filter(PriceData.store_name.in_(stores))
            
            prices = query.all()
            return prices
            
        finally:
            session.close()
    
    def _needs_price_refresh(self, existing_prices: List[PriceData]) -> bool:
        """Check if price data needs refreshing"""
        
        if not existing_prices:
            return True
        
        # Check if we have recent data from multiple stores
        recent_stores = set()
        cutoff_time = datetime.now() - timedelta(hours=self.cache_duration_hours)
        
        for price in existing_prices:
            if price.scraped_at > cutoff_time:
                recent_stores.add(price.store_name)
        
        # We want data from at least 2 stores
        return len(recent_stores) < 2
    
    async def _refresh_price_data(self, product_name: str, stores: List[str] = None):
        """Refresh price data by scraping"""
        
        if stores is None:
            stores = ['walmart', 'target', 'kroger']
        
        try:
            # Scrape fresh data
            price_results = await self.scraper.scrape_product_prices([product_name], stores)
            
            # Save to database
            if price_results:
                saved_count = await self.scraper.save_price_data(price_results)
                logger.info(f"Refreshed {saved_count} price records for {product_name}")
            
        except Exception as e:
            logger.error(f"Error refreshing price data for {product_name}: {e}")
    
    def _create_price_comparison(
        self, 
        product_name: str, 
        price_data: List[PriceData]
    ) -> PriceComparison:
        """Create price comparison from price data"""
        
        if not price_data:
            return None
        
        # Group by store and get best price for each store
        store_prices = {}
        all_prices = []
        
        for price in price_data:
            store = price.store_name
            if store not in store_prices or price.price < store_prices[store]['price']:
                store_prices[store] = {
                    'price': price.price,
                    'product_name': price.product_name,
                    'unit': price.unit,
                    'source_url': price.source_url,
                    'last_updated': price.scraped_at
                }
            all_prices.append(price.price)
        
        # Calculate statistics
        cheapest_price = min(all_prices)
        most_expensive = max(all_prices)
        average_price = statistics.mean(all_prices)
        
        # Find cheapest store
        cheapest_store = None
        for store, data in store_prices.items():
            if data['price'] == cheapest_price:
                cheapest_store = store
                break
        
        # Calculate confidence based on data recency and store coverage
        confidence = self._calculate_confidence(price_data, len(store_prices))
        
        # Calculate savings
        savings = most_expensive - cheapest_price
        
        return PriceComparison(
            product_name=product_name,
            cheapest_price=cheapest_price,
            cheapest_store=cheapest_store,
            average_price=round(average_price, 2),
            price_range=(cheapest_price, most_expensive),
            stores_compared=len(store_prices),
            savings_opportunity=round(savings, 2),
            price_by_store=store_prices,
            confidence=confidence,
            last_updated=max(p.scraped_at for p in price_data)
        )
    
    def _calculate_confidence(self, price_data: List[PriceData], store_count: int) -> str:
        """Calculate confidence level for price comparison"""
        
        # Check data recency
        recent_count = sum(1 for p in price_data if p.scraped_at > datetime.now() - timedelta(hours=2))
        recency_score = recent_count / len(price_data)
        
        # Check store coverage
        coverage_score = min(store_count / 3, 1.0)  # Ideal is 3+ stores
        
        # Overall confidence
        confidence_score = (recency_score + coverage_score) / 2
        
        if confidence_score >= 0.8:
            return "high"
        elif confidence_score >= 0.5:
            return "medium"
        else:
            return "low"
    
    async def get_best_deals(
        self, 
        product_names: List[str], 
        min_savings: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Find products with significant savings opportunities"""
        
        comparisons = await self.compare_prices(product_names)
        
        deals = []
        for product_name, comparison in comparisons.items():
            if comparison.savings_opportunity >= min_savings:
                deals.append({
                    'product_name': product_name,
                    'cheapest_store': comparison.cheapest_store,
                    'cheapest_price': comparison.cheapest_price,
                    'savings': comparison.savings_opportunity,
                    'confidence': comparison.confidence
                })
        
        # Sort by savings amount
        deals.sort(key=lambda x: x['savings'], reverse=True)
        
        return deals
    
    async def get_shopping_list_comparison(
        self, 
        shopping_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare total cost of shopping list across stores"""
        
        product_names = [item['item'] for item in shopping_list]
        comparisons = await self.compare_prices(product_names)
        
        # Calculate total cost by store
        store_totals = {}
        items_found = 0
        total_savings = 0
        
        for item in shopping_list:
            product_name = item['item']
            quantity = item.get('quantity', 1)
            
            if product_name in comparisons:
                comparison = comparisons[product_name]
                items_found += 1
                total_savings += comparison.savings_opportunity * quantity
                
                for store, price_data in comparison.price_by_store.items():
                    if store not in store_totals:
                        store_totals[store] = {
                            'total': 0,
                            'items': 0,
                            'confidence_scores': []
                        }
                    
                    store_totals[store]['total'] += price_data['price'] * quantity
                    store_totals[store]['items'] += 1
                    
                    # Add confidence score for averaging
                    confidence_value = {'high': 1.0, 'medium': 0.7, 'low': 0.4}[comparison.confidence]
                    store_totals[store]['confidence_scores'].append(confidence_value)
        
        # Find best store overall
        best_store = None
        best_total = float('inf')
        
        for store, data in store_totals.items():
            if data['total'] < best_total and data['items'] >= items_found * 0.7:  # At least 70% coverage
                best_total = data['total']
                best_store = store
        
        # Calculate average confidence by store
        for store_data in store_totals.values():
            if store_data['confidence_scores']:
                avg_confidence = statistics.mean(store_data['confidence_scores'])
                if avg_confidence >= 0.8:
                    store_data['confidence'] = 'high'
                elif avg_confidence >= 0.6:
                    store_data['confidence'] = 'medium'
                else:
                    store_data['confidence'] = 'low'
            else:
                store_data['confidence'] = 'low'
        
        return {
            'best_store': best_store,
            'best_total': round(best_total, 2) if best_store else None,
            'store_comparisons': {
                store: {
                    'total': round(data['total'], 2),
                    'items_found': data['items'],
                    'confidence': data['confidence']
                }
                for store, data in store_totals.items()
            },
            'items_compared': items_found,
            'total_items': len(shopping_list),
            'potential_savings': round(total_savings, 2),
            'coverage': round(items_found / len(shopping_list) * 100, 1)
        }
    
    async def track_price_trends(self, product_name: str, days: int = 30) -> Dict[str, Any]:
        """Track price trends for a product over time"""
        
        session = get_session()
        
        try:
            # Get historical price data
            prices = session.query(PriceData).filter(
                PriceData.product_name.ilike(f"%{product_name}%"),
                PriceData.scraped_at > datetime.now() - timedelta(days=days)
            ).order_by(PriceData.scraped_at).all()
            
            if not prices:
                return {'error': 'No price history available'}
            
            # Group by store and calculate trends
            store_trends = {}
            
            for price in prices:
                store = price.store_name
                if store not in store_trends:
                    store_trends[store] = []
                
                store_trends[store].append({
                    'price': price.price,
                    'date': price.scraped_at.isoformat(),
                    'product_name': price.product_name
                })
            
            # Calculate trend direction for each store
            trend_analysis = {}
            
            for store, price_history in store_trends.items():
                if len(price_history) >= 2:
                    first_price = price_history[0]['price']
                    last_price = price_history[-1]['price']
                    change = last_price - first_price
                    change_percent = (change / first_price) * 100
                    
                    if change_percent > 5:
                        trend = 'increasing'
                    elif change_percent < -5:
                        trend = 'decreasing'
                    else:
                        trend = 'stable'
                    
                    trend_analysis[store] = {
                        'trend': trend,
                        'change_amount': round(change, 2),
                        'change_percent': round(change_percent, 1),
                        'first_price': first_price,
                        'last_price': last_price,
                        'data_points': len(price_history)
                    }
            
            return {
                'product_name': product_name,
                'period_days': days,
                'stores_tracked': list(store_trends.keys()),
                'trend_analysis': trend_analysis,
                'price_history': store_trends,
                'total_data_points': len(prices)
            }
            
        finally:
            session.close()

    async def get_price_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        """Get price drop alerts for user's watchlist items"""
        
        # This would integrate with user's watchlist/favorites
        # For now, return empty list as placeholder
        return []
    
    async def find_substitutes(self, product_name: str, max_price_diff: float = 1.0) -> List[Dict[str, Any]]:
        """Find cheaper substitute products"""
        
        session = get_session()
        
        try:
            # Get current product price
            current_prices = session.query(PriceData).filter(
                PriceData.product_name.ilike(f"%{product_name}%"),
                PriceData.availability == True
            ).all()
            
            if not current_prices:
                return []
            
            avg_current_price = statistics.mean(p.price for p in current_prices)
            
            # Find similar products that are cheaper
            # This is a simplified approach - in reality you'd use more sophisticated matching
            keywords = product_name.lower().split()
            main_keyword = keywords[0] if keywords else product_name
            
            substitute_prices = session.query(PriceData).filter(
                PriceData.product_name.ilike(f"%{main_keyword}%"),
                PriceData.product_name != product_name,
                PriceData.price < avg_current_price + max_price_diff,
                PriceData.availability == True,
                PriceData.scraped_at > datetime.now() - timedelta(hours=24)
            ).limit(10).all()
            
            substitutes = []
            for sub in substitute_prices:
                savings = avg_current_price - sub.price
                if savings > 0:
                    substitutes.append({
                        'product_name': sub.product_name,
                        'store': sub.store_name,
                        'price': sub.price,
                        'savings': round(savings, 2),
                        'savings_percent': round((savings / avg_current_price) * 100, 1)
                    })
            
            # Sort by savings
            substitutes.sort(key=lambda x: x['savings'], reverse=True)
            
            return substitutes[:5]  # Return top 5 substitutes
            
        finally:
            session.close()

# Global price service instance
price_service = PriceComparisonService()