import time
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Query, Request
from scraper import scrape_amazon


app = FastAPI(
    title="Stealth Amazon Scraper API",
    description="High-speed scraping API equipped with Camoufox harvesting and IP-based rate limiting.",
    version="1.1.0"
)

# ---------------------------------------------------------
# 🎛️ RATE LIMITER CONFIGURATIONS
# ---------------------------------------------------------
RATE_LIMIT_ENABLED = True  # Set to False to completely disable rate limiting
MAX_REQUESTS = 20          # Number of allowed searches
WINDOW_SECONDS = 86400     # 24 hours in seconds (60s * 60m * 24h)

# Memory storage structure: { "127.0.0.1": [timestamp1, timestamp2, ...] }
ip_request_history = defaultdict(list)
# ---------------------------------------------------------

@app.get("/search")
async def search_amazon_endpoint(
    request: Request,  # Injected to intercept the incoming device IP address
    q: str = Query(..., description="The product or keyword to search on Amazon"),
    domain: str = Query("amazon.in", description="The specific Amazon domain to target")
):
    """
    Search Amazon dynamically with optional, toggleable rolling IP rate limiting.
    """
    # 1. Enforce Rate Limiting if toggled ON
    if RATE_LIMIT_ENABLED:
        # Get the unique identifier of the calling device
        client_ip = request.client.host
        current_time = time.time()
        
        # Pull up the IP history and filter out logs older than 24 hours
        active_timestamps = [
            t for t in ip_request_history[client_ip] 
            if current_time - t < WINDOW_SECONDS
        ]
        ip_request_history[client_ip] = active_timestamps
        
        # Check if the remaining active request count breaches the ceiling
        if len(active_timestamps) >= MAX_REQUESTS:
            # Calculate remaining hours/minutes until the oldest request clears out
            oldest_request_age = active_timestamps[0]
            time_to_wait = WINDOW_SECONDS - (current_time - oldest_request_age)
            hours_left = int(time_to_wait // 3600)
            minutes_left = int((time_to_wait % 3600) // 60)
            
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Max {MAX_REQUESTS} searches per 24 hours. "
                       f"Try again in {hours_left}h {minutes_left}m."
            )
        
        # Log the current successful hit timestamp
        ip_request_history[client_ip].append(current_time)

    # 2. Execute Scraping Payload
    clean_query = q.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Search query 'q' cannot be empty.")

    results = await scrape_amazon(query=clean_query, domain=domain)

    if isinstance(results, dict) and "error" in results:
        raise HTTPException(status_code=500, detail=results["error"])

    return {
        "status": "success",
        "target_domain": domain,
        "search_query": clean_query,
        "count": len(results),
        "rate_limiting_active": RATE_LIMIT_ENABLED,
        "results": results
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}