from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
from my_webull import my_webull, my_paper_webull
from webull_playwright_auth import authenticate_webull_playwright
import talib
import numpy as np
import pandas as pd
import math
import hashlib
from trading_bot_service import run_trading_bot, get_bot_status, initialize_notifications, bot_state

# Set Playwright browser path BEFORE any playwright imports
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')
load_dotenv(ROOT_DIR / '.env.security')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Collections
sessions_collection = db['sessions']
settings_collection = db['settings']
entry_signals_collection = db['entry_signals']  # New collection for persisting entry signals
position_tracking_collection = db['position_tracking']  # New collection for tracking positions with trailing stops

# App password from environment
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'changeme123')

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global webull instance (will be set after login)
wb_instance = None
is_paper_trading = True

# Trading bot task
trading_bot_task = None

# Function to ensure Playwright browsers are installed
def ensure_playwright_browsers(force=False):
    """Check and install Playwright browsers if missing or wrong version"""
    import subprocess
    from pathlib import Path
    
    # Check if chromium browser exists (build 1187 for Playwright 1.55.0)
    browser_path = Path('/pw-browsers/chromium_headless_shell-1187/chrome-linux/headless_shell')
    wrong_version = Path('/pw-browsers/chromium_headless_shell-1194')
    
    needs_install = False
    
    # Check if wrong version is installed
    if wrong_version.exists() and not browser_path.exists():
        logger.warning("⚠️ WRONG VERSION detected: Build 1194 found, need 1187. Removing and reinstalling...")
        try:
            import shutil
            shutil.rmtree(str(wrong_version))
            shutil.rmtree('/pw-browsers/chromium-1194', ignore_errors=True)
            logger.info("Removed wrong browser version (1194)")
        except Exception as e:
            logger.error(f"Failed to remove wrong version: {e}")
        needs_install = True
    elif not browser_path.exists():
        logger.warning("⚠️ Playwright browsers (build 1187) not found. Installing...")
        needs_install = True
    elif force:
        logger.info("🔄 Force reinstall requested")
        needs_install = True
    
    if needs_install:
        try:
            # Install chromium browser with --force to ensure correct version
            # Use sys.executable to ensure we use the same Python interpreter
            import sys
            logger.info("Installing Playwright browsers (build 1187)...")
            result = subprocess.run(
                [sys.executable, '-m', 'playwright', 'install', 'chromium', '--force'],
                cwd='/app/backend',
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                # Verify correct version was installed
                if browser_path.exists():
                    logger.info("✅ Playwright browsers (build 1187) installed successfully")
                    return True
                else:
                    logger.error(f"⚠️ Playwright install succeeded but build 1187 not found!")
                    return False
            else:
                logger.error(f"❌ Failed to install Playwright browsers: {result.stderr[:500]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Playwright browser installation timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error installing Playwright browsers: {e}")
            return False
    else:
        logger.info("✅ Playwright browsers (build 1187) already installed")
        return True

# Initialize Twilio on startup
@app.on_event("startup")
async def startup_event():
    # Ensure Playwright browsers are installed
    ensure_playwright_browsers()
    
    initialize_notifications()
    logger.info("Application startup complete")
    
    # Check if auto-trading is enabled and start bot
    asyncio.create_task(check_and_start_bot())

async def check_and_start_bot():
    """Check if auto-trading is enabled and start bot if needed"""
    global trading_bot_task
    
    # Wait a bit for everything to initialize
    await asyncio.sleep(5)
    
    try:
        # Check settings
        settings = await db.settings.find_one({'user': 'default'}, {"_id": 0})
        
        if settings and settings.get('auto_trading', False):
            logger.info("Auto-trading is enabled - checking for existing session...")
            
            # Check if there's a valid session
            session_data = await db.sessions.find_one({'user': 'default'})
            
            if session_data and not bot_state.running:
                logger.info("🚀 Auto-starting trading bot on startup (silent mode - no email notifications)")
                
                wb = get_webull_instance(session_data.get('is_paper', True))
                wb.api_login(
                    access_token=session_data['access_token'],
                    refresh_token=session_data['refresh_token'],
                    token_expire=session_data['token_expire'],
                    uuid=session_data['uuid']
                )
                
                # CRITICAL: Restore trade token for bot order placement
                if 'trade_token' in session_data and session_data['trade_token']:
                    wb._trade_token = session_data['trade_token']
                    logger.info("✅ Bot startup: Trade token restored")
                else:
                    logger.warning("⚠️ Bot startup: No trade token - bot orders will fail!")
                
                if session_data.get('is_paper', True):
                    wb.get_account_id()
                
                trading_bot_task = asyncio.create_task(run_trading_bot(wb, settings))
                logger.info("✅ Trading bot auto-started successfully (NO EMAIL SENT)")
            else:
                logger.info("No valid session found for auto-start")
    except Exception as e:
        logger.error(f"Error auto-starting bot: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== MODELS =====================

class AppPasswordRequest(BaseModel):
    password: str

class AppPasswordResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str
    trade_pin: str
    is_paper: bool = True
    device_id: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[str] = None

class TradeRequest(BaseModel):
    symbol: str
    option_type: str  # 'call' or 'put'
    trade_grade: str

class SellPositionRequest(BaseModel):
    ticker_id: int

class SettingsUpdate(BaseModel):
    auto_trading: Optional[bool] = None
    profit_percentage: Optional[float] = None
    loss_percentage: Optional[float] = None
    sms_notifications: Optional[bool] = None

# ===================== HELPER FUNCTIONS =====================

def get_webull_instance(is_paper: bool = True):
    """Get or create webull instance"""
    global wb_instance, is_paper_trading
    if wb_instance is None or is_paper_trading != is_paper:
        wb_instance = my_paper_webull() if is_paper else my_webull()
        is_paper_trading = is_paper
    return wb_instance

async def save_session(session_data: dict):
    """Save Webull session to database"""
    session_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one(
        {'session_type': 'webull'},
        {'$set': session_data},
        upsert=True
    )

async def get_session():
    """Retrieve Webull session from database"""
    return await db.sessions.find_one({'session_type': 'webull'})

def get_rsi_grade(df):
    """Calculate RSI grade from dataframe"""
    rsi = talib.RSI(df['close'])
    df_last = df.tail(1)
    if rsi.iloc[-1] <= 30 and df_last['close'].iloc[-1] > df_last['open'].iloc[-1]:
        return 'A+'
    if rsi.iloc[-1] >= 70 and df_last['close'].iloc[-1] < df_last['open'].iloc[-1]:
        return 'A+'
    if (rsi.iloc[-2] > rsi.iloc[-1] and rsi.iloc[-1] < 30) or (rsi.iloc[-2] < rsi.iloc[-1] and rsi.iloc[-1] > 70):
        return 'A'
    return 'D'

def get_macd_grade(df):
    """Calculate MACD grade from dataframe"""
    macd, macdsignal, macdhist = talib.MACD(df['close'])
    if macd.iloc[-1] > macdsignal.iloc[-1] and macd.iloc[-2] < macdsignal.iloc[-2]:
        return 'A+'
    return 'D'

def filter_options(wb, symbol, option_type):
    """Filter options based on volume and strike price"""
    current_date = datetime.now().date()
    current_day = current_date.weekday()
    
    min_days = 3 if current_day == 4 else 1
    min_date = current_date + timedelta(days=min_days)
    
    expiration_dates = wb.get_options_expiration_dates(symbol)
    expiration_dates = [date for date in expiration_dates if datetime.strptime(date['date'], '%Y-%m-%d').date() >= min_date]
    
    if not expiration_dates:
        return []
    
    expiration_date = expiration_dates[0]['date']
    current_price = float(wb.get_quote(stock=symbol)['close'])
    rounded_price = round(current_price)
    
    if option_type == 'call':
        options = wb.get_options(stock=symbol, count=-1, direction='call', expireDate=expiration_date)
        options = [opt for opt in options if rounded_price <= float(opt['strikePrice']) <= rounded_price + 5]
        options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['call']['tickerId'])['data'][0]['volume']), reverse=True)
        return options
    else:
        options = wb.get_options(stock=symbol, count=-1, direction='put', expireDate=expiration_date)
        options = [opt for opt in options if rounded_price - 5 <= float(opt['strikePrice']) <= rounded_price]
        options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['put']['tickerId'])['data'][0]['volume']), reverse=True)
        return options

