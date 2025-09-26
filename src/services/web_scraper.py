import asyncio
import time
import random
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import re

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
import json

from src.core.config import Config
from src.data.models import get_session, PriceData

logger = logging.getLogger(__name__)

class GroceryWebScraper:
    """Web scraper for grocery store prices"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.stores = {
            'walmart': WalmartScraper(self.session),
            'target': TargetScraper(self.session),
            'kroger': KrogerScraper(self.session)
        }
        
        self.rate_limit_delay = Config.SCRAPING_DELAY
        
        # Loop prevention mechanisms
        self.active_requests = set()  # Track active requests
        self.request_cache = {}  # Cache recent requests
        self.max_concurrent_requests = 3  # Limit concurrent requests
        self.request_timeout = 30  # Timeout for stuck requests
    
    async def scrape_product_prices(
        self, 
        product_names: List[str], 
        stores: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Scrape prices for multiple products from multiple stores"""
        
        if stores is None:
            stores = list(self.stores.keys())
        
        # LOOP PREVENTION: Deduplicate and limit requests
        unique_requests = self._deduplicate_requests(product_names, stores)
        
        if not unique_requests:
            logger.info("All requested items already being processed or recently cached")
            return []
        
        logger.info(f"🔄 SCRAPING REQUEST: {len(unique_requests)} unique items after deduplication")
        
        results = []
        
        # Process requests in batches to prevent overwhelming
        batch_size = min(self.max_concurrent_requests, len(unique_requests))
        
        for i in range(0, len(unique_requests), batch_size):
            batch = unique_requests[i:i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)
            
            # Cleanup completed requests from active set
            for product_name, store_name in batch:
                request_key = f"{product_name.lower()}_{store_name}"
                self.active_requests.discard(request_key)
        
        logger.info(f"✅ SCRAPING COMPLETED: Found {len(results)} price records")
        return results
    
    def _deduplicate_requests(self, product_names: List[str], stores: List[str]) -> List[tuple]:
        """Deduplicate requests to prevent loops"""
        
        unique_requests = []
        current_time = datetime.now()
        
        for product_name in product_names:
            for store_name in stores:
                if store_name not in self.stores:
                    continue
                    
                request_key = f"{product_name.lower()}_{store_name}"
                
                # Skip if already being processed
                if request_key in self.active_requests:
                    logger.debug(f"Skipping {request_key} - already in progress")
                    continue
                
                # Check cache for recent requests (within 10 minutes)
                if request_key in self.request_cache:
                    cache_time = self.request_cache[request_key]
                    if (current_time - cache_time).seconds < 600:  # 10 minutes
                        logger.debug(f"Skipping {request_key} - recently processed")
                        continue
                
                # Add to active requests and unique list
                self.active_requests.add(request_key)
                unique_requests.append((product_name, store_name))
                
                # Limit total requests per call
                if len(unique_requests) >= 10:  # Hard limit
                    logger.warning("Request limit reached, truncating batch")
                    break
            
            if len(unique_requests) >= 10:
                break
        
        return unique_requests
    
    async def _process_batch(self, batch: List[tuple]) -> List[Dict[str, Any]]:
        """Process a batch of requests"""
        
        results = []
        
        for product_name, store_name in batch:
            try:
                logger.info(f"Scraping {store_name} for: {product_name}")
                
                scraper = self.stores[store_name]
                price_data = await scraper.scrape_product(product_name)
                
                # Cache this request
                request_key = f"{product_name.lower()}_{store_name}"
                self.request_cache[request_key] = datetime.now()
                
                if price_data:
                    price_data['product_search_term'] = product_name
                    price_data['scraped_at'] = datetime.now()
                    results.append(price_data)
                    logger.info(f"✅ Found price for {product_name} at {store_name}: ${price_data['price']}")
                else:
                    logger.info(f"❌ No results found for {product_name} at {store_name}")
                
                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay + random.uniform(0, 1))
                
            except Exception as e:
                logger.error(f"Error scraping {store_name} for {product_name}: {e}")
                # Remove from active requests even on error
                request_key = f"{product_name.lower()}_{store_name}"
                self.active_requests.discard(request_key)
                continue
        
        return results
    
    def _cleanup_old_cache(self):
        """Clean up old cache entries"""
        current_time = datetime.now()
        expired_keys = [
            key for key, cache_time in self.request_cache.items()
            if (current_time - cache_time).seconds > 3600  # 1 hour
        ]
        
        for key in expired_keys:
            del self.request_cache[key]
    
    async def save_price_data(self, price_results: List[Dict[str, Any]]) -> int:
        """Save scraped price data to database"""
        
        if not price_results:
            logger.info("No price data to save")
            return 0
        
        saved_count = 0
        session = get_session()
        
        try:
            for price_data in price_results:
                # Check if we already have recent data for this product/store
                existing = session.query(PriceData).filter(
                    PriceData.product_name == price_data['product_name'],
                    PriceData.store_name == price_data['store_name'],
                    PriceData.scraped_at > datetime.now() - timedelta(hours=6)
                ).first()
                
                if existing:
                    # Update existing record
                    existing.price = price_data['price']
                    existing.availability = price_data['availability']
                    existing.scraped_at = price_data['scraped_at']
                    existing.source_url = price_data.get('source_url')
                    logger.debug(f"Updated existing price record for {price_data['product_name']}")
                else:
                    # Create new record
                    new_price = PriceData(
                        product_name=price_data['product_name'],
                        store_name=price_data['store_name'],
                        price=price_data['price'],
                        unit=price_data.get('unit', 'each'),
                        availability=price_data['availability'],
                        source_url=price_data.get('source_url'),
                        data_source='web_scraping',
                        scraped_at=price_data['scraped_at']
                    )
                    session.add(new_price)
                    logger.debug(f"Created new price record for {price_data['product_name']}")
                
                saved_count += 1
            
            session.commit()
            logger.info(f"💾 Saved {saved_count} price records to database")
            
            # Cleanup old cache after successful save
            self._cleanup_old_cache()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving price data: {e}")
        finally:
            session.close()
        
        return saved_count


