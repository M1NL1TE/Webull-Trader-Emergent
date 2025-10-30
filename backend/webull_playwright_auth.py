"""
Webull Playwright Authenticator
Uses browser automation to bypass CAPTCHA and capture authentication tokens
Based on solution from: https://github.com/tedchou12/webull/issues/456
"""

import logging
import asyncio
from typing import Optional, Dict
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class WebullPlaywrightAuth:
    """
    Authenticate with Webull using Playwright browser automation.
    This bypasses CAPTCHA by setting the DID cookie before login.
    """

    LOGIN_URL = (
        "https://passport.webull.com/auth/simple/login?"
        "source=seo-webull-home&hl=en&"
        "redirect_uri=https%3A%2F%2Fwww.webull.com%2Fcenter"
    )

    def __init__(self, username: str, password: str, did_value: str, headless: bool = True):
        self.username = username
        self.password = password
        self.did_value = did_value
        self.headless = headless

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.tokens: Dict[str, Optional[str]] = {
            "Did": did_value,
            "AccessToken": None,
            "RefreshToken": None,
            "UUID": None,
            "TokenExpire": None
        }

    async def start_browser(self):
        """Start Playwright browser with DID cookie set"""
        try:
            self.playwright = await async_playwright().start()
            
            # Use full chromium - let Playwright find the correct path
            self.browser = await self.playwright.chromium.launch(
                headless=True
            )
            
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
            )
            self.page = await self.context.new_page()
            
            # Set DID cookie BEFORE navigating to login - this bypasses CAPTCHA
            await self.page.context.add_cookies([{
                'name': 'web_did',
                'value': self.did_value,
                'domain': '.webull.com',
                'path': '/',
                'httpOnly': False,
                'secure': True
            }])
            
            logger.info("Playwright browser started with DID cookie")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    async def close_browser(self):
        """Close browser and playwright"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def login(self, timeout: int = 60000):
        """
        Automate login process
        timeout: milliseconds to wait for elements (default 60s)
        """
        if not self.page:
            raise Exception("Browser not started. Call start_browser() first.")

        try:
            logger.info("Navigating to login page...")
            await self.page.goto(self.LOGIN_URL, timeout=timeout, wait_until='domcontentloaded')
            logger.info("Page loaded, waiting for stability...")
            
            # Wait a bit for page to stabilize
            await self.page.wait_for_timeout(2000)

            # Click "Email Login" if present
            try:
                await self.page.click('span:has-text("Email Login")', timeout=5000)
                logger.info("Clicked Email Login")
                await self.page.wait_for_timeout(1000)
            except PlaywrightTimeout:
                logger.info("Email Login button not found, continuing...")

            # Fill username
            logger.info("Filling username...")
            username_selector = 'input[class*="csr"]'
            await self.page.wait_for_selector(username_selector, timeout=15000)
            await self.page.fill(username_selector, self.username)
            await self.page.wait_for_timeout(500)

            # Fill password
            logger.info("Filling password...")
            await self.page.fill('input[type="password"]', self.password)
            await self.page.wait_for_timeout(500)

            # Click login button
            logger.info("Clicking login button...")
            await self.page.click('button:has-text("Log In")')

            # Wait for redirect to trading page or center
            logger.info("Waiting for successful login redirect...")
            try:
                await self.page.wait_for_url("**/center", timeout=timeout)
                logger.info("Login successful - redirected to center page")
                return True
            except PlaywrightTimeout:
                # Check if we're on trade page instead
                current_url = self.page.url
                logger.info(f"Checking current URL: {current_url}")
                if "app.webull.com" in current_url or "webull.com/center" in current_url:
                    logger.info("Login successful - on Webull page")
                    return True
                else:
                    logger.error(f"Login may have failed - current URL: {current_url}")
                    return False

        except PlaywrightTimeout as e:
            logger.error(f"Timeout during login: {e}")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def capture_tokens(self, timeout: int = 60):
        """
        Intercept network responses to extract authentication tokens
        timeout: seconds to wait for tokens
        """
        if not self.context:
            raise Exception("Browser context not available")

        logger.info("Setting up network interception to capture tokens...")

        def response_handler(response):
            """Handle network responses to extract tokens"""
            url = response.url
            
            # Check for login response
            if "passport/login" in url or "/api/user/v1/login/account" in url:
                try:
                    data = response.json()
                    if data.get("accessToken") and not self.tokens["AccessToken"]:
                        self.tokens["AccessToken"] = data.get("accessToken")
                        self.tokens["RefreshToken"] = data.get("refreshToken")
                        self.tokens["UUID"] = data.get("uuid")
                        self.tokens["TokenExpire"] = data.get("tokenExpireTime", "2099-01-01T00:00:00.000+0000")
                        logger.info("✅ Captured authentication tokens!")
                except Exception as e:
                    logger.debug(f"Could not parse response from {url}: {e}")

        # Start listening to responses
        self.context.on("response", response_handler)

        # Wait for tokens to be captured
        logger.info(f"Waiting up to {timeout}s for tokens...")
        elapsed = 0
        poll_interval = 1000  # 1 second
        
        while elapsed < (timeout * 1000) and not self.tokens["AccessToken"]:
            await self.page.wait_for_timeout(poll_interval)
            elapsed += poll_interval

        if self.tokens["AccessToken"]:
            logger.info("✅ All tokens successfully captured")
            return self.tokens
        else:
            logger.error("❌ Timeout: AccessToken not captured")
            return None

    async def authenticate(self, login_timeout: int = 60, capture_timeout: int = 60):
        """
        Complete authentication flow: start browser, login, capture tokens, close
        
        Args:
            login_timeout: seconds to wait for login (default 60)
            capture_timeout: seconds to wait for token capture (default 60)
            
        Returns:
            dict with tokens or None if failed
        """
        try:
            # Start browser
            if not await self.start_browser():
                return None

            # Set up network interception BEFORE login
            logger.info("Setting up network interception to capture tokens...")
            
            async def response_handler(response):
                """Handle network responses to extract tokens"""
                url = response.url
                
                # Check for login response
                if "passport/login" in url or "/api/user/v1/login/account" in url:
                    try:
                        data = await response.json()
                        if data.get("accessToken") and not self.tokens["AccessToken"]:
                            self.tokens["AccessToken"] = data.get("accessToken")
                            self.tokens["RefreshToken"] = data.get("refreshToken")
                            self.tokens["UUID"] = data.get("uuid")
                            self.tokens["TokenExpire"] = data.get("tokenExpireTime", "2099-01-01T00:00:00.000+0000")
                            logger.info("✅ Captured authentication tokens!")
                    except Exception as e:
                        logger.debug(f"Could not parse response from {url}: {e}")

            # Start listening to responses BEFORE login
            self.context.on("response", lambda response: asyncio.create_task(response_handler(response)))

            # Perform login (convert seconds to milliseconds)
            if not await self.login(timeout=login_timeout * 1000):
                await self.close_browser()
                return None

            # Wait a bit for tokens after successful login
            logger.info(f"Waiting up to {capture_timeout}s for tokens...")
            elapsed = 0
            poll_interval = 1000  # 1 second
            
            while elapsed < (capture_timeout * 1000) and not self.tokens["AccessToken"]:
                await self.page.wait_for_timeout(poll_interval)
                elapsed += poll_interval

            if self.tokens["AccessToken"]:
                logger.info("✅ All tokens successfully captured")
            else:
                logger.error("❌ Timeout: AccessToken not captured")
            
            # Close browser
            await self.close_browser()
            
            return self.tokens if self.tokens["AccessToken"] else None

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            await self.close_browser()
            return None


async def authenticate_webull_playwright(username: str, password: str, did: str) -> Optional[Dict]:
    """
    Helper function to authenticate with Webull using Playwright
    
    Args:
        username: Webull username (email)
        password: Webull password
        did: Device ID (32-char hex string)
        
    Returns:
        dict with AccessToken, RefreshToken, UUID, Did, TokenExpire
    """
    authenticator = WebullPlaywrightAuth(
        username=username,
        password=password,
        did_value=did,
        headless=True  # Set to False to see browser
    )
    
    return await authenticator.authenticate(login_timeout=60, capture_timeout=60)
