from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Simple in-memory rate limiting (in production, use Redis)
request_counts = defaultdict(lambda: defaultdict(int))
request_times = defaultdict(lambda: defaultdict(list))

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware class"""
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        
        client_ip = request.client.host
        endpoint = str(request.url.path)
        current_time = time.time()
        
        # Rate limits per endpoint
        rate_limits = {
            "/api/v1/chat/message": {"requests": 30, "window": 60},  # 30 requests per minute
            "/api/v1/shopping/lists": {"requests": 20, "window": 60},
            "/api/v1/shopping/optimize": {"requests": 10, "window": 60},
            "/api/v1/shopping/deals": {"requests": 15, "window": 60},
            "default": {"requests": 100, "window": 60}  # Default limit
        }
        
        # Get rate limit for this endpoint
        limit_config = rate_limits.get(endpoint, rate_limits["default"])
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Clean old requests
        cutoff_time = current_time - window_seconds
        request_times[client_ip][endpoint] = [
            req_time for req_time in request_times[client_ip][endpoint] 
            if req_time > cutoff_time
        ]
        
        # Check rate limit
        current_requests = len(request_times[client_ip][endpoint])
        
        if current_requests >= max_requests:
            logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {max_requests} requests per {window_seconds} seconds",
                    "retry_after": window_seconds
                }
            )
        
        # Record this request
        request_times[client_ip][endpoint].append(current_time)
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add response time header
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        
        return response

# Create middleware instance
rate_limit_middleware = RateLimitMiddleware