"""
Automated Trading Bot Service
Integrates user's original trading bot logic into async background task
"""
import asyncio
import logging
from datetime import datetime, timedelta, time as dt_time, timezone
from typing import Optional
import os
import numpy as np
import pandas as pd
import talib
import math
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Position tracking collection for trailing stops (initialized from server.py)
position_tracking_collection = None

async def save_position_tracking(ticker_id, dte, entry_price, quantity, direction):
    """Save position tracking data for trailing stop logic"""
    try:
        from server import position_tracking_collection
        await position_tracking_collection.replace_one(
            {'ticker_id': ticker_id},
            {
                'ticker_id': ticker_id,
                'dte': dte,
                'entry_price': entry_price,
                'initial_quantity': quantity,
                'remaining_quantity': quantity,
                'direction': direction,
                'phase': 'initial',  # 'initial' or 'trailing'
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            upsert=True
        )
        logger.info(f"✅ Position tracking saved for {ticker_id}: {dte}DTE, {quantity} contracts")
    except Exception as e:
        logger.error(f"Error saving position tracking: {e}")

async def get_position_tracking(ticker_id):
    """Get position tracking data"""
    try:
        from server import position_tracking_collection
        return await position_tracking_collection.find_one({'ticker_id': ticker_id})
    except Exception as e:
        logger.error(f"Error getting position tracking: {e}")
        return None

async def update_position_phase(ticker_id, phase, remaining_quantity):
    """Update position to trailing phase after initial profit target hit"""
    try:
        from server import position_tracking_collection
        await position_tracking_collection.update_one(
            {'ticker_id': ticker_id},
            {
                '$set': {
                    'phase': phase,
                    'remaining_quantity': remaining_quantity,
                    'phase_updated': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        logger.info(f"✅ Position phase updated: {ticker_id} → {phase}, {remaining_quantity} contracts remaining")
    except Exception as e:
        logger.error(f"Error updating position phase: {e}")

def get_profit_loss_targets(dte, trailing_phase=False, settings_override=None):
    """
    Get profit and loss targets based on DTE and position phase.
    
    Args:
        dte: 0 or 1 (days to expiration)
        trailing_phase: False for initial, True for trailing stop phase
        settings_override: Dict with 'profit' and 'loss' percentages to override defaults
        
    Returns:
        (profit_target_pct, stop_loss_pct, contracts_to_keep)
    """
    if settings_override:
        return (settings_override['profit'], settings_override['loss'], 0)
    
    if not trailing_phase:
        # Initial phase
        if dte == 0:
            # 0DTE: 25% profit, 25% loss, keep 1 contract for trailing
            return (0.25, 0.25, 1)
        else:
            # 1DTE: 20% profit, 25% loss, keep 2 contracts for trailing
            return (0.20, 0.25, 2)
    else:
        # Trailing phase (after initial profit target hit)
        if dte == 0:
            # 0DTE: 75% total profit (50% additional), 5% loss (lock in profit)
            return (0.75, 0.05, 0)
        else:
            # 1DTE: 95% total profit (75% additional), 5% loss (lock in profit)
            return (0.95, 0.05, 0)

# API retry helper for handling Webull API timeouts
async def retry_api_call(func, max_retries=3, delay=2):
    """
    Retry an API call with exponential backoff.
    Handles temporary timeouts without crashing the bot.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = delay * (attempt + 1)
                    logger.warning(f"⚠️ API timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
            # If not a timeout or last attempt, raise the error
            raise
    raise Exception(f"API call failed after {max_retries} retries")

# Keep-alive heartbeat to prevent platform sleep
last_heartbeat = datetime.now(timezone.utc)

async def keep_alive_heartbeat():
    """
    Background task that keeps the bot alive by making actual HTTP requests.
    Only runs during market hours (9:30 AM - 4:00 PM EST, Monday-Friday).
    
    This makes REAL HTTP requests to the backend to signal activity to the platform,
    not just memory updates. This prevents the platform from detecting inactivity.
    """
    global last_heartbeat
    import aiohttp
    
    # Wait a bit before starting to ensure server is ready
    await asyncio.sleep(10)
    
    while True:
        try:
            # Check if we're in market hours
            from pytz import timezone as pytz_timezone
            eastern = pytz_timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            current_time = now_eastern.time()
            is_weekday = now_eastern.weekday() < 5
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            
            # Only update heartbeat during market hours
            if is_weekday and market_open <= current_time <= market_close:
                last_heartbeat = datetime.now(timezone.utc)
                
                # Make actual HTTP request to keep platform active
                try:
                    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8001')
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f'{backend_url}/api/bot/heartbeat', timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                logger.info(f"💓 Keep-alive: Bot active at {last_heartbeat.strftime('%H:%M:%S')} EST (Market hours)")
                            else:
                                logger.warning(f"⚠️ Keep-alive ping returned status {response.status}")
                except Exception as e:
                    logger.warning(f"⚠️ Keep-alive ping failed (will retry): {e}")
                
                await asyncio.sleep(60)  # Ping every minute during market hours
            else:
                # Outside market hours - longer sleep, allow inactivity
                logger.debug(f"💤 Keep-alive paused (outside market hours)")
                await asyncio.sleep(600)  # Check every 10 minutes outside market hours
                
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(60)

# Entry signal persistence functions
async def save_entry_signal_to_db(entry_signal):
    """Save entry signal to MongoDB for persistence across restarts"""
    try:
        from server import entry_signals_collection
        # Add/update the entry signal with a fixed ID so we only keep the latest one
        await entry_signals_collection.replace_one(
            {'_id': 'current'},
            {'_id': 'current', **entry_signal, 'saved_at': datetime.now(timezone.utc).isoformat()},
            upsert=True
        )
        logger.info(f"✅ Entry signal saved to database: {entry_signal['signal_type']}")
    except Exception as e:
        logger.error(f"Error saving entry signal to DB: {e}")

async def load_entry_signal_from_db():
    """Load the last entry signal from MongoDB"""
    try:
        from server import entry_signals_collection
        signal = await entry_signals_collection.find_one({'_id': 'current'})
        if signal:
            signal.pop('_id', None)  # Remove MongoDB _id
            signal.pop('saved_at', None)  # Remove save timestamp
            logger.info(f"✅ Loaded entry signal from database: {signal.get('signal_type')}")
            return signal
        logger.info("No saved entry signal found in database")
        return None
    except Exception as e:
        logger.error(f"Error loading entry signal from DB: {e}")
        return None


# Bot state
class BotState:
    def __init__(self):
        self.running = False
        self.last_check_time = None
        self.last_action = None
        self.market_status = "Unknown"
        self.current_signal = "None"
        self.error_message = None
        self.zones = {
            'demand_top': 0,
            'demand_bottom': 0,
            'supply_top': 0,
            'supply_bottom': 0
        }
        self.orb_status = {
            'upside_broken': False,
            'downside_broken': False,
            'upside_time': None,
            'downside_time': None,
            'high': 0,
            'low': 0
        }
        self.position_status = "No Position"
        self.technical_signals = {
            'rsi_grade': 'D',
            'macd_grade': 'D',
            'candle_grade': 'D',
            'volume_grade': 'D',
            'combined_grade': 'D'
        }
        self.no_trade_reason = "Initializing..."
        self.current_price = 0
        self.last_entry_signal = None  # Store last trade entry details
        self.in_supply_zone = False  # Track if currently in supply zone
        self.in_demand_zone = False  # Track if currently in demand zone
        self.last_zone_notification = None  # Track last zone notification to prevent spam
        
bot_state = BotState()

# Twilio client (initialized when bot starts)
twilio_client = None
smtp_enabled = False
notification_email = None

def initialize_notifications():
    """Initialize notification systems (Twilio SMS and/or Email)"""
    global twilio_client, smtp_enabled, notification_email
    
    # Try to initialize Twilio
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    
    if account_sid and auth_token:
        try:
            twilio_client = Client(account_sid, auth_token)
            logger.info("Twilio client initialized")
        except Exception as e:
            logger.warning(f"Twilio initialization failed: {e}")
    else:
        logger.info("Twilio credentials not found")
    
    # Initialize email notifications
    smtp_enabled = os.getenv('SMTP_ENABLED', 'false').lower() == 'true'
    notification_email = os.getenv('NOTIFICATION_EMAIL')
    
    if smtp_enabled and notification_email:
        logger.info(f"Email notifications enabled for: {notification_email}")
    else:
        logger.info("Email notifications not configured")

def send_email(subject: str, body: str):
    """Send email notification via Gmail SMTP"""
    if not smtp_enabled or not notification_email:
        logger.warning("Email notifications not enabled")
        return
        
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Get SMTP credentials from environment
        mail_username = os.getenv('MAIL_USERNAME')
        mail_password = os.getenv('MAIL_PASSWORD')
        mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        mail_port = int(os.getenv('MAIL_PORT', '587'))
        mail_from = os.getenv('MAIL_FROM', mail_username)
        
        if not mail_username or not mail_password:
            logger.error("Gmail SMTP credentials not configured")
            return
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mail_from
        msg['To'] = notification_email
        
        # Attach body
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        with smtplib.SMTP(mail_server, mail_port, timeout=10) as server:
            server.starttls()  # Upgrade connection to TLS
            server.login(mail_username, mail_password)
            server.sendmail(mail_from, [notification_email], msg.as_string())
        
        logger.info(f"✅ Email sent successfully: {subject}")
        logger.info(f"   To: {notification_email}")
        
        # Also log to file as backup
        log_file = '/app/notifications.log'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] EMAIL SENT TO: {notification_email}\n")
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"{'='*60}\n")
            f.write(f"{body}\n")
            f.write(f"{'='*60}\n")
            
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail SMTP authentication failed - check app password")
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def send_notification(message: str):
    """Send notification via all enabled methods (SMS and/or Email)"""
    # Extract subject from message (first line)
    lines = message.split('\n', 1)
    subject = lines[0] if lines else message
    body = lines[1] if len(lines) > 1 else message
    
    # Try email first (more reliable)
    if smtp_enabled:
        send_email(f"Trading Bot: {subject}", body)
    
    # Try SMS if available
    send_sms(message)

def send_sms(message: str):
    """Send SMS notification via configured provider (Telnyx or Twilio)"""
    sms_provider = os.getenv('SMS_PROVIDER', 'twilio').lower()
    
    if sms_provider == 'telnyx':
        try:
            import telnyx
            api_key = os.getenv('TELNYX_API_KEY')
            from_number = os.getenv('TELNYX_FROM_NUMBER')
            to_number = os.getenv('SMS_TO_NUMBER')
            
            if not api_key or not from_number or not to_number:
                logger.warning("Telnyx credentials not configured")
                return
            
            telnyx.api_key = api_key
            msg = telnyx.Message.create(
                from_=from_number,
                to=to_number,
                text=message
            )
            logger.info(f"✅ SMS sent via Telnyx: {message[:50]}... (ID: {msg.id})")
        except ImportError:
            logger.error("Telnyx SDK not installed. Run: pip install telnyx")
        except Exception as e:
            logger.error(f"Failed to send SMS via Telnyx: {e}")
    
    elif sms_provider == 'twilio':
        if not twilio_client:
            logger.warning("Twilio not initialized, skipping SMS")
            return
            
        try:
            twilio_from = os.getenv('TWILIO_FROM_NUMBER')
            twilio_to = os.getenv('TWILIO_TO_NUMBER')
            
            if not twilio_from or not twilio_to:
                logger.warning("Twilio phone numbers not configured")
                return
                
            msg = twilio_client.messages.create(
                to=twilio_to,
                from_=twilio_from,
                body=message
            )
            logger.info(f"SMS sent via Twilio: {message} (SID: {msg.sid})")
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio: {e}")
    
    else:
        logger.warning(f"Unknown SMS provider: {sms_provider}")

# Trade grades from original bot
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

# Technical analysis functions from original bot
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

def get_candle_grade(df):
    """Calculate candlestick pattern grade"""
    candle_names = talib.get_function_groups()['Pattern Recognition']
    candlesticks = {}
    for candle in candle_names:
        candlesticks[candle] = getattr(talib, candle)(df['open'], df['high'], df['low'], df['close'])
    
    if ('CDL3LINESTRIKE' in candlesticks and candlesticks['CDL3LINESTRIKE'][-1] != 0) or \
       ('CDLKICKINGBYLENGTH' in candlesticks and candlesticks['CDLKICKINGBYLENGTH'][-1] != 0):
        return 'A+'
    if ('CDLEVENINGDOJISTAR' in candlesticks and candlesticks['CDLEVENINGDOJISTAR'][-1] != 0) or \
       ('CDLEVENINGSTAR' in candlesticks and candlesticks['CDLEVENINGSTAR'][-1] != 0) or \
       ('CDLGRAVESTONEDOJI' in candlesticks and candlesticks['CDLGRAVESTONEDOJI'][-1] != 0) or \
       ('CDLHAMMER' in candlesticks and candlesticks['CDLHAMMER'][-1] != 0) or \
       ('CDLHANGINGMAN' in candlesticks and candlesticks['CDLHANGINGMAN'][-1] != 0):
        return 'A'
    if 'CDLMORNINGDOJISTAR' in candlesticks and 'CDLBULLISHHARAMI' in candlesticks:
        return 'B+'
    if 'CDLMORNINGDOJISTAR' in candlesticks or 'CDLBULLISHHARAMI' in candlesticks:
        return 'B'
    if 'CDLBELTHOLD' in candlesticks and 'CDLRISEFALL3METHODS' in candlesticks:
        return 'C+'
    if 'CDLBELTHOLD' in candlesticks or 'CDLRISEFALL3METHODS' in candlesticks:
        return 'C'
    return 'D'


def analyze_supply_demand(df):
    """Analyze supply and demand zones from price data using proper swing detection
    
    Improvements:
    - Uses 15-minute candles for stronger levels
    - 3 trading days lookback (195 candles × 15-min = ~48.75 hours)
    - Tighter 0.25% zone width for precision
    - Requires 3 candles on each side for stronger pivots
    - Returns separate timestamp information for supply and demand zones
    """
    try:
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        timestamps = df.index  # Get timestamps from dataframe index
        
        # Look at last 195 candles (~3 trading days with 15-min candles)
        lookback = min(195, len(df))
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        recent_closes = closes[-lookback:]
        recent_timestamps = timestamps[-lookback:]
        
        # Find swing highs and lows with TIGHTER detection (3 candles on each side)
        # Track both price and timestamp for each swing
        swing_highs = []  # (price, timestamp_index)
        swing_lows = []   # (price, timestamp_index)
        
        for i in range(3, lookback - 3):
            # Check for swing high (3 candles on each side)
            if (recent_highs[i] > recent_highs[i-1] and 
                recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i-3] and
                recent_highs[i] > recent_highs[i+1] and 
                recent_highs[i] > recent_highs[i+2] and
                recent_highs[i] > recent_highs[i+3]):
                swing_highs.append((recent_highs[i], i))
            
            # Check for swing low (3 candles on each side)
            if (recent_lows[i] < recent_lows[i-1] and 
                recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i-3] and
                recent_lows[i] < recent_lows[i+1] and 
                recent_lows[i] < recent_lows[i+2] and
                recent_lows[i] < recent_lows[i+3]):
                swing_lows.append((recent_lows[i], i))
        
        # Find the supply level and its timestamp
        supply_timestamp = None
        if len(swing_highs) > 0:
            # Log all detected swing highs for debugging
            logger.info(f"📊 Found {len(swing_highs)} swing highs:")
            for idx, (price, ts_idx) in enumerate(swing_highs):
                logger.info(f"  Swing High #{idx+1}: ${price:.2f} at {recent_timestamps[ts_idx]}")
            
            # Use the ABSOLUTE HIGHEST swing high from the entire list
            supply_swing = max(swing_highs, key=lambda x: x[0])
            supply_level = supply_swing[0]
            supply_timestamp = recent_timestamps[supply_swing[1]].isoformat()
            logger.info(f"✅ Selected Supply Level (ABSOLUTE HIGHEST): ${supply_level:.2f} at {supply_timestamp}")
        else:
            # Fallback to simple max
            max_idx = np.argmax(recent_highs)
            supply_level = recent_highs[max_idx]
            supply_timestamp = recent_timestamps[max_idx].isoformat()
            logger.info(f"⚠️ No swing highs found - using absolute max: ${supply_level:.2f} at {supply_timestamp}")
        
        # Find the demand level and its timestamp
        demand_timestamp = None
        if len(swing_lows) > 0:
            # Log all detected swing lows for debugging
            logger.info(f"📊 Found {len(swing_lows)} swing lows:")
            for idx, (price, ts_idx) in enumerate(swing_lows):
                logger.info(f"  Swing Low #{idx+1}: ${price:.2f} at {recent_timestamps[ts_idx]}")
            
            # Use the ABSOLUTE LOWEST swing low from the entire list
            demand_swing = min(swing_lows, key=lambda x: x[0])
            demand_level = demand_swing[0]
            demand_timestamp = recent_timestamps[demand_swing[1]].isoformat()
            logger.info(f"✅ Selected Demand Level (ABSOLUTE LOWEST): ${demand_level:.2f} at {demand_timestamp}")
        else:
            # Fallback to simple min
            min_idx = np.argmin(recent_lows)
            demand_level = recent_lows[min_idx]
            demand_timestamp = recent_timestamps[min_idx].isoformat()
            logger.info(f"⚠️ No swing lows found - using absolute min: ${demand_level:.2f} at {demand_timestamp}")
        
        # Create zones with 0.25% width (more precise for intraday SPY)
        supply_top = supply_level
        supply_bottom = supply_level * 0.9975  # 0.25% below high
        
        demand_bottom = demand_level  
        demand_top = demand_level * 1.0025  # 0.25% above low
        
        # CRITICAL: Ensure zones don't overlap
        # If demand top is above supply bottom, there's an issue
        if demand_top > supply_bottom:
            # Create a gap between zones
            midpoint = (supply_bottom + demand_top) / 2
            supply_bottom = midpoint + 0.5  # At least $0.50 gap
            demand_top = midpoint - 0.5
        
        # Calculate overall timestamp range
        first_timestamp = recent_timestamps[0].isoformat() if len(recent_timestamps) > 0 else None
        last_timestamp = recent_timestamps[-1].isoformat() if len(recent_timestamps) > 0 else None
        candle_count = lookback
        
        return {
            'demand_top': demand_top,
            'demand_bottom': demand_bottom,
            'supply_top': supply_top,
            'supply_bottom': supply_bottom,
            'supply_timestamp': supply_timestamp,  # Timestamp of supply swing candle
            'demand_timestamp': demand_timestamp,  # Timestamp of demand swing candle
            'timestamp_start': first_timestamp,    # First candle in lookback
            'timestamp_end': last_timestamp,       # Last candle in lookback
            'candle_count': candle_count
        }
    except Exception as e:
        logger.error(f"Error analyzing supply/demand: {e}")
        return {
            'demand_top': 0, 
            'demand_bottom': 0, 
            'supply_top': 0, 
            'supply_bottom': 0,
            'supply_timestamp': None,
            'demand_timestamp': None,
            'timestamp_start': None,
            'timestamp_end': None,
            'candle_count': 0
        }


def check_orb_breakout(wb, symbol, current_time):
    """Check for Opening Range Breakout in first 15 minutes
    
    ORB levels persist throughout the trading day once calculated.
    If calculated after 9:45 AM, fetches historical data from 9:30-9:45 AM window.
    """
    try:
        from pytz import timezone as pytz_timezone
        eastern = pytz_timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        
        market_open = now_eastern.replace(hour=9, minute=30, second=0, microsecond=0)
        orb_end = market_open + timedelta(minutes=15)
        
        # If we already have ORB levels for today, return None but keep levels
        if bot_state.orb_status.get('high', 0) > 0:
            return None, f"ORB calculated. Levels: ${bot_state.orb_status['low']:.2f} - ${bot_state.orb_status['high']:.2f}"
        
        # If we're before market open, no ORB yet
        if now_eastern < market_open:
            return None, "Market not open yet (ORB at 9:30 AM)"
        
        # Calculate ORB levels (works both during and after the window)
        stockId = wb.get_ticker(symbol)
        
        # If we're past the ORB window, get historical data from 9:30-9:45 AM today
        if now_eastern > orb_end:
            # Calculate timestamp for 9:45 AM today
            orb_end_timestamp = int(orb_end.timestamp())
            df_1m = wb.get_bars(symbol, stockId, 'm1', 15, 1, timeStamp=orb_end_timestamp)
            logger.info(f"📊 Calculating ORB from historical data (9:30-9:45 AM)")
        else:
            # We're in the ORB window - get current data
            df_1m = wb.get_bars(symbol, stockId, 'm1', 20, 1)
        
        if df_1m is None or len(df_1m) < 10:
            return None, "Insufficient data for ORB calculation"
        
        # Calculate opening range (first 10 minutes of 1-min bars)
        orb_high = df_1m['high'][:10].max()
        orb_low = df_1m['low'][:10].min()
        
        # Store ORB levels (persist throughout day)
        bot_state.orb_status['high'] = orb_high
        bot_state.orb_status['low'] = orb_low
        
        logger.info(f"✅ ORB Levels Calculated: High=${orb_high:.2f}, Low=${orb_low:.2f}")
        
        # Check current price for breakout status (only if we have current data)
        if now_eastern <= orb_end and len(df_1m) > 0:
            current_price = df_1m['close'].iloc[-1]
            
            # Check for breakout
            if current_price > orb_high and not bot_state.orb_status['upside_broken']:
                bot_state.orb_status['upside_broken'] = True
                bot_state.orb_status['upside_time'] = now_eastern.isoformat()
                return 'call', f"ORB upside breakout: ${current_price:.2f} > ${orb_high:.2f}"
            
            elif current_price < orb_low and not bot_state.orb_status['downside_broken']:
                bot_state.orb_status['downside_broken'] = True
                bot_state.orb_status['downside_time'] = now_eastern.isoformat()
                return 'put', f"ORB downside breakout: ${current_price:.2f} < ${orb_low:.2f}"
            
            return None, f"ORB range: ${orb_low:.2f} - ${orb_high:.2f}, Current: ${current_price:.2f}"
        
        return None, f"ORB levels set: ${orb_low:.2f} - ${orb_high:.2f}"
        
    except Exception as e:
        logger.error(f"Error checking ORB: {e}")
        return None, f"ORB check error: {str(e)}"


def get_combined_grade(rsi_grade, macd_grade, candle_grade, volume_grade):
    """Calculate combined grade from all technical indicators"""
    grade_values = {'A+': 8, 'A': 7, 'B+': 6, 'B': 5, 'C+': 4, 'C': 3, 'D+': 2, 'D': 1}
    grades = [rsi_grade, macd_grade, candle_grade, volume_grade]
    
    avg_value = sum(grade_values.get(g, 1) for g in grades) / len(grades)
    
    # Convert back to grade
    for grade, value in sorted(grade_values.items(), key=lambda x: -x[1]):
        if avg_value >= value:
            return grade
    return 'D'

def get_volume_candle_grade(df):
    """Calculate volume-based candle grade"""
    df_last = df.tail(3)
    if df_last['volume'].iloc[-1] > df_last['volume'].iloc[-2] and df_last['close'].iloc[-1] > df_last['open'].iloc[-1]:
        return 'A+'
    elif df_last['volume'].iloc[-1] > df_last['volume'].iloc[-2]:
        return 'A'
    elif df_last['close'].iloc[-1] > df_last['open'].iloc[-1]:
        return 'B+'
    elif df_last['volume'].iloc[-1] > df_last['volume'].iloc[-3] and df_last['close'].iloc[-1] > df_last['open'].iloc[-1]:
        return 'B'
    elif df_last['volume'].iloc[-1] > df_last['volume'].iloc[-3]:
        return 'C+'
    elif df_last['close'].iloc[-1] > df_last['open'].iloc[-1]:
        return 'C'
    else:
        return 'D'

async def check_daily_notification_sent(notification_type):
    """Check if we've already sent a notification today"""
    try:
        from server import db
        from pytz import timezone as pytz_timezone
        eastern = pytz_timezone('US/Eastern')
        today = datetime.now(eastern).date().isoformat()
        
        result = await db.daily_notifications.find_one({
            'type': notification_type,
            'date': today
        })
        return result is not None
    except Exception as e:
        logger.error(f"Error checking daily notification: {e}")
        return False

async def mark_daily_notification_sent(notification_type):
    """Mark that we've sent a notification today"""
    try:
        from server import db
        from pytz import timezone as pytz_timezone
        eastern = pytz_timezone('US/Eastern')
        today = datetime.now(eastern).date().isoformat()
        
        await db.daily_notifications.replace_one(
            {'type': notification_type, 'date': today},
            {
                'type': notification_type,
                'date': today,
                'sent_at': datetime.now(timezone.utc).isoformat()
            },
            upsert=True
        )
        logger.info(f"✅ Marked {notification_type} notification as sent for {today}")
    except Exception as e:
        logger.error(f"Error marking daily notification: {e}")

async def run_trading_bot(wb, settings):
    """
    Main trading bot loop - async version of original main() function
    Runs continuously while auto_trading is enabled
    """
    global bot_state
    
    try:
        bot_state.running = True
        bot_state.error_message = None
        logger.info("🤖 Trading bot started")
        
        # Smart daily notification system (not spammy!)
        logger.info("📧 Smart notification system active (once per day)")
        
        # Load persisted entry signal from database
        saved_signal = await load_entry_signal_from_db()
        if saved_signal:
            bot_state.last_entry_signal = saved_signal
        
        # Initialize variables (from original main)
        symbol = 'SPY'
        interval = 'm15'  # 15-minute candles for stronger S/D levels
        ztd, zbd, zts, zbs = 0, 0, 0, 0
        orb_up_time, orb_down_time = '', ''
        orb_break_upside, orb_break_downside = False, False
        zone_order_taken, orb_order_taken = False, False
        zone_broken = False
        zone_break_candle_demand_price, zone_break_candle_supply_price = 0, 0
        
        # Get settings (used as override if needed)
        settings_profit_pct = settings.get('profit_percentage', 50.0) / 100.0
        settings_loss_pct = settings.get('loss_percentage', 25.0) / 100.0
        
        logger.info(f"Bot settings: Profit override={settings_profit_pct*100}%, Loss override={settings_loss_pct*100}%")
        
        # Start keep-alive heartbeat task
        asyncio.create_task(keep_alive_heartbeat())
        logger.info("💓 Keep-alive heartbeat started")
        
        # Calculate initial zones even if market is closed (for display purposes)
        try:
            stockId = wb.get_ticker(symbol)
            df = wb.get_bars(symbol, stockId, interval, 250, 1)  # Increased for 195-candle lookback (3 trading days)
            if df is not None and len(df) >= 50:
                initial_zones = analyze_supply_demand(df)
                bot_state.zones = initial_zones
                bot_state.current_price = df['close'].iloc[-1]
                logger.info(f"Initial zones calculated: Supply ${initial_zones['supply_bottom']:.2f}-${initial_zones['supply_top']:.2f}, Demand ${initial_zones['demand_bottom']:.2f}-${initial_zones['demand_top']:.2f}")
        except Exception as e:
            logger.warning(f"Could not calculate initial zones: {e}")
        
        # Counter to reload settings periodically
        check_counter = 0
        
        while bot_state.running:
            try:
                bot_state.last_check_time = datetime.now()
                
                # Reload settings every 10 iterations (~2.5 minutes)
                check_counter += 1
                if check_counter % 10 == 0:
                    try:
                        from server import settings_collection
                        settings_doc = settings_collection.find_one({})
                        if settings_doc:
                            profit_pct = settings_doc.get('profit_percentage', 50.0) / 100.0
                            loss_pct = settings_doc.get('loss_percentage', 25.0) / 100.0
                            logger.info(f"♻️ Settings reloaded: Profit={profit_pct*100}%, Loss={loss_pct*100}%")
                    except Exception as e:
                        logger.warning(f"Could not reload settings: {e}")
                
                # Check if market is open (in Eastern Time)
                from pytz import timezone as pytz_timezone
                eastern = pytz_timezone('US/Eastern')
                now_eastern = datetime.now(eastern)
                current_time = now_eastern.time()
                is_weekday = now_eastern.weekday() < 5
                market_open = dt_time(9, 30)
                market_close = dt_time(16, 0)
                
                logger.info(f"Current Eastern Time: {now_eastern.strftime('%I:%M %p %Z')} | Weekday: {is_weekday}")
                
                if not is_weekday:
                    bot_state.market_status = "Closed (Weekend)"
                    bot_state.current_signal = "Waiting for market open"
                    logger.info("Weekend - market closed")
                    # Reset ORB status on weekends
                    bot_state.orb_status = {'high': 0, 'low': 0, 'upside_broken': False, 'downside_broken': False}
                    await asyncio.sleep(3600)  # Check every hour on weekends
                    continue
                
                if current_time < market_open:
                    bot_state.market_status = "Pre-Market"
                    bot_state.current_signal = "Waiting for market open at 9:30 AM"
                    logger.info(f"Pre-market - waiting until {market_open}")
                    # Reset ORB status before market opens (new trading day)
                    if bot_state.orb_status.get('high', 0) > 0:
                        logger.info("Resetting ORB levels for new trading day")
                        bot_state.orb_status = {'high': 0, 'low': 0, 'upside_broken': False, 'downside_broken': False}
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                if current_time > market_close:
                    bot_state.market_status = "Closed (After Hours)"
                    bot_state.current_signal = "Market closed for the day"
                    logger.info("Market closed for the day")
                    
                    # Send "Bot Finished" notification once per day (when market closes)
                    if not await check_daily_notification_sent('bot_finished'):
                        # Get some stats for the end-of-day summary
                        try:
                            account_info = wb.get_account()
                            positions_count = len(account_info.get('positions', []))
                            open_orders_count = len(account_info.get('openOrders', []))
                            
                            send_notification(
                                f"🏁 Trading Bot Finished for Today\n"
                                f"Market closed at 4:00 PM EST\n\n"
                                f"Status:\n"
                                f"• Open Positions: {positions_count}\n"
                                f"• Open Orders: {open_orders_count}\n"
                                f"• Bot Status: Idle (waiting for tomorrow)\n\n"
                                f"The bot will resume monitoring when market opens tomorrow at 9:30 AM EST.\n\n"
                                f"Check your dashboard for detailed P/L and trade history."
                            )
                            await mark_daily_notification_sent('bot_finished')
                            logger.info("📧 Daily 'Bot Finished' notification sent")
                        except Exception as e:
                            logger.error(f"Could not send end-of-day notification: {e}")
                    
                    # Keep ORB levels visible after hours (don't reset)
                    await asyncio.sleep(3600)  # Check every hour after close
                    continue
                
                # Market is open
                bot_state.market_status = "Open"
                logger.info(f"✅ Market open - checking for trades at {current_time}")
                
                # Send "Bot Online" notification once per day (first time market opens)
                if not await check_daily_notification_sent('bot_online'):
                    send_notification(
                        f"🤖 Trading Bot Online\n"
                        f"Bot is now active and monitoring SPY for trading signals.\n\n"
                        f"Market Hours: 9:30 AM - 4:00 PM EST\n"
                        f"Started: {now_eastern.strftime('%I:%M %p %Z')}\n\n"
                        f"You'll receive notifications for:\n"
                        f"• Trade entries (calls/puts)\n"
                        f"• Profit target hits\n"
                        f"• Stop loss triggers\n"
                        f"• End of day summary"
                    )
                    await mark_daily_notification_sent('bot_online')
                    logger.info("📧 Daily 'Bot Online' notification sent")
                
                # Get account info with retry logic
                try:
                    account_info = await retry_api_call(lambda: wb.get_account())
                    stockId = await retry_api_call(lambda: wb.get_ticker(symbol))
                except Exception as e:
                    logger.error(f"Failed to get account info after retries: {e}")
                    await asyncio.sleep(30)
                    continue
                
                # Check for positions and orders
                has_position = bool(account_info.get('positions'))
                has_open_orders = bool(account_info.get('openOrders'))
                
                bot_state.position_status = "Position Open" if has_position else "No Position"
                
                # Update current price for display (always, regardless of position status)
                try:
                    quick_quote = await retry_api_call(lambda: wb.get_quote(stock=symbol))
                    bot_state.current_price = float(quick_quote['close'])
                except Exception as e:
                    logger.debug(f"Could not fetch quick quote for price display: {e}")
                
                # ALWAYS calculate ORB levels (even with positions, for display purposes)
                if bot_state.orb_status.get('high', 0) == 0:
                    orb_signal, orb_message = check_orb_breakout(wb, symbol, current_time)
                    logger.info(f"ORB Check: {orb_message}")
                
                if not has_position and not has_open_orders:
                    # Look for entry signals
                    logger.info("No positions - analyzing for entry signals...")
                    
                    # Get price data with retry logic
                    try:
                        df = await retry_api_call(lambda: wb.get_bars(symbol, stockId, interval, 250, 1))
                    except Exception as e:
                        logger.error(f"Failed to get price data after retries: {e}")
                        await asyncio.sleep(30)
                        continue
                    
                    if df is None or len(df) < 50:
                        bot_state.no_trade_reason = "Insufficient price data"
                        bot_state.current_signal = "Waiting for data..."
                        continue
                    
                    current_price = df['close'].iloc[-1]
                    bot_state.current_price = current_price
                    
                    # 1. CHECK ORB (for trading signals)
                    orb_signal, orb_message = check_orb_breakout(wb, symbol, current_time)
                    logger.info(f"ORB Check: {orb_message}")
                    
                    if orb_signal:
                        # ORB breakout detected - TAKE THE TRADE!
                        logger.info(f"🚨 ORB BREAKOUT DETECTED: {orb_signal.upper()}")
                        bot_state.current_signal = f"ORB {orb_signal} breakout!"
                        bot_state.no_trade_reason = f"Executing ORB {orb_signal} trade"
                        
                        # Execute ORB trade
                        try:
                            if orb_signal == 'call':
                                success, dte = execute_call_trade(wb, symbol, 'A+', account_info, signal_type='orb')
                                if success:
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'ORB Breakout',
                                        'reasons': orb_message,
                                        'zones': None,
                                        'grade': 'A+',
                                        'entry_price': current_price,
                                        'direction': 'CALL',
                                        'dte': dte,
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    await save_entry_signal_to_db(bot_state.last_entry_signal)
                                    send_notification(f"ORB Call Trade ({dte}DTE)\n{orb_message}\nORB breakout strategy")
                                    bot_state.last_action = f"ORB CALL at {current_time} ({dte}DTE)"
                                    logger.info(f"✅ ORB call order placed ({dte}DTE)")
                            elif orb_signal == 'put':
                                success, dte = execute_put_trade(wb, symbol, 'A+', account_info, signal_type='orb')
                                if success:
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'ORB Breakout',
                                        'reasons': orb_message,
                                        'zones': None,
                                        'grade': 'A+',
                                        'entry_price': current_price,
                                        'direction': 'PUT',
                                        'dte': dte,
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    await save_entry_signal_to_db(bot_state.last_entry_signal)
                                    send_notification(f"ORB Put Trade ({dte}DTE)\n{orb_message}\nORB breakout strategy")
                                    bot_state.last_action = f"ORB PUT at {current_time} ({dte}DTE)"
                                    logger.info(f"✅ ORB put order placed ({dte}DTE)")
                        except Exception as e:
                            logger.error(f"Error executing ORB trade: {e}", exc_info=True)
                            bot_state.no_trade_reason = f"ORB trade error: {str(e)}"
                        
                        continue  # Move to next iteration
                    
                    # 2. ANALYZE SUPPLY/DEMAND ZONES
                    zones = analyze_supply_demand(df)
                    bot_state.zones = zones
                    
                    in_demand_zone = zones['demand_bottom'] <= current_price <= zones['demand_top']
                    in_supply_zone = zones['supply_bottom'] <= current_price <= zones['supply_top']
                    
                    zone_signal = None
                    if in_demand_zone:
                        zone_signal = 'call'
                        logger.info(f"💚 Price in DEMAND zone: ${zones['demand_bottom']:.2f} - ${zones['demand_top']:.2f}")
                    elif in_supply_zone:
                        zone_signal = 'put'
                        logger.info(f"🔴 Price in SUPPLY zone: ${zones['supply_bottom']:.2f} - ${zones['supply_top']:.2f}")
                    
                    # 3. CALCULATE TECHNICAL GRADES
                    try:
                        rsi_grade = get_rsi_grade(df)
                        macd_grade = get_macd_grade(df)
                        candle_grade = get_candle_grade(df)
                        volume_grade = get_volume_candle_grade(df)
                        combined_grade = get_combined_grade(rsi_grade, macd_grade, candle_grade, volume_grade)
                        
                        bot_state.technical_signals = {
                            'rsi_grade': rsi_grade,
                            'macd_grade': macd_grade,
                            'candle_grade': candle_grade,
                            'volume_grade': volume_grade,
                            'combined_grade': combined_grade
                        }
                        
                        logger.info(f"📊 Grades: RSI={rsi_grade}, MACD={macd_grade}, Candle={candle_grade}, Volume={volume_grade}, Combined={combined_grade}")
                    
                    except Exception as e:
                        logger.error(f"Error calculating grades: {e}")
                        bot_state.no_trade_reason = f"Error analyzing technicals: {str(e)}"
                        continue
                    
                    # 4. DETERMINE TRADE SIGNAL
                    trade_signal = None
                    trade_reason = []
                    
                    # Grade comparison helper (alphabetic comparison is backwards for grades!)
                    grade_values = {'A+': 8, 'A': 7, 'B+': 6, 'B': 5, 'C+': 4, 'C': 3, 'D+': 2, 'D': 1}
                    current_grade_value = grade_values.get(combined_grade, 1)
                    
                    # ONLY TRADE ON ZONE-BASED SIGNALS (ORB or Supply/Demand zones)
                    # Pure technical signals are DISABLED per user request
                    
                    # Zone-based signals (require C or higher = value >= 3)
                    if zone_signal == 'call' and current_grade_value >= 3:
                        trade_signal = 'call'
                        trade_reason.append(f"Demand zone bounce (Grade: {combined_grade})")
                        trade_reason.append(f"Price: ${current_price:.2f} in demand zone ${zones['demand_bottom']:.2f}-${zones['demand_top']:.2f}")
                    elif zone_signal == 'put' and current_grade_value >= 3:
                        trade_signal = 'put'
                        trade_reason.append(f"Supply zone rejection (Grade: {combined_grade})")
                        trade_reason.append(f"Price: ${current_price:.2f} in supply zone ${zones['supply_bottom']:.2f}-${zones['supply_top']:.2f}")
                    
                    # DISABLED: Pure technical signals (too random, user preference)
                    # Only ORB breakouts and supply/demand zone trades are allowed
                    else:
                        # Log why we're not trading
                        rsi = talib.RSI(df['close'])
                        rsi_value = rsi.iloc[-1]
                        
                        if not zone_signal:
                            bot_state.no_trade_reason = f"Not in supply/demand zone. Grade: {combined_grade}, RSI: {rsi_value:.1f}"
                            logger.info(f"❌ No trade: Not in zone (RSI={rsi_value:.1f}, Grade={combined_grade})")
                        else:
                            bot_state.no_trade_reason = f"In zone but grade too low. Grade: {combined_grade} (need C+ or higher)"
                            logger.info(f"❌ No trade: Grade {combined_grade} too low for zone trade")
                    
                    # 5. EXECUTE OR LOG WHY NOT
                    if trade_signal:
                        logger.info(f"🎯 TRADE SIGNAL: {trade_signal.upper()} - {', '.join(trade_reason)}")
                        bot_state.current_signal = f"{trade_signal.upper()} signal detected!"
                        bot_state.no_trade_reason = f"Executing {trade_signal} trade"
                        
                        # EXECUTE ACTUAL TRADE
                        try:
                            if trade_signal == 'call':
                                success, dte = execute_call_trade(wb, symbol, combined_grade, account_info, signal_type='zone')
                                if success:
                                    # Store entry details with technical breakdown
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'Zone Trade' if zone_signal else 'Technical',
                                        'reasons': ', '.join(trade_reason),
                                        'zones': zones.copy() if zone_signal else None,
                                        'grade': combined_grade,
                                        'grade_breakdown': {
                                            'rsi': rsi_grade,
                                            'macd': macd_grade,
                                            'candle': candle_grade,
                                            'volume': volume_grade
                                        },
                                        'entry_price': current_price,
                                        'direction': 'CALL',
                                        'dte': dte,
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    await save_entry_signal_to_db(bot_state.last_entry_signal)
                                    
                                    send_notification(f"Call Trade Executed ({dte}DTE)\n{', '.join(trade_reason)}\nPrice: ${current_price:.2f}\nGrade: {combined_grade}")
                                    bot_state.last_action = f"Placed CALL order at ${current_price:.2f} ({dte}DTE)"
                                    logger.info(f"✅ Call order placed successfully ({dte}DTE)")
                                else:
                                    logger.error("❌ Failed to place call order")
                                    bot_state.no_trade_reason = "Order placement failed"
                            
                            elif trade_signal == 'put':
                                success, dte = execute_put_trade(wb, symbol, combined_grade, account_info, signal_type='zone')
                                if success:
                                    # Store entry details with technical breakdown
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'Zone Trade' if zone_signal else 'Technical',
                                        'reasons': ', '.join(trade_reason),
                                        'zones': zones.copy() if zone_signal else None,
                                        'grade': combined_grade,
                                        'grade_breakdown': {
                                            'rsi': rsi_grade,
                                            'macd': macd_grade,
                                            'candle': candle_grade,
                                            'volume': volume_grade
                                        },
                                        'entry_price': current_price,
                                        'direction': 'PUT',
                                        'dte': dte,
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    await save_entry_signal_to_db(bot_state.last_entry_signal)
                                    
                                    send_notification(f"Put Trade Executed ({dte}DTE)\n{', '.join(trade_reason)}\nPrice: ${current_price:.2f}\nGrade: {combined_grade}")
                                    bot_state.last_action = f"Placed PUT order at ${current_price:.2f} ({dte}DTE)"
                                    logger.info(f"✅ Put order placed successfully ({dte}DTE)")
                                else:
                                    logger.error("❌ Failed to place put order")
                                    bot_state.no_trade_reason = "Order placement failed"
                        
                        except Exception as e:
                            logger.error(f"Error executing trade: {e}", exc_info=True)
                            bot_state.no_trade_reason = f"Trade execution error: {str(e)}"
                        
                    else:
                        # Explain why no trade
                        reasons = []
                        if not zone_signal:
                            reasons.append(f"Not in supply/demand zone (Price: ${current_price:.2f})")
                        
                        # Check grade properly (not alphabetical comparison)
                        if zone_signal and current_grade_value < 3:
                            reasons.append(f"Grade too low for zone trade ({combined_grade}, need C+)")
                        elif not zone_signal and current_grade_value < 5:
                            reasons.append(f"Grade too low for technical trade ({combined_grade}, need B+)")
                        
                        if not orb_signal:
                            reasons.append(orb_message)
                        
                        bot_state.no_trade_reason = " | ".join(reasons) if reasons else "Scanning for setups..."
                        bot_state.current_signal = "Scanning for entry signals..."
                        logger.info(f"No trade: {bot_state.no_trade_reason}")
                    
                elif has_position and not has_open_orders:
                    # Monitor position for exit with trailing stop logic
                    logger.info("Monitoring open position...")
                    position = account_info['positions'][0]
                    current_ticker = position['ticker']['symbol']
                    
                    # Check if entry signal is for current position (not old position)
                    if bot_state.last_entry_signal:
                        # If stored ticker doesn't match current position, it's old - clear it
                        stored_ticker = bot_state.last_entry_signal.get('ticker_symbol')
                        if stored_ticker and stored_ticker != current_ticker:
                            logger.info(f"Clearing old entry signal (old ticker: {stored_ticker}, current: {current_ticker})")
                            bot_state.last_entry_signal = None
                        elif not stored_ticker:
                            # No ticker stored - add it now
                            bot_state.last_entry_signal['ticker_symbol'] = current_ticker
                            logger.info(f"Added ticker symbol to entry signal: {current_ticker}")
                    
                    # Backfill entry signal if missing
                    if not bot_state.last_entry_signal:
                        logger.info("Entry signal missing - attempting to backfill from order history")
                        backfill_entry_signal(wb)
                    
                    cost_price = float(position['costPrice'])
                    current_price = float(position['lastPrice'])
                    ticker_id = position['ticker']['tickerId']
                    quantity = int(position['position'])
                    
                    # Get position tracking data
                    tracking = await get_position_tracking(ticker_id)
                    
                    # Check if this is a new position vs continuation of existing position
                    # If tracking exists but quantity is different from remaining_quantity, it's a NEW position
                    is_new_position = False
                    if not tracking:
                        is_new_position = True
                    elif tracking.get('remaining_quantity', 0) != quantity:
                        # Quantity mismatch means this is a new position (not a continuation)
                        is_new_position = True
                        logger.info(f"Detected NEW position (qty={quantity}) vs old tracking (remaining_qty={tracking.get('remaining_quantity')})")
                    
                    if is_new_position:
                        # New position - create fresh tracking data with 'initial' phase
                        dte = bot_state.last_entry_signal.get('dte', 1) if bot_state.last_entry_signal else 1
                        await save_position_tracking(ticker_id, dte, cost_price, quantity, 
                                                     bot_state.last_entry_signal.get('direction', 'UNKNOWN') if bot_state.last_entry_signal else 'UNKNOWN')
                        tracking = await get_position_tracking(ticker_id)
                        logger.info(f"✅ New position tracking created: {ticker_id}, phase=initial, qty={quantity}")
                    
                    dte = tracking['dte']
                    phase = tracking.get('phase', 'initial')
                    initial_quantity = tracking.get('initial_quantity', quantity)
                    
                    # Check if user enabled custom override in settings
                    use_override = settings.get('override_profit_loss', False)
                    
                    if use_override:
                        profit_target_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(
                            dte, trailing_phase=(phase == 'trailing'),
                            settings_override={'profit': settings_profit_pct, 'loss': settings_loss_pct}
                        )
                    else:
                        # Check if quantity is too low for trailing stops
                        min_quantity = 2 if dte == 0 else 3  # Need at least 2 for 0DTE, 3 for 1DTE
                        if initial_quantity < min_quantity and phase == 'initial':
                            logger.info(f"⚠️ Quantity too low ({initial_quantity}) for trailing stops, using regular targets")
                            profit_target_pct, stop_loss_pct, contracts_to_keep = (0.25 if dte == 0 else 0.20, 0.25, 0)
                        else:
                            profit_target_pct, stop_loss_pct, contracts_to_keep = get_profit_loss_targets(
                                dte, trailing_phase=(phase == 'trailing')
                            )
                    
                    target_price = cost_price * (1 + profit_target_pct)
                    stop_loss_price = cost_price * (1 - stop_loss_pct)
                    pnl_pct = ((current_price - cost_price) / cost_price) * 100
                    
                    logger.info(f"Position P/L: {pnl_pct:.2f}% ({dte}DTE, {phase} phase, Target: +{profit_target_pct*100}%, Stop: -{stop_loss_pct*100}%)")
                    bot_state.current_signal = f"Monitoring {dte}DTE position ({phase}): P/L {pnl_pct:.2f}%"
                    
                    # CHECK FOR EXIT CONDITIONS
                    if current_price >= target_price:
                        logger.info(f"🎯 PROFIT TARGET REACHED! P/L: {pnl_pct:.2f}%")
                        try:
                            quote = wb.get_option_quote(stock='SPY', optionId=ticker_id)
                            bid_price = float(quote['data'][0]['bidList'][0]['price'])
                            ask_price = float(quote['data'][0]['askList'][0]['price'])
                            mid_price = (bid_price + ask_price) / 2
                            
                            # Determine how many contracts to sell
                            if phase == 'initial' and contracts_to_keep > 0 and quantity > contracts_to_keep:
                                # Initial profit target - sell all but X contracts
                                contracts_to_sell = quantity - contracts_to_keep
                                logger.info(f"📊 Trailing stop strategy: Selling {contracts_to_sell} contracts, keeping {contracts_to_keep} for trailing")
                                
                                wb.place_order_option(
                                    optionId=ticker_id,
                                    lmtPrice=mid_price,
                                    stpPrice=str(float(mid_price) - 0.25),
                                    action='SELL',
                                    orderType='MKT',
                                    enforce='GTC',
                                    quant=contracts_to_sell
                                )
                                logger.info(f"✅ Partial SELL order placed: {contracts_to_sell} contracts at market price")
                                send_notification(f"Profit Target Hit! ({dte}DTE)\nSold {contracts_to_sell}/{quantity} contracts at {pnl_pct:.2f}% profit\nKeeping {contracts_to_keep} for trailing stop\nEntry: ${cost_price:.2f}, Exit: ${current_price:.2f}")
                                
                                # Update to trailing phase
                                await update_position_phase(ticker_id, 'trailing', contracts_to_keep)
                                bot_state.last_action = f"SOLD {contracts_to_sell} at +{pnl_pct:.2f}% profit (keeping {contracts_to_keep})"
                            else:
                                # Trailing profit target or regular sell - sell all remaining
                                logger.info(f"📊 Selling all {quantity} remaining contracts")
                                wb.place_order_option(
                                    optionId=ticker_id,
                                    lmtPrice=mid_price,
                                    stpPrice=str(float(mid_price) - 0.25),
                                    action='SELL',
                                    orderType='MKT',
                                    enforce='GTC',
                                    quant=quantity
                                )
                                logger.info(f"✅ SELL order placed: {quantity} contracts at market price")
                                phase_msg = " (Trailing Stop)" if phase == 'trailing' else ""
                                send_notification(f"Profit Target Hit{phase_msg}! ({dte}DTE)\nSold {quantity} contracts at {pnl_pct:.2f}% profit\nEntry: ${cost_price:.2f}, Exit: ${current_price:.2f}")
                                bot_state.last_action = f"SOLD {quantity} at +{pnl_pct:.2f}% profit{phase_msg}"
                        except Exception as e:
                            logger.error(f"❌ Error placing SELL order: {e}")
                            
                    elif current_price <= stop_loss_price:
                        logger.info(f"🛑 STOP LOSS HIT! P/L: {pnl_pct:.2f}%")
                        try:
                            quote = wb.get_option_quote(stock='SPY', optionId=ticker_id)
                            bid_price = float(quote['data'][0]['bidList'][0]['price'])
                            ask_price = float(quote['data'][0]['askList'][0]['price'])
                            mid_price = (bid_price + ask_price) / 2
                            
                            # Sell all remaining contracts
                            wb.place_order_option(
                                optionId=ticker_id,
                                lmtPrice=mid_price,
                                stpPrice=str(float(mid_price) - 0.25),
                                action='SELL',
                                orderType='MKT',
                                enforce='GTC',
                                quant=quantity
                            )
                            phase_msg = f" ({phase} phase)" if phase == 'trailing' else ""
                            loss_or_profit = "profit" if pnl_pct > 0 else "loss"
                            logger.info(f"✅ STOP LOSS SELL order placed: {quantity} contracts at market price")
                            send_notification(f"Stop Loss Triggered{phase_msg}! ({dte}DTE)\nSold {quantity} contracts at {pnl_pct:.2f}% {loss_or_profit}\nEntry: ${cost_price:.2f}, Exit: ${current_price:.2f}")
                            bot_state.last_action = f"SOLD {quantity} at {pnl_pct:.2f}% {loss_or_profit} (stop loss)"
                        except Exception as e:
                            logger.error(f"❌ Error placing STOP LOSS order: {e}")
                
                # Clear any temporary errors after successful iteration
                if bot_state.error_message and "timeout" in bot_state.error_message.lower():
                    bot_state.error_message = None
                
                # Sleep before next check (5 seconds for responsive price updates)
                await asyncio.sleep(5)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error in trading loop iteration: {error_msg}", exc_info=True)
                
                # Only show persistent errors, not temporary timeouts
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    logger.warning(f"⚠️ Temporary API timeout - will retry")
                    bot_state.error_message = None  # Don't display timeout errors
                else:
                    bot_state.error_message = error_msg  # Show other errors
                
                await asyncio.sleep(60)  # Wait a bit longer on errors
                
    except Exception as e:
        logger.error(f"Trading bot crashed: {e}", exc_info=True)
        bot_state.error_message = str(e)
        send_notification(f"Bot Error\nTrading bot stopped due to error: {str(e)}")
    finally:
        bot_state.running = False
        logger.info("🛑 Trading bot stopped")

def execute_call_trade(wb, symbol, trade_grade, account_info, signal_type='zone'):
    """Execute call option trade based on your original buy_call logic"""
    try:
        # Filter options for calls with signal type for DTE selection
        filtered_chain, dte = filter_options_for_trade(wb, symbol, 'call', signal_type)
        
        if not filtered_chain or dte is None:
            logger.error("No suitable call options found")
            return False, None
        
        # Calculate order quantity based on trade grade and account value
        account_value = float(account_info['accountMembers'][1]['value'])
        trade_pct = trade_grades.get(trade_grade, {'trade_pct': 0.10})['trade_pct']
        
        option_price = wb.get_option_quote(stock=symbol, optionId=filtered_chain[0]['call']['tickerId'])['data'][0]['askList'][0]['price']
        order_quantity = float((account_value * trade_pct) / (float(option_price) * 100))
        order_quantity = math.floor(order_quantity)
        
        # Ensure at least 1 contract
        if order_quantity < 1:
            for option in filtered_chain:
                option_price = wb.get_option_quote(stock=symbol, optionId=option['call']['tickerId'])['data'][0]['askList'][0]['price']
                new_order_quantity = (account_value * trade_pct) / (float(option_price) * 100)
                if new_order_quantity >= 1:
                    filtered_chain.remove(option)
                    filtered_chain.insert(0, option)
                    order_quantity = math.floor(new_order_quantity)
                    break
            else:
                logger.error("Cannot afford even 1 contract")
                return False
        
        # Get bid/ask to calculate mid price
        option_id = filtered_chain[0]['call']['tickerId']
        quote = wb.get_option_quote(stock=symbol, optionId=option_id)
        bid_price = float(quote['data'][0]['bidList'][0]['price'])
        ask_price = float(quote['data'][0]['askList'][0]['price'])
        mid_price = (bid_price + ask_price) / 2
        
        # Place market order for immediate fill
        logger.info(f"Placing MARKET call order: {order_quantity} contracts @ {dte}DTE (reference price: ${mid_price:.2f}, bid: ${bid_price:.2f}, ask: ${ask_price:.2f})")
        order_result = wb.place_order_option(
            optionId=option_id,
            lmtPrice=mid_price,  # Required by API but not used for MKT orders
            stpPrice=str(float(mid_price) - 0.25),
            action='BUY',
            orderType='MKT',  # Market order for immediate fill
            enforce='GTC',
            quant=order_quantity
        )
        
        # Validate order was actually placed
        if not order_result or not order_result.get('success', False):
            logger.error(f"❌ Order placement failed: {order_result}")
            return False, None
        
        logger.info(f"✅ Order confirmed by Webull API: {order_result}")
        return True, dte  # Return DTE for position tracking
        
    except Exception as e:
        logger.error(f"Error in execute_call_trade: {e}", exc_info=True)
        return False, None


def execute_put_trade(wb, symbol, trade_grade, account_info, signal_type='zone'):
    """Execute put option trade based on your original buy_put logic"""
    try:
        # Filter options for puts with signal type for DTE selection
        filtered_chain, dte = filter_options_for_trade(wb, symbol, 'put', signal_type)
        
        if not filtered_chain or dte is None:
            logger.error("No suitable put options found")
            return False, None
        
        # Calculate order quantity
        account_value = float(account_info['accountMembers'][1]['value'])
        trade_pct = trade_grades.get(trade_grade, {'trade_pct': 0.10})['trade_pct']
        
        option_price = wb.get_option_quote(stock=symbol, optionId=filtered_chain[0]['put']['tickerId'])['data'][0]['askList'][0]['price']
        order_quantity = float((account_value * trade_pct) / (float(option_price) * 100))
        order_quantity = math.floor(order_quantity)
        
        # Ensure at least 1 contract
        if order_quantity < 1:
            for option in filtered_chain:
                option_price = wb.get_option_quote(stock=symbol, optionId=option['put']['tickerId'])['data'][0]['askList'][0]['price']
                new_order_quantity = (account_value * trade_pct) / (float(option_price) * 100)
                if new_order_quantity >= 1:
                    filtered_chain.remove(option)
                    filtered_chain.insert(0, option)
                    order_quantity = math.floor(new_order_quantity)
                    break
            else:
                logger.error("Cannot afford even 1 contract")
                return False
        
        # Get bid/ask to calculate mid price
        option_id = filtered_chain[0]['put']['tickerId']
        quote = wb.get_option_quote(stock=symbol, optionId=option_id)
        bid_price = float(quote['data'][0]['bidList'][0]['price'])
        ask_price = float(quote['data'][0]['askList'][0]['price'])
        mid_price = (bid_price + ask_price) / 2
        
        # Place market order for immediate fill
        logger.info(f"Placing MARKET put order: {order_quantity} contracts @ {dte}DTE (reference price: ${mid_price:.2f}, bid: ${bid_price:.2f}, ask: ${ask_price:.2f})")
        order_result = wb.place_order_option(
            optionId=option_id,
            lmtPrice=mid_price,  # Required by API but not used for MKT orders
            stpPrice=str(float(mid_price) - 0.25),
            action='BUY',
            orderType='MKT',  # Market order for immediate fill
            enforce='GTC',
            quant=order_quantity
        )
        
        # Validate order was actually placed
        if not order_result or not order_result.get('success', False):
            logger.error(f"❌ Order placement failed: {order_result}")
            return False, None
        
        logger.info(f"✅ Order confirmed by Webull API: {order_result}")
        return True, dte  # Return DTE for position tracking
        
    except Exception as e:
        logger.error(f"Error in execute_put_trade: {e}", exc_info=True)
        return False, None


def filter_options_for_trade(wb, symbol, option_type, signal_type='zone'):
    """
    Filter SPY options based on strike price and volume with dynamic expiry selection
    
    Expiry Logic:
    - ORB signals: Always 0DTE (same day)
    - Zone signals: 0DTE if before 1 PM EST, 1DTE if after 1 PM EST
    """
    try:
        from pytz import timezone as pytz_timezone
        eastern = pytz_timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        current_time = now_eastern.time()
        current_date = now_eastern.date()
        
        # Determine target expiration based on signal type and time
        if signal_type == 'orb':
            # ORB trades: Always 0DTE
            target_dte = 0
            logger.info("🎯 ORB trade: Selecting 0DTE options")
        else:
            # Zone trades: 0DTE before 1 PM, 1DTE after 1 PM EST
            cutoff_time = dt_time(13, 0)  # 1 PM EST
            if current_time < cutoff_time:
                target_dte = 0
                logger.info("📈 Zone trade before 1 PM: Selecting 0DTE options")
            else:
                target_dte = 1
                logger.info("📈 Zone trade after 1 PM: Selecting 1DTE options")
        
        # Get expiration dates
        expiration_dates = wb.get_options_expiration_dates(symbol)
        
        # Find expiration matching target DTE
        target_date = current_date + timedelta(days=target_dte)
        
        # Find closest matching expiration
        expiration_date = None
        for exp_data in expiration_dates:
            exp_date = datetime.strptime(exp_data['date'], '%Y-%m-%d').date()
            if exp_date >= target_date:
                expiration_date = exp_data['date']
                break
        
        if not expiration_date:
            logger.error(f"No expiration found for {target_dte}DTE")
            return None, None
        
        logger.info(f"Selected expiration: {expiration_date} ({target_dte}DTE)")
        
        # Get current price and calculate strike range
        current_price = float(wb.get_quote(stock=symbol)['close'])
        rounded_price = round(current_price)
        
        if option_type == 'call':
            call_options = wb.get_options(stock=symbol, count=-1, direction='call', expireDate=expiration_date)
            call_options = [opt for opt in call_options if rounded_price <= float(opt['strikePrice']) <= rounded_price + 5]
            call_options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['call']['tickerId'])['data'][0]['volume']), reverse=True)
            return call_options, target_dte
        
        elif option_type == 'put':
            put_options = wb.get_options(stock=symbol, count=-1, direction='put', expireDate=expiration_date)
            put_options = [opt for opt in put_options if rounded_price - 5 <= float(opt['strikePrice']) <= rounded_price]
            put_options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['put']['tickerId'])['data'][0]['volume']), reverse=True)
            return put_options, target_dte
        
    except Exception as e:
        logger.error(f"Error filtering options: {e}")
        return None, None