# ===================== ROUTES =====================

@api_router.post("/auth/app-password", response_model=AppPasswordResponse)
async def verify_app_password(request: AppPasswordRequest):
    """Verify the app access password"""
    try:
        if request.password == APP_PASSWORD:
            # Generate a simple token (hash of password + timestamp)
            token = hashlib.sha256(f"{APP_PASSWORD}{datetime.now().date()}".encode()).hexdigest()
            return AppPasswordResponse(
                success=True,
                message="Access granted",
                token=token
            )
        else:
            raise HTTPException(status_code=401, detail="Invalid password")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"App password verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login to Webull using Playwright automation"""
    try:
        # Validate Device ID
        if not request.device_id or len(request.device_id) != 32:
            raise HTTPException(
                status_code=400,
                detail="Valid Device ID (32-character hex string) is required. See instructions on login page."
            )
        
        logger.info(f"Starting Playwright authentication for user: {request.username[:5]}..., is_paper: {request.is_paper}")
        
        # Ensure browsers are installed before attempting Playwright auth
        logger.info("Verifying Playwright browsers before login...")
        if not ensure_playwright_browsers():
            raise HTTPException(
                status_code=500,
                detail="Failed to install Playwright browsers. Please try again or contact support."
            )
        
        # Use Playwright to authenticate and capture tokens (now async)
        tokens = await authenticate_webull_playwright(
            username=request.username,
            password=request.password,
            did=request.device_id
        )
        
        logger.info(f"Playwright auth result: {tokens.keys() if tokens else 'None'}")
        
        if not tokens or not tokens.get('AccessToken'):
            logger.error(f"Authentication failed - no access token. Tokens received: {tokens}")
            raise HTTPException(
                status_code=401,
                detail="Login failed. Please check:\n1. Username and password are correct\n2. Device ID is valid (32-char hex from browser)\n3. No CAPTCHA appeared (DID should prevent this)\n\nIf CAPTCHA appears, you may need a fresh DID from a new browser login."
            )
        
        logger.info("Playwright authentication successful, initializing Webull instance...")
        
        # Initialize Webull instance with captured tokens
        wb = get_webull_instance(request.is_paper)
        wb._set_did(request.device_id)
        
        # Use api_login with captured tokens
        wb.api_login(
            access_token=tokens['AccessToken'],
            refresh_token=tokens['RefreshToken'],
            uuid=tokens['UUID'],
            token_expire=tokens.get('TokenExpire', '2099-01-01T00:00:00.000+0000')
        )
        
        # For paper trading, explicitly get account ID (api_login doesn't do this for paper)
        if request.is_paper:
            logger.info("Getting paper account ID...")
            account_id = wb.get_account_id()
            if not account_id:
                raise HTTPException(status_code=500, detail="Failed to get paper account ID")
            logger.info(f"Paper account ID: {account_id}")
        else:
            logger.info(f"Live account ID: {wb._account_id}")
        
        # Get trade token
        logger.info("Getting trade token...")
        if not wb.get_trade_token(request.trade_pin):
            raise HTTPException(status_code=401, detail="Invalid trade PIN")
        
        logger.info(f"✅ Trade token obtained: {wb._trade_token[:20]}..." if wb._trade_token else "❌ No trade token")
        
        # Save session including tokens, DID, and TRADE TOKEN
        session_data = {
            'session_type': 'webull',
            'access_token': tokens['AccessToken'],
            'refresh_token': tokens['RefreshToken'],
            'token_expire': tokens.get('TokenExpire', '2099-01-01T00:00:00.000+0000'),
            'uuid': tokens['UUID'],
            'account_id': wb._account_id,
            'is_paper': request.is_paper,
            'device_id': request.device_id,
            'trade_token': wb._trade_token  # CRITICAL: Save trade token for order placement
        }
        # CRITICAL: Check old session BEFORE saving new one to detect mode switches
        old_is_paper = None
        global trading_bot_task
        if bot_state.running:
            try:
                old_session = await db.sessions.find_one({'session_type': 'webull'})
                old_is_paper = old_session.get('is_paper', True) if old_session else True
            except:
                old_is_paper = True
        
        await save_session(session_data)
        
        logger.info(f"✅ Session saved to database (is_paper: {request.is_paper})")
        
        # If bot is running and mode changed, restart it with new session
        if bot_state.running and old_is_paper is not None and old_is_paper != request.is_paper:
            logger.warning(f"⚠️ Bot mode switch detected: {'PAPER' if old_is_paper else 'LIVE'} → {'PAPER' if request.is_paper else 'LIVE'}. Restarting bot...")
            bot_state.running = False
            if trading_bot_task:
                trading_bot_task.cancel()
                await asyncio.sleep(1)  # Give it time to stop
            
            # Get settings
            settings = await settings_collection.find_one({'user': 'default'}) or {'auto_trading': False}
            if settings.get('auto_trading', False):
                # Restart bot with NEW wb instance using correct mode
                trading_bot_task = asyncio.create_task(run_trading_bot(wb, settings))
                logger.info(f"✅ Bot restarted in {'LIVE' if not request.is_paper else 'PAPER'} trading mode")
            else:
                logger.info("Auto-trading is disabled, not restarting bot")
        elif bot_state.running:
            logger.info(f"Bot mode unchanged ({'PAPER' if request.is_paper else 'PAPER'}), no restart needed")
        
        return LoginResponse(
            success=True,
            message="Login successful via Playwright automation",
            session_id=tokens['UUID']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Login error: {error_msg}", exc_info=True)
        
        # Provide helpful error messages
        if "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=408,
                detail="Login timeout. The automated browser may have encountered an issue. Please try again."
            )
        elif "playwright" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="Browser automation error. Please contact support if this persists."
            )
        elif "account" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail=f"Account access error: {error_msg}. Please verify your account credentials and try again."
            )
        
        raise HTTPException(status_code=500, detail=f"Login failed: {error_msg}")