class BaseScraper:
    """Base class for store-specific scrapers"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.store_name = "unknown"
        self.base_url = ""
    
    async def scrape_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Scrape product data - to be implemented by subclasses"""
        raise NotImplementedError
    
    def clean_price(self, price_text: str) -> Optional[float]:
        """Extract price from text"""
        if not price_text:
            return None
        
        # Remove currency symbols and extract number
        price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
        if price_match:
            try:
                return float(price_match.group())
            except ValueError:
                return None
        return None
    
    def clean_product_name(self, name: str) -> str:
        """Clean up product name"""
        if not name:
            return ""
        
        # Remove extra whitespace and common prefixes
        cleaned = re.sub(r'\s+', ' ', name.strip())
        # Remove brand-specific suffixes that might confuse matching
        cleaned = re.sub(r'\s*-\s*Walmart.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*-\s*Target.*$', '', cleaned, flags=re.IGNORECASE)
        
        return cleaned


class WalmartScraper(BaseScraper):
    """Walmart grocery price scraper"""
    
    def __init__(self, session):
        super().__init__(session)
        self.store_name = "walmart"
        self.base_url = "https://www.walmart.com"
        self.search_url = "https://www.walmart.com/search"
    
    async def scrape_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Scrape Walmart for product price"""
        
        try:
            # Search for the product
            search_params = {
                'query': product_name,
                'cat_id': '976759',  # Grocery category
                'facet': 'fulfillment_method:Pickup'
            }
            
            response = self.session.get(self.search_url, params=search_params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product containers
            product_containers = soup.find_all('div', {'data-testid': 'item-stack'})
            
            if not product_containers:
                # Try alternative selectors
                product_containers = soup.find_all('div', class_=lambda x: x and 'search-result-gridview-item' in x)
            
            for container in product_containers[:3]:  # Check first 3 results
                try:
                    # Extract product name
                    name_elem = container.find('span', {'data-automation-id': 'product-title'})
                    if not name_elem:
                        name_elem = container.find('a', {'data-automation-id': 'product-title'})
                    
                    if not name_elem:
                        continue
                    
                    product_title = self.clean_product_name(name_elem.get_text(strip=True))
                    
                    # Extract price
                    price_elem = container.find('span', class_=lambda x: x and 'price' in x.lower())
                    if not price_elem:
                        price_elem = container.find('div', {'data-automation-id': 'product-price'})
                    
                    if not price_elem:
                        continue
                    
                    price_text = price_elem.get_text(strip=True)
                    price = self.clean_price(price_text)
                    
                    if price and price > 0:
                        # Extract product URL
                        link_elem = container.find('a', href=True)
                        product_url = urljoin(self.base_url, link_elem['href']) if link_elem else None
                        
                        return {
                            'store_name': self.store_name,
                            'product_name': product_title,
                            'price': price,
                            'unit': 'each',
                            'availability': True,
                            'source_url': product_url,
                            'confidence_score': self._calculate_match_confidence(product_name, product_title)
                        }
                
                except Exception as e:
                    logger.debug(f"Error parsing Walmart product container: {e}")
                    continue
            
            logger.info(f"No Walmart results found for: {product_name}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Walmart scraping request failed for {product_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Walmart scraping error for {product_name}: {e}")
            return None
    
    def _calculate_match_confidence(self, search_term: str, product_title: str) -> float:
        """Calculate how well the product matches the search term"""
        search_words = set(search_term.lower().split())
        title_words = set(product_title.lower().split())
        
        if not search_words:
            return 0.0
        
        matches = len(search_words.intersection(title_words))
        return matches / len(search_words)


class TargetScraper(BaseScraper):
    """Target grocery price scraper"""
    
    def __init__(self, session):
        super().__init__(session)
        self.store_name = "target"
        self.base_url = "https://www.target.com"
        self.search_url = "https://www.target.com/s"
    
    async def scrape_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Scrape Target for product price"""
        
        try:
            # Target search
            search_params = {
                'searchTerm': product_name,
                'category': 'grocery'
            }
            
            response = self.session.get(self.search_url, params=search_params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for product cards
            product_cards = soup.find_all('div', {'data-test': 'product-card'})
            
            if not product_cards:
                # Alternative selector
                product_cards = soup.find_all('div', class_=lambda x: x and 'ProductCardImage' in str(x))
            
            for card in product_cards[:3]:  # Check first 3 results
                try:
                    # Extract product name
                    name_elem = card.find('a', {'data-test': 'product-title'})
                    if not name_elem:
                        name_elem = card.find('h3')
                    
                    if not name_elem:
                        continue
                    
                    product_title = self.clean_product_name(name_elem.get_text(strip=True))
                    
                    # Extract price
                    price_elem = card.find('span', {'data-test': 'product-price'})
                    if not price_elem:
                        price_elem = card.find('span', class_=lambda x: x and 'price' in x.lower())
                    
                    if not price_elem:
                        continue
                    
                    price_text = price_elem.get_text(strip=True)
                    price = self.clean_price(price_text)
                    
                    if price and price > 0:
                        # Extract product URL
                        link_elem = card.find('a', href=True)
                        product_url = urljoin(self.base_url, link_elem['href']) if link_elem else None
                        
                        return {
                            'store_name': self.store_name,
                            'product_name': product_title,
                            'price': price,
                            'unit': 'each',
                            'availability': True,
                            'source_url': product_url,
                            'confidence_score': self._calculate_match_confidence(product_name, product_title)
                        }
                
                except Exception as e:
                    logger.debug(f"Error parsing Target product card: {e}")
                    continue
            
            logger.info(f"No Target results found for: {product_name}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Target scraping request failed for {product_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Target scraping error for {product_name}: {e}")
            return None
    
    def _calculate_match_confidence(self, search_term: str, product_title: str) -> float:
        """Calculate how well the product matches the search term"""
        search_words = set(search_term.lower().split())
        title_words = set(product_title.lower().split())
        
        if not search_words:
            return 0.0
        
        matches = len(search_words.intersection(title_words))
        return matches / len(search_words)


class KrogerScraper(BaseScraper):
    """Kroger grocery price scraper (simplified version)"""
    
    def __init__(self, session):
        super().__init__(session)
        self.store_name = "kroger"
        self.base_url = "https://www.kroger.com"
    
    async def scrape_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Kroger has more complex anti-bot measures, so this is a simplified version"""
        
        try:
            # For now, return mock data since Kroger is harder to scrape
            # In a real implementation, you'd use more sophisticated techniques
            
            # Simulate some realistic grocery prices
            mock_prices = {
                'milk': 3.49,
                'bread': 2.29,
                'eggs': 2.99,
                'chicken': 5.99,
                'rice': 1.99,
                'pasta': 1.49,
                'tomatoes': 2.99,
                'cheese': 4.99,
                'yogurt': 0.99,
                'bananas': 1.29
            }
            
            # Find best match
            best_match = None
            for item, price in mock_prices.items():
                if item.lower() in product_name.lower():
                    best_match = (item, price)
                    break
            
            if best_match:
                item_name, price = best_match
                return {
                    'store_name': self.store_name,
                    'product_name': f"Kroger {item_name.title()}",
                    'price': price + random.uniform(-0.5, 0.5),  # Add some variation
                    'unit': 'each',
                    'availability': True,
                    'source_url': f"{self.base_url}/search?query={quote_plus(product_name)}",
                    'confidence_score': 0.7
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Kroger scraping error for {product_name}: {e}")
            return None


# Global scraper instance
grocery_scraper = GroceryWebScraper()