def backfill_entry_signal(wb):
    """Backfill entry signal data for current position from order history"""
    try:
        logger.info("🔄 Attempting to backfill entry signal for current position...")
        
        # Get current positions
        account_info = wb.get_account()
        positions = account_info.get('positions', [])
        
        if not positions:
            logger.info("No positions to backfill")
            return False
        
        # Get the most recent position (assuming only one position at a time)
        position = positions[0]
        ticker_symbol = position['ticker']['symbol']
        
        # Get order history to find when this position was opened
        orders = wb.get_history_orders(1)  # Paper trading account
        
        # Find the BUY order for this ticker
        buy_order = None
        for order in orders:
            if (order.get('action') == 'BUY' and 
                order.get('ticker', {}).get('symbol') == ticker_symbol and
                order.get('status') == 'Filled'):
                buy_order = order
                break
        
        if not buy_order:
            logger.warning(f"Could not find BUY order for {ticker_symbol}")
            return False
        
        # Get the filled time (timestamp in milliseconds)
        filled_time_ms = buy_order.get('filledTime0')
        if not filled_time_ms:
            logger.warning("No filled time found in order")
            return False
        
        # Convert to seconds for get_bars
        filled_timestamp = int(filled_time_ms / 1000)
        
        logger.info(f"Found BUY order filled at timestamp: {filled_timestamp}")
        
        # Get SPY price at that time (get bars around that timestamp)
        stockId = wb.get_ticker('SPY')
        df = wb.get_bars('SPY', stockId, 'm15', 200, 1, timeStamp=filled_timestamp)
        
        if df is None or len(df) == 0:
            logger.warning("Could not fetch historical SPY data")
            return False
        
        # Get the price closest to the order time
        entry_price = df['close'].iloc[-1]
        
        # Calculate zones at that time
        zones = analyze_supply_demand(df)
        
        # Determine if it was a zone trade
        in_demand_zone = zones['demand_bottom'] <= entry_price <= zones['demand_top']
        in_supply_zone = zones['supply_bottom'] <= entry_price <= zones['supply_top']
        
        # Determine direction from option type
        option_type = position.get('ticker', {}).get('optionSymbol', '')
        is_call = 'C' in ticker_symbol[-9:]  # Check last part for C or P
        direction = 'CALL' if is_call else 'PUT'
        
        signal_type = 'Zone Trade' if (in_demand_zone or in_supply_zone) else 'Manual/Historical'
        
        # Format the filled time properly
        filled_time = buy_order.get('filledTime', 'Unknown')
        
        # Create backfilled entry signal
        bot_state.last_entry_signal = {
            'signal_type': signal_type,
            'reasons': f'Position opened at {filled_time} {"in demand zone" if in_demand_zone else "in supply zone" if in_supply_zone else ""}',
            'zones': zones.copy() if (in_demand_zone or in_supply_zone) else None,
            'grade': 'N/A',
            'entry_price': float(entry_price),
            'direction': direction,
            'timestamp': filled_time,
            'ticker_symbol': ticker_symbol,  # Store ticker to identify position
            'backfilled': True
        }
        
        logger.info(f"✅ Entry signal backfilled: SPY ${entry_price:.2f}, {direction}, {signal_type}")
        return True
        
    except Exception as e:
        logger.error(f"Error backfilling entry signal: {e}", exc_info=True)
        return False


def get_bot_status():
    """Get current bot status for API endpoint"""
    return {
        'running': bot_state.running,
        'last_check_time': bot_state.last_check_time.isoformat() if bot_state.last_check_time else None,
        'last_action': bot_state.last_action,
        'market_status': bot_state.market_status,
        'current_signal': bot_state.current_signal,
        'position_status': bot_state.position_status,
        'error_message': bot_state.error_message,
        'zones': bot_state.zones,
        'orb_status': bot_state.orb_status,
        'technical_signals': bot_state.technical_signals,
        'no_trade_reason': bot_state.no_trade_reason,
        'current_price': bot_state.current_price,
        'last_entry_signal': bot_state.last_entry_signal
    }