@api_router.post("/auth/restore")
async def restore_session():
    """Restore session from database"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=404, detail="No session found")
        
        wb = get_webull_instance(session.get('is_paper', True))
        
        # Restore DID if available
        if 'device_id' in session:
            wb._set_did(session['device_id'])
        
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # CRITICAL: Restore trade token for order placement
        if 'trade_token' in session and session['trade_token']:
            wb._trade_token = session['trade_token']
            logger.info("✅ Trade token restored from session")
        else:
            logger.warning("⚠️ No trade token in session - orders will fail!")
        
        return {"success": True, "is_paper": session.get('is_paper', True)}
    except Exception as e:
        logger.error(f"Restore session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/auth/logout")
async def logout():
    """Logout and clear session"""
    try:
        # Delete session from database
        await db.sessions.delete_one({'session_type': 'webull'})
        logger.info("Session cleared successfully")
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/debug/playwright-status")
async def get_playwright_status():
    """Check Playwright browser installation status and debug info"""
    import os
    from pathlib import Path
    import glob
    
    debug_info = {
        "playwright_browsers_path": os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'NOT SET'),
        "browsers_installed": [],
        "browser_path_exists": False,
        "debug_screenshots": [],
        "recent_errors": []
    }
    
    # Check browser installation
    pw_path = Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/pw-browsers'))
    debug_info["browser_path_exists"] = pw_path.exists()
    
    if pw_path.exists():
        debug_info["browsers_installed"] = [d.name for d in pw_path.iterdir() if d.is_dir()]
    
    # Check for chromium specifically
    chromium_1187 = pw_path / "chromium_headless_shell-1187" / "chrome-linux" / "headless_shell"
    debug_info["chromium_1187_exists"] = chromium_1187.exists()
    
    # List debug screenshots
    screenshot_dir = Path("/tmp/webull_debug")
    if screenshot_dir.exists():
        screenshots = sorted(screenshot_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]
        debug_info["debug_screenshots"] = [str(s) for s in screenshots]
    
    # Try to import playwright and check version
    try:
        import playwright
        debug_info["playwright_version"] = playwright.__version__
    except Exception as e:
        debug_info["playwright_import_error"] = str(e)
    
    return debug_info

@api_router.get("/debug/screenshot/{filename}")
async def get_debug_screenshot(filename: str):
    """Retrieve a debug screenshot by filename"""
    from fastapi.responses import FileResponse
    import os
    
    # Security: only allow alphanumeric, underscore, dash, and .png extension
    import re
    if not re.match(r'^[\w\-]+\.png$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    screenshot_path = f"/tmp/webull_debug/{filename}"
    if not os.path.exists(screenshot_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    
    return FileResponse(screenshot_path, media_type="image/png")

@api_router.get("/account")
async def get_account():
    """Get account information"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            logger.info("Getting paper account ID...")
            account_id = wb.get_account_id()
            logger.info(f"Paper account ID: {account_id}")
        
        logger.info("Fetching account info...")
        account_info = wb.get_account()
        
        # Log detailed info
        logger.info(f"netLiquidation: {account_info.get('netLiquidation')}")
        logger.info(f"accountMembers type: {type(account_info.get('accountMembers'))}")
        if account_info.get('accountMembers'):
            logger.info(f"accountMembers content: {account_info.get('accountMembers')}")
        
        return account_info
    except Exception as e:
        logger.error(f"Get account error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/positions")
