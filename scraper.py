import httpx
import asyncio
import json
import logging
from bs4 import BeautifulSoup
from cookie_fetcher import refresh_session, SESSION_FILE

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_session():
    """Reads the saved session headers and cookies from disk."""
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Session file '{SESSION_FILE}' not found.")
        return None

async def scrape_amazon(query: str, domain: str = "amazon.in", retrying: bool = False):
    """
    Fetches product data from Amazon using saved stealth sessions.
    Accepts a custom domain to dynamically adjust the regional storefront.
    """
    # Construct the exact regional target links
    search_url = f"https://www.{domain}/s?k={query.replace(' ', '+')}"
    base_url = f"https://www.{domain}/"
    
    session_data = load_session()

    # Self-heal step 1: No session file exists yet
    if not session_data:
        logger.info("No session found. Initializing new session...")
        if await refresh_session(base_url=base_url):
            session_data = load_session()
        else:
            return {"error": "Failed to generate initial browser session."}

    headers = session_data.get("headers", {})
    cookies = session_data.get("cookies", {})

    logger.info(f"Fetching results from {domain} for: '{query}'")

    async with httpx.AsyncClient(http2=True, timeout=15.0) as client:
        try:
            response = await client.get(search_url, headers=headers, cookies=cookies)
            
            # Catch basic anti-bot blockers or unexpected redirects
            is_blocked = response.status_code == 503 or "captcha" in response.text.lower() or "bot check" in response.text.lower()
            
            if is_blocked:
                if retrying:
                    logger.error("Got blocked again even after refreshing session.")
                    return {"error": "Amazon blocked the request permanently."}
                
                logger.warning("Amazon blocked the request! Triggering Camoufox to harvest a new session...")
                success = await refresh_session(base_url=base_url) 
                if success:
                    # Retry once recursively with the new cookie state
                    return await scrape_amazon(query, domain, retrying=True)
                else:
                    return {"error": "Failed to refresh session after being blocked."}

            if response.status_code != 200:
                return {"error": f"Failed request. Status Code: {response.status_code}"}

            logger.info("Request successful. Parsing HTML...")
            return parse_amazon_html(response.text, domain)

        except Exception as e:
            logger.error(f"HTTPX Request Failed: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}

def parse_amazon_html(html_content: str, domain: str):
    """Extracts product data from Amazon search HTML based on target domain."""
    soup = BeautifulSoup(html_content, "html.parser")
    products = []

    items = soup.find_all("div", {"data-component-type": "s-search-result"})

    for item in items:
        # Title
        title_el = item.find("h2", class_="a-size-medium") or item.find("h2", class_="a-size-base-plus")
        title = title_el.text.strip() if title_el else None

        # Price
        price_el = item.find("span", class_="a-price-whole")
        price = price_el.text.strip().replace(",", "") if price_el else None

        # Link
        link_el = item.find("a", class_="a-link-normal s-no-outline")
        link = f"https://www.{domain}{link_el['href']}" if link_el else None

        # Image
        img_el = item.find("img", class_="s-image")
        image = img_el["src"] if img_el else None

        if title and price:
            # Match currency sign representation based on domain type
            currency = "$" if "com" in domain else "₹"
            products.append({
                "title": title,
                "price": f"{currency}{price}",
                "link": link,
                "image": image,
                "source": f"Amazon ({domain})"
            })

    logger.info(f"Successfully parsed {len(products)} products.")
    return products