from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global webull instance (will be set after login)
wb_instance = None
is_paper_trading = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================== MODELS =====================

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
        
        logger.info(f"Starting Playwright authentication for user: {request.username[:5]}...")
        
        # Use Playwright to authenticate and capture tokens (now async)
        tokens = await authenticate_webull_playwright(
            username=request.username,
            password=request.password,
            did=request.device_id
        )
        
        if not tokens or not tokens.get('AccessToken'):
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
        
        # Get trade token
        logger.info("Getting trade token...")
        if not wb.get_trade_token(request.trade_pin):
            raise HTTPException(status_code=401, detail="Invalid trade PIN")
        
        # Save session including tokens and DID
        session_data = {
            'session_type': 'webull',
            'access_token': tokens['AccessToken'],
            'refresh_token': tokens['RefreshToken'],
            'token_expire': tokens.get('TokenExpire', '2099-01-01T00:00:00.000+0000'),
            'uuid': tokens['UUID'],
            'account_id': wb._account_id,
            'is_paper': request.is_paper,
            'device_id': request.device_id
        }
        await save_session(session_data)
        
        logger.info("✅ Login successful!")
        
        return LoginResponse(
            success=True,
            message="Login successful via Playwright automation",
            session_id=tokens['UUID']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Login error: {error_msg}")
        
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
        
        return {"success": True, "is_paper": session.get('is_paper', True)}
    except Exception as e:
        logger.error(f"Restore session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        positions = wb.get_positions()
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
        
        ticker_id = wb.get_ticker(symbol)
        df = wb.get_bars(symbol, ticker_id, 'm30', 140, 1)
        
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
        
        # Get option details
        option_key = 'call' if request.option_type == 'call' else 'put'
        option = filtered_chain[0][option_key]
        option_quote = wb.get_option_quote(stock=request.symbol, optionId=option['tickerId'])
        option_price = float(option_quote['data'][0]['askList'][0]['price'])
        
        # Calculate quantity
        order_quantity = math.floor((account_value * trade_pct) / (option_price * 100))
        
        if order_quantity < 1:
            raise HTTPException(status_code=400, detail="Insufficient funds for trade")
        
        # Place order
        result = wb.place_order_option(
            optionId=option['tickerId'],
            lmtPrice=option_price,
            stpPrice=str(option_price - 0.25),
            action='BUY',
            orderType='LMT',
            enforce='GTC',
            quant=order_quantity
        )
        
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
                "sms_notifications": False
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
    """Update user settings"""
    try:
        update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
        update_data['user'] = 'default'
        
        await db.settings.update_one(
            {'user': 'default'},
            {'$set': update_data},
            upsert=True
        )
        
        # Return updated settings without _id
        result = await db.settings.find_one({'user': 'default'}, {"_id": 0})
        result.pop('user', None)
        
        return {"success": True, "settings": result}
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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