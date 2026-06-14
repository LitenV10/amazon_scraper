import json
import logging
import asyncio
from camoufox.async_api import AsyncCamoufox

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SESSION_FILE = "session.json"

async def refresh_session(base_url="https://www.amazon.in/"):
    """
    Spins up a stealth AsyncCamoufox browser instance to harvest session tokens.
    """
    logger.info("Launching stealth Camoufox browser (Async)...")
    
    # Using the Async API now
    async with AsyncCamoufox(
        headless=True,
        humanize=True,  
    ) as browser:
        
        context = await browser.new_context()
        page = await context.new_page()
        
        logger.info(f"Navigating to {base_url} to harvest session tokens...")
        try:
            # We must await all Playwright actions
            await page.goto(base_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            
            logger.info("Extracting valid session data...")
            
            playwright_cookies = await context.cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in playwright_cookies}
            
            user_agent = await page.evaluate("navigator.userAgent")
            device_memory = await page.evaluate("navigator.deviceMemory || 8")
            hardware_concurrency = await page.evaluate("navigator.hardwareConcurrency || 4")
            
            headers_dict = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Device-Memory": str(device_memory),
                "Hardware-Concurrency": str(hardware_concurrency),
            }
            
            session_data = {
                "headers": headers_dict,
                "cookies": cookies_dict
            }
            
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=4, ensure_ascii=False)
                
            logger.info(f"Successfully saved fresh session tokens to {SESSION_FILE}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate session tokens: {str(e)}")
            return False

if __name__ == "__main__":
    # Test execution locally
    success = asyncio.run(refresh_session())
    if success:
        print("\nSession initialization complete! Check your local 'session.json'.")
    else:
        print("\nFailed to initialize session.")