async def get_positions():
    """Get current positions"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            wb.get_account_id()
        
        # Restore trade token
        if 'trade_token' in session and session['trade_token']:
            wb._trade_token = session['trade_token']
        
        positions = wb.get_positions()
        
        # Enrich option positions with full symbol
        # 1. First try from entry_signals database (fast, for bot trades)
        # 2. If not found, fetch from Webull API (for manual trades)
        # 3. For paper trading, fix optionSymbol field (it returns just ticker instead of full symbol)
        
        is_paper = session.get('is_paper', True)
        
        for pos in positions:
            # Paper trading uses 'tickerType', live uses 'assetType'
            is_option = (pos.get('assetType') == 'OPTION' or pos.get('tickerType') == 'OPTION')
            
            # PAPER TRADING FIX: Paper API returns symbol/optionSymbol swapped
            # Paper: symbol="SPY251212P00687000", optionSymbol="SPY"
            # Live: symbol="SPY", optionSymbol="SPY251212P00687000"
            if is_paper and is_option and 'ticker' in pos:
                ticker = pos['ticker']
                symbol = ticker.get('symbol', '')
                option_symbol = ticker.get('optionSymbol', '')
                
                # If symbol looks like full option symbol but optionSymbol doesn't, swap them
                if len(symbol) > 10 and len(option_symbol) <= 5:
                    ticker['optionSymbol'] = symbol  # Use full symbol
                    ticker['symbol'] = option_symbol  # Use short ticker
                    logger.debug(f"Paper trading: Fixed optionSymbol for {pos.get('tickerId')}: {symbol}")
            
            if is_option and pos.get('tickerId'):
                try:
                    option_id = str(pos['tickerId'])
                    enriched = False
                    
                    # Try getting from entry signal database first (instant, no API call)
                    entry_signal = await db.entry_signals.find_one({'ticker_id': option_id})
                    if entry_signal:
                        if entry_signal.get('ticker_symbol'):
                            pos['ticker']['optionSymbol'] = entry_signal['ticker_symbol']
                            enriched = True
                        if entry_signal.get('timestamp'):
                            pos['ticker']['entryTime'] = entry_signal['timestamp']
                    
                    # If not in database, fetch from Webull API (manual trades)
                    if not enriched:
                        try:
                            option_quote = wb.get_option_quote(stock='SPY', optionId=int(option_id))
                            if option_quote.get('data') and option_quote['data']:
                                option_symbol = option_quote['data'][0].get('symbol')
                                if option_symbol:
                                    pos['ticker']['optionSymbol'] = option_symbol
                                    logger.info(f"Fetched optionSymbol from API for {option_id}: {option_symbol}")
                        except Exception as api_e:
                            logger.warning(f"Could not fetch optionSymbol from API for {option_id}: {api_e}")
                    
                except Exception as e:
                    logger.warning(f"Could not enrich option position {option_id}: {e}")
        
        return {"positions": positions}
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders")
async def get_orders():
    """Get current open orders"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            wb.get_account_id()
        
        orders = wb.get_current_orders()
        return {"orders": orders}
    except Exception as e:
        logger.error(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders/history")
async def get_order_history():
    """Get historical orders"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            wb.get_account_id()
        
        # Get historical orders - paper trading uses different status param
        # Limit to 30 orders for better performance (was 50)
        logger.info(f"Fetching order history for {'PAPER' if session.get('is_paper') else 'LIVE'} account...")
        if session.get('is_paper', True):
            try:
                history = wb.get_history_orders(status='All', count=30)
            except:
                history = wb.get_history_orders(status='', count=30)
        else:
            # For live accounts, try multiple query strategies
            logger.info("Attempting live account order history fetch...")
            try:
                # Try with 'Filled' status first (most common successful orders)
                history = wb.get_history_orders(status='Filled', count=30)
                logger.info(f"Live account query (Filled): {len(history) if history else 0} orders")
                
                # If empty, try 'All' status
                if not history or len(history) == 0:
                    logger.info("Trying 'All' status...")
                    history = wb.get_history_orders(status='All', count=30)
                    logger.info(f"Live account query (All): {len(history) if history else 0} orders")
                
                # If still empty, try without status parameter
                if not history or len(history) == 0:
                    logger.info("Trying without status parameter...")
                    history = wb.get_history_orders(count=30)
                    logger.info(f"Live account query (no status): {len(history) if history else 0} orders")
                
                # If still empty, try the paper trading method
                if not history or len(history) == 0:
                    logger.info("Trying paper trading account ID method...")
                    wb.get_account_id()
                    history = wb.get_history_orders(status='All', count=30)
                    logger.info(f"Live account query (with account_id): {len(history) if history else 0} orders")
                    
            except Exception as e:
                logger.error(f"All live account query attempts failed: {e}")
                history = []
        
        logger.info(f"Final order history count: {len(history) if history else 0} orders")
        
        # Enrich orders with ticker symbols and entry signals
        ticker_cache = {}  # Cache ticker lookups to avoid duplicate API calls
        
        # Fetch all entry signals from database
        entry_signals_list = []
        try:
            async for signal in entry_signals_collection.find({}).sort('timestamp', -1).limit(50):
                entry_signals_list.append(signal)
        except Exception as e:
            logger.warning(f"Could not fetch entry signals: {e}")
        
        if isinstance(history, list):
            for order in history:
                # Add ticker symbols for options
                if order.get('tickerType') == 'OPTION' and order.get('belongTickerId'):
                    ticker_id = order['belongTickerId']
                    
                    # Check cache first
                    if ticker_id in ticker_cache:
                        order['underlyingSymbol'] = ticker_cache[ticker_id]
                    else:
                        try:
                            # Look up the underlying stock symbol using ticker ID
                            ticker_info = wb.get_quote(tId=ticker_id)
                            if ticker_info and 'symbol' in ticker_info:
                                symbol = ticker_info['symbol']
                                order['underlyingSymbol'] = symbol
                                ticker_cache[ticker_id] = symbol  # Cache it
                            else:
                                logger.warning(f"No symbol in ticker info for ID {ticker_id}")
                                order['underlyingSymbol'] = f"ID:{ticker_id}"
                                ticker_cache[ticker_id] = f"ID:{ticker_id}"
                        except Exception as e:
                            logger.warning(f"Could not lookup ticker for ID {ticker_id}: {e}")
                            order['underlyingSymbol'] = f"ID:{ticker_id}"
                            ticker_cache[ticker_id] = f"ID:{ticker_id}"
                
                # Match entry signal to order by timestamp (within 2 minutes)
                order['entry_signal'] = None
                if order.get('action') == 'BUY' and order.get('status') in ['Filled', 'Working']:
                    order_time = order.get('createTime0') or order.get('createTime')
                    if order_time:
                        try:
                            from datetime import datetime, timedelta
                            order_dt = datetime.fromtimestamp(int(order_time) / 1000) if isinstance(order_time, (int, float)) else datetime.fromisoformat(str(order_time))
                            
                            # Find matching entry signal within 2 minutes
                            for signal in entry_signals_list:
                                if '_id' in signal and signal['_id'] == 'current':
                                    signal_time_str = signal.get('timestamp') or signal.get('saved_at')
                                    if signal_time_str:
                                        signal_dt = datetime.fromisoformat(signal_time_str.replace('Z', '+00:00'))
                                        time_diff = abs((order_dt - signal_dt).total_seconds())
                                        
                                        if time_diff < 120:  # Within 2 minutes
                                            order['entry_signal'] = {
                                                'type': signal.get('signal_type', 'Unknown'),
                                                'reasons': signal.get('reasons', []),
                                                'grade': signal.get('grade', 'N/A')
                                            }
                                            break
                        except Exception as e:
                            logger.debug(f"Could not match entry signal: {e}")
        
        return {"orders": history if isinstance(history, list) else []}
    except Exception as e:
        logger.error(f"Get order history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/account/activities")
async def get_account_activities():
    """Get account activities including trades for P/L calculation"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            wb.get_account_id()
        
        # Try to get activities first (works for real accounts)
        activities = wb.get_activities(index=1, size=500)
        
        # If activities data is empty (common for paper trading), calculate P/L from filled orders
        if isinstance(activities, dict) and isinstance(activities.get('data'), dict) and not activities['data']:
            logger.info("Activities data is empty, calculating P/L from filled orders...")
            
            # Get filled orders for P/L calculation
            try:
                filled_orders = wb.get_history_orders(status='Filled', count=100)
                logger.info(f"Fetched {len(filled_orders) if isinstance(filled_orders, list) else 0} filled orders")
                
                # Log first order structure for debugging
                if isinstance(filled_orders, list) and len(filled_orders) > 0:
                    logger.info(f"Sample filled order structure: {filled_orders[0]}")
                
                # Calculate P/L from filled orders
                pl_by_period, pl_by_symbol = calculate_pl_from_orders(filled_orders, wb)
                
                # Return in a format that matches activities structure
                return {
                    'success': True,
                    'code': 'success',
                    'msg': 'OK',
                    'data': {
                        'pl_summary': pl_by_period,
                        'pl_by_symbol': pl_by_symbol,
                        'orders': filled_orders if isinstance(filled_orders, list) else []
                    }
                }
            except Exception as e:
                logger.error(f"Error fetching filled orders: {e}")
                # Return empty structure if we can't get orders
                return {
                    'success': True,
                    'code': 'success',
                    'msg': 'OK',
                    'data': {
                        'pl_summary': {
                            'today': 0.0,
                            'week': 0.0,
                            'month': 0.0,
                            'year': 0.0,
                            'all_time': 0.0
                        },
                        'pl_by_symbol': [],
                        'orders': []
                    }
                }
        
        return activities
    except Exception as e:
        logger.error(f"Get activities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_pl_from_orders(orders, wb=None):
    """Calculate profit/loss from filled orders grouped by time periods and by symbol"""
    if not isinstance(orders, list) or len(orders) == 0:
        return {
            'today': 0.0,
            'week': 0.0,
            'month': 0.0,
            'year': 0.0,
            'all_time': 0.0
        }, []
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)
    
    pl_data = {
        'today': 0.0,
        'week': 0.0,
        'month': 0.0,
        'year': 0.0,
        'all_time': 0.0
    }
    
    # Track P/L by symbol
    pl_by_symbol_dict = {}
    
    # Group orders by tickerId for matching buy/sell
    ticker_orders = {}
    for order in orders:
        if order.get('status') != 'Filled':
            continue
            
        # Get ticker ID from the order
        ticker_id = None
        if isinstance(order.get('ticker'), dict):
            ticker_id = order['ticker'].get('tickerId')
        elif order.get('tickerId'):
            ticker_id = order.get('tickerId')
            
        if not ticker_id:
            continue
            
        if ticker_id not in ticker_orders:
            ticker_orders[ticker_id] = {'buys': [], 'sells': []}
        
        action = order.get('action', '').upper()
        if action == 'BUY':
            ticker_orders[ticker_id]['buys'].append(order)
        elif action == 'SELL':
            ticker_orders[ticker_id]['sells'].append(order)
    
    logger.info(f"Processing {len(ticker_orders)} unique ticker IDs for P/L calculation")
    
    # Calculate P/L for each ticker by matching buy/sell
    for ticker_id, order_dict in ticker_orders.items():
        buys = sorted(order_dict['buys'], key=lambda x: x.get('createTime0', 0))
        sells = sorted(order_dict['sells'], key=lambda x: x.get('createTime0', 0))
        
        logger.info(f"Ticker ID {ticker_id}: {len(buys)} buys, {len(sells)} sells")
        
        # Initialize symbol P/L tracking
        underlying_symbol = None
        ticker_total_pl = 0.0
        
        # Try to get underlying symbol name from orders (just the ticker, not full contract details)
        for order in buys + sells:
            if order.get('tickerType') == 'OPTION' and order.get('belongTickerId'):
                # For options, get underlying symbol only
                try:
                    if wb:
                        ticker_info = wb.get_quote(tId=order['belongTickerId'])
                        if ticker_info and 'symbol' in ticker_info:
                            underlying_symbol = ticker_info['symbol']
                            break
                except Exception as e:
                    logger.warning(f"Could not lookup symbol for ticker {order.get('belongTickerId')}: {e}")
            # For stocks, symbol might be in ticker field
            elif isinstance(order.get('ticker'), dict) and order['ticker'].get('symbol'):
                underlying_symbol = order['ticker']['symbol']
                break
        
        if not underlying_symbol:
            underlying_symbol = f"Unknown (ID: {ticker_id})"
        
        # Simple FIFO matching
        for sell in sells:
            try:
                sell_qty = float(sell.get('filledQuantity', 0))
                sell_price = float(sell.get('avgFilledPrice', 0))
                sell_time_ms = sell.get('createTime0', sell.get('filledTime0', 0))
                multiplier = float(sell.get('optionContractMultiplier', 1))
                
                if sell_qty <= 0 or sell_price <= 0:
                    continue
                
                # Parse sell time
                sell_time = datetime.fromtimestamp(sell_time_ms / 1000, tz=timezone.utc)
                
                # Match with corresponding buy orders (FIFO)
                remaining_qty = sell_qty
                pl = 0.0
                
                for buy in buys[:]:  # Iterate over copy
                    if remaining_qty <= 0:
                        break
                        
                    buy_qty = float(buy.get('filledQuantity', 0))
                    buy_price = float(buy.get('avgFilledPrice', 0))
                    
                    if buy_qty <= 0 or buy_price <= 0:
                        continue
                    
                    # Match quantities
                    matched_qty = min(remaining_qty, buy_qty)
                    
                    # Calculate P/L for this match
                    # P/L = (sell_price - buy_price) * matched_qty * multiplier
                    match_pl = (sell_price - buy_price) * matched_qty * multiplier
                    pl += match_pl
                    
                    remaining_qty -= matched_qty
                    buy['filledQuantity'] = str(buy_qty - matched_qty)  # Update remaining
                    
                    if buy_qty - matched_qty <= 0:
                        buys.remove(buy)  # Fully matched
                
                logger.info(f"Sell order {sell.get('orderId')}: P/L = ${pl:.2f}")
                
                # Track ticker total
                ticker_total_pl += pl
                
                # Add to appropriate time periods
                pl_data['all_time'] += pl
                if sell_time >= year_start:
                    pl_data['year'] += pl
                if sell_time >= month_start:
                    pl_data['month'] += pl
                if sell_time >= week_start:
                    pl_data['week'] += pl
                if sell_time >= today_start:
                    pl_data['today'] += pl
                        
            except Exception as e:
                logger.warning(f"Error calculating P/L for sell order: {e}")
                continue
        
        # Aggregate P/L by underlying symbol (consolidate all contracts for same ticker)
        if ticker_total_pl != 0:  # Only include symbols with realized P/L
            if underlying_symbol in pl_by_symbol_dict:
                pl_by_symbol_dict[underlying_symbol] += ticker_total_pl
            else:
                pl_by_symbol_dict[underlying_symbol] = ticker_total_pl
    
    # Convert to list format for frontend, sorted by P/L (negative first, then positive)
    pl_by_symbol_list = [
        {'symbol': symbol, 'pl': pl}
        for symbol, pl in sorted(pl_by_symbol_dict.items(), key=lambda x: x[1])
    ]
    
    logger.info(f"Calculated P/L: {pl_data}")
    logger.info(f"P/L by symbol: {pl_by_symbol_list}")
    return pl_data, pl_by_symbol_list

@api_router.get("/market/quote/{symbol}")
async def get_market_quote(symbol: str):
    """Get market quote for a symbol"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        quote = wb.get_quote(stock=symbol)
        return quote
    except Exception as e:
        logger.error(f"Get quote error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/market/bars/{symbol}")
async def get_market_bars(symbol: str, interval: str = 'm30', count: int = 140):
    """Get market bars (candlestick data)"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        ticker_id = wb.get_ticker(symbol)
        bars = wb.get_bars(symbol, ticker_id, interval, count, 1)
        
        # Convert DataFrame to dict for JSON serialization
        bars_dict = bars.to_dict(orient='records')
        return {"bars": bars_dict, "symbol": symbol}
    except Exception as e:
        logger.error(f"Get bars error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analysis/signals/{symbol}")
async def get_trading_signals(symbol: str):
    """Get trading signals (RSI, MACD, etc.) for a symbol"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # For paper trading, get account ID first
        if session.get('is_paper', True):
            wb.get_account_id()
        
        ticker_id = wb.get_ticker(symbol)
        if not ticker_id or ticker_id == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"Could not find ticker ID for {symbol}. Market may be closed or symbol is invalid."
            )
        
        df = wb.get_bars(symbol, ticker_id, 'm30', 140, 1)
        
        if df is None or df.empty:
            raise HTTPException(
                status_code=503,
                detail="No market data available. Market may be closed."
            )
        
        # Calculate indicators
        rsi = talib.RSI(df['close'])
        macd, signal, hist = talib.MACD(df['close'])
        
        rsi_grade = get_rsi_grade(df)
        macd_grade = get_macd_grade(df)
        
        return {
            "symbol": symbol,
            "rsi": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
            "rsi_grade": rsi_grade,
            "macd": float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None,
            "macd_signal": float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else None,
            "macd_grade": macd_grade,
            "current_price": float(df['close'].iloc[-1])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/trade/option")
async def place_option_trade(request: TradeRequest):
    """Place an option trade"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # CRITICAL: Restore trade token for order placement
        if 'trade_token' in session and session['trade_token']:
            wb._trade_token = session['trade_token']
            logger.info("Manual trade: Trade token restored")
        else:
            raise HTTPException(status_code=401, detail="No trade token found. Please log out and log in again.")
        
        account_info = wb.get_account()
        account_value = float(account_info['accountMembers'][1]['value'])
        
        # Get filtered options
        filtered_chain = filter_options(wb, request.symbol, request.option_type)
        if not filtered_chain:
            raise HTTPException(status_code=404, detail="No suitable options found")
        
        # Trade percentages based on grade
        trade_grades = {
            'A+': {'stop_loss_pct': 0.50, 'trade_pct': 0.2},
            'A': {'stop_loss_pct': 0.47, 'trade_pct': 0.18},
            'B+': {'stop_loss_pct': 0.44, 'trade_pct': 0.15},
            'B': {'stop_loss_pct': 0.41, 'trade_pct': 0.15},
            'C+': {'stop_loss_pct': 0.38, 'trade_pct': 0.12},
            'C': {'stop_loss_pct': 0.35, 'trade_pct': 0.10},
            'D+': {'stop_loss_pct': 0.30, 'trade_pct': 0.05},
            'D': {'stop_loss_pct': 0.25, 'trade_pct': 0.05}
        }
        
        trade_pct = trade_grades[request.trade_grade]['trade_pct']
        
        # DOUBLE percentages for accounts under $5,000 (more aggressive on small accounts)
        if account_value < 5000:
            trade_pct = min(trade_pct * 2, 1.0)  # Double but cap at 100%
            logger.info(f"💰 Small account (<$5k): Doubled manual trade percentage to {trade_pct*100:.0f}%")
        
        # Get option details
        option_key = 'call' if request.option_type == 'call' else 'put'
        option = filtered_chain[0][option_key]
        option_quote = wb.get_option_quote(stock=request.symbol, optionId=option['tickerId'])
        option_price = float(option_quote['data'][0]['askList'][0]['price'])
        
        # Calculate quantity
        capital_to_use = account_value * trade_pct
        contract_cost = option_price * 100
        order_quantity = math.floor(capital_to_use / contract_cost)
        
        logger.info(f"Manual trade calculation: Account=${account_value:.2f}, Grade={request.trade_grade} ({trade_pct*100}%), Capital=${capital_to_use:.2f}, Option=${option_price:.2f}, Contract=${contract_cost:.2f}, Quantity={order_quantity}")
        
        # If calculated quantity is 0 but account can afford 1 contract, use 1 contract minimum
        if order_quantity < 1:
            if account_value >= contract_cost:
                logger.warning(f"Grade-based calculation gave 0 contracts, but account can afford 1. Using minimum of 1 contract.")
                order_quantity = 1
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient funds: Account ${account_value:.2f}, need ${contract_cost:.2f} per contract but only ${capital_to_use:.2f} ({trade_pct*100}% for grade {request.trade_grade})"
                )
        
        # Get current SPY price for entry signal (use option price as fallback)
        try:
            spy_quote = wb.get_quote(stock=request.symbol)
            spy_current_price = float(spy_quote[0]['close'])
        except Exception as e:
            logger.warning(f"Could not fetch SPY price, using approximate: {e}")
            spy_current_price = option_price * 100  # Rough estimate from option price
        
        # Place LIMIT order at ask price for immediate execution (like market order)
        # Use ask price for BUY orders to ensure fill (pay what sellers are asking)
        logger.info(f"Manual trade: Placing LIMIT order at ASK price ${option_price:.2f} for {order_quantity} contracts")
        result = wb.place_order_option(
            optionId=option['tickerId'],
            lmtPrice=option_price,  # Use ask price for aggressive fill (option_price from quote is ask)
            stpPrice=None,  # Not needed for limit orders
            action='BUY',
            orderType='LMT',  # Limit order (Webull rejects MKT+GTC on live accounts)
            enforce='GTC',
            quant=order_quantity
        )
        
        # Store manual trade entry signal
        from datetime import datetime, timezone
        ticker_id_str = str(option['tickerId'])
        manual_entry_signal = {
            'signal_type': 'Manual Trade',
            'reasons': f'Manually placed {request.option_type.upper()} trade from Trade panel',
            'zones': None,
            'grade': 'N/A',
            'entry_price': spy_current_price,
            'direction': request.option_type.upper(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'ticker_symbol': option['symbol'],
            'ticker_id': ticker_id_str  # CRITICAL: Add ticker_id for position enrichment
        }
        
        # Save to database (use ticker_id as key for easy lookup)
        await entry_signals_collection.replace_one(
            {'ticker_id': ticker_id_str},
            {**manual_entry_signal, 'saved_at': datetime.now(timezone.utc).isoformat()},
            upsert=True
        )
        
        # Also save as 'current' for backward compatibility
        await entry_signals_collection.replace_one(
            {'_id': 'current'},
            {'_id': 'current', **manual_entry_signal, 'saved_at': datetime.now(timezone.utc).isoformat()},
            upsert=True
        )
        logger.info(f"✅ Manual trade entry signal saved")
        
        return {
            "success": True,
            "order": result,
            "quantity": order_quantity,
            "price": option_price,
            "symbol": request.symbol,
            "option_type": request.option_type
        }
    except Exception as e:
        logger.error(f"Place trade error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/trade/order/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an open order"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        result = wb.cancel_order(order_id)
        return {"success": result}
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/trade/sell-position")
async def sell_position_at_market(request: SellPositionRequest):
    """Sell a position at market price"""
    try:
        ticker_id = request.ticker_id
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # Get account info to find the position
        account_info = wb.get_account()
        positions = account_info.get('positions', [])
        
        # Find the position with matching ticker_id
        position = None
        for pos in positions:
            if pos['ticker']['tickerId'] == ticker_id:
                position = pos
                break
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Get current market price
        option_quote = wb.get_option_quote(stock='SPY', optionId=ticker_id)
        
        # Try to get bid price, fall back to last price if bid/ask not available
        bid_price = None
        if (option_quote.get('data') and option_quote['data'] and 
            option_quote['data'][0].get('bidList') and option_quote['data'][0]['bidList']):
            bid_price = float(option_quote['data'][0]['bidList'][0]['price'])
        elif option_quote.get('data') and option_quote['data']:
            # Fallback to last price
            bid_price = float(position['lastPrice'])
            logger.warning(f"⚠️ Bid price not available, using last price: ${bid_price:.2f}")
        
        if not bid_price or bid_price <= 0:
            raise HTTPException(status_code=500, detail="Cannot determine sell price for position")
        
        quantity = int(position['position'])
        
        logger.info(f"Selling position: {quantity} contracts at LIMIT price ${bid_price:.2f}")
        
        # Place SELL LIMIT order - Use SAME parameters as BUY orders
        result = wb.place_order_option(
            optionId=ticker_id,
            lmtPrice=bid_price,  # Use bid price for SELL orders
            stpPrice=None,
            action='SELL',
            orderType='LMT',  # Same as BUY
            enforce='GTC',  # SAME AS BUY
            quant=quantity
        )
        
        # Clear entry signal since position is being closed
        bot_state.last_entry_signal = None
        logger.info("✅ Position sold manually, entry signal cleared")
        
        return {
            "success": True,
            "order": result,
            "quantity": quantity,
            "price": bid_price,
            "ticker_id": ticker_id
        }
        
    except Exception as e:
        logger.error(f"Sell position error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/quote/spy")
async def get_spy_quote():
    """Get real-time SPY quote directly from Webull (bypasses bot state)"""
    try:
        session = await get_session()
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        wb = get_webull_instance(session.get('is_paper', True))
        wb.api_login(
            access_token=session['access_token'],
            refresh_token=session['refresh_token'],
            token_expire=session['token_expire'],
            uuid=session['uuid']
        )
        
        # Direct quote fetch - no caching, always fresh
        quote = wb.get_quote(stock='SPY')
        
        return {
            "symbol": "SPY",
            "price": float(quote.get('close', 0)),
            "change": float(quote.get('change', 0)),
            "changeRatio": float(quote.get('changeRatio', 0)),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Get SPY quote error: {e}")
        # Return last known price from bot state as fallback
        from trading_bot_service import bot_state
        return {
            "symbol": "SPY",
            "price": bot_state.current_price,
            "change": 0,
            "changeRatio": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fallback": True
        }

@api_router.get("/settings")
async def get_settings():
    """Get user settings"""
    try:
        settings = await db.settings.find_one({'user': 'default'}, {"_id": 0})
        if not settings:
            # Return default settings
            return {
                "auto_trading": False,
                "profit_percentage": 50.0,
                "loss_percentage": 25.0,
                "sms_notifications": False,
                "zone_exit_enabled": False,
                "use_5min_entries": False
            }
        # Remove MongoDB _id if present
        settings.pop('_id', None)
        settings.pop('user', None)
        return settings
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/settings")
async def update_settings(settings: SettingsUpdate):
    """Update user settings and manage trading bot"""
    global trading_bot_task
    
    try:
        update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
        update_data['user'] = 'default'
        
        logger.info(f"Settings update request: {update_data}")
        
        await db.settings.update_one(
            {'user': 'default'},
            {'$set': update_data},
            upsert=True
        )
        
        # Get updated settings
        result = await db.settings.find_one({'user': 'default'}, {"_id": 0})
        result.pop('user', None)
        
        # Manage trading bot based on auto_trading setting
        auto_trading_enabled = result.get('auto_trading', False)
        
        logger.info(f"Auto-trading enabled: {auto_trading_enabled}, Bot currently running: {bot_state.running}")
        
        if auto_trading_enabled and not bot_state.running:
            # Start the trading bot
            logger.info("🚀 Starting trading bot (auto-trading enabled)")
            
            # Get session and webull instance
            session = await get_session()
            if not session:
                logger.error("Cannot start bot - no authenticated session")
                raise HTTPException(status_code=401, detail="Not authenticated. Please login first.")
            
            wb = get_webull_instance(session.get('is_paper', True))
            wb.api_login(
                access_token=session['access_token'],
                refresh_token=session['refresh_token'],
                token_expire=session['token_expire'],
                uuid=session['uuid']
            )
            
            # Get account ID for paper trading
            if session.get('is_paper', True):
                wb.get_account_id()
            
            # Start bot as background task
            trading_bot_task = asyncio.create_task(run_trading_bot(wb, result))
            logger.info("✅ Trading bot task created and started")
            
        elif not auto_trading_enabled and bot_state.running:
            # Stop the trading bot
            logger.info("🛑 Stopping trading bot (auto-trading disabled)")
            bot_state.running = False
            if trading_bot_task:
                trading_bot_task.cancel()
                trading_bot_task = None
            logger.info("✅ Trading bot stopped")
        else:
            logger.info(f"No bot state change needed (enabled={auto_trading_enabled}, running={bot_state.running})")
        
        return {"success": True, "settings": result, "bot_running": bot_state.running}
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bot/status")
async def get_trading_bot_status():
    """Get current trading bot status and auto-start if needed"""
    global trading_bot_task
    
    try:
        # Check if bot should be running but isn't
        if not bot_state.running:
            # Get settings
            settings = await db.settings.find_one({'user': 'default'}, {"_id": 0})
            
            if settings and settings.get('auto_trading', False):
                # Auto-trading is ON but bot is stopped - check for session
                session = await get_session()
                
                if session:
                    logger.info("🚀 Auto-starting bot (auto_trading=ON, session exists, bot stopped)")
                    
                    wb = get_webull_instance(session.get('is_paper', True))
                    wb.api_login(
                        access_token=session['access_token'],
                        refresh_token=session['refresh_token'],
                        token_expire=session['token_expire'],
                        uuid=session['uuid']
                    )
                    
                    if session.get('is_paper', True):
                        wb.get_account_id()
                    
                    # Start bot
                    trading_bot_task = asyncio.create_task(run_trading_bot(wb, settings))
                    logger.info("✅ Bot auto-started from status check")
    
    except Exception as e:
        logger.error(f"Error in bot status auto-start: {e}")
    
    return get_bot_status()

@api_router.get("/bot/heartbeat")
async def get_bot_heartbeat():
    """Health check endpoint that returns bot heartbeat status"""
    from trading_bot_service import last_heartbeat
    
    now = datetime.now(timezone.utc)
    time_since_heartbeat = (now - last_heartbeat).total_seconds()
    
    return {
        "alive": time_since_heartbeat < 120,  # Consider alive if heartbeat within 2 minutes
        "last_heartbeat": last_heartbeat.isoformat(),
        "seconds_since_heartbeat": time_since_heartbeat,
        "bot_running": bot_state.running,
        "current_time": now.isoformat()
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()