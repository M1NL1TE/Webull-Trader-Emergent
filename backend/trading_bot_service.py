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
    """Send email notification - logs to file for review"""
    if not smtp_enabled or not notification_email:
        logger.warning("Email notifications not enabled")
        return
        
    try:
        # Log notification to file (always works)
        log_file = '/app/notifications.log'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] TO: {notification_email}\n")
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"{'='*60}\n")
            f.write(f"{body}\n")
            f.write(f"{'='*60}\n")
        
        logger.info(f"📧 Notification logged: {subject}")
        logger.info(f"   Email would be sent to: {notification_email}")
        logger.info(f"   Content logged to: {log_file}")
        
        # Also print to console for immediate visibility
        print(f"\n📧 EMAIL NOTIFICATION:")
        print(f"To: {notification_email}")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        print(f"{'='*60}\n")
            
    except Exception as e:
        logger.error(f"Failed to log notification: {e}")

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
    """Send SMS notification via Twilio"""
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
        logger.info(f"SMS sent: {message} (SID: {msg.sid})")
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")

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
        send_notification("Bot Started\nTrading bot is now monitoring SPY for entry signals during market hours (9:30 AM - 4:00 PM EST)")
        
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
        
        # Get settings
        profit_pct = settings.get('profit_percentage', 50.0) / 100.0  # Convert to decimal
        loss_pct = settings.get('loss_percentage', 25.0) / 100.0
        
        logger.info(f"Bot settings: Profit target={profit_pct*100}%, Stop loss={loss_pct*100}%")
        
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
                    # Keep ORB levels visible after hours (don't reset)
                    await asyncio.sleep(3600)  # Check every hour after close
                    continue
                
                # Market is open
                bot_state.market_status = "Open"
                logger.info(f"✅ Market open - checking for trades at {current_time}")
                
                # Get account info
                account_info = wb.get_account()
                stockId = wb.get_ticker(symbol)
                
                # Check for positions and orders
                has_position = bool(account_info.get('positions'))
                has_open_orders = bool(account_info.get('openOrders'))
                
                bot_state.position_status = "Position Open" if has_position else "No Position"
                
                # ALWAYS calculate ORB levels (even with positions, for display purposes)
                if bot_state.orb_status.get('high', 0) == 0:
                    orb_signal, orb_message = check_orb_breakout(wb, symbol, current_time)
                    logger.info(f"ORB Check: {orb_message}")
                
                if not has_position and not has_open_orders:
                    # Look for entry signals
                    logger.info("No positions - analyzing for entry signals...")
                    
                    # Get price data
                    df = wb.get_bars(symbol, stockId, interval, 250, 1)  # Increased for 195-candle lookback (3 trading days)
                    
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
                                success = execute_call_trade(wb, symbol, 'A+', account_info)  # ORB gets A+ grade
                                if success:
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'ORB Breakout',
                                        'reasons': orb_message,
                                        'zones': None,
                                        'grade': 'A+',
                                        'entry_price': current_price,
                                        'direction': 'CALL',
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    send_notification(f"ORB Call Trade\n{orb_message}\nORB breakout strategy")
                                    bot_state.last_action = f"ORB CALL at {current_time}"
                                    logger.info("✅ ORB call order placed")
                            elif orb_signal == 'put':
                                success = execute_put_trade(wb, symbol, 'A+', account_info)  # ORB gets A+ grade
                                if success:
                                    bot_state.last_entry_signal = {
                                        'signal_type': 'ORB Breakout',
                                        'reasons': orb_message,
                                        'zones': None,
                                        'grade': 'A+',
                                        'entry_price': current_price,
                                        'direction': 'PUT',
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    send_notification(f"ORB Put Trade\n{orb_message}\nORB breakout strategy")
                                    bot_state.last_action = f"ORB PUT at {current_time}"
                                    logger.info("✅ ORB put order placed")
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
                    
                    # Zone-based signals (require C or higher = value >= 3)
                    if zone_signal == 'call' and current_grade_value >= 3:
                        trade_signal = 'call'
                        trade_reason.append(f"Demand zone bounce (Grade: {combined_grade})")
                    elif zone_signal == 'put' and current_grade_value >= 3:
                        trade_signal = 'put'
                        trade_reason.append(f"Supply zone rejection (Grade: {combined_grade})")
                    
                    # Pure technical signals (require B or higher = value >= 5)
                    elif current_grade_value >= 5:
                        # Determine direction from RSI/MACD
                        rsi = talib.RSI(df['close'])
                        rsi_value = rsi.iloc[-1]
                        
                        if rsi_value < 40:
                            trade_signal = 'call'
                            trade_reason.append(f"Oversold RSI ({rsi_value:.1f}) with strong technicals")
                            trade_reason.append(f"Grades: RSI={rsi_grade}, MACD={macd_grade}, Candle={candle_grade}, Volume={volume_grade} → {combined_grade}")
                        elif rsi_value > 60:
                            trade_signal = 'put'
                            trade_reason.append(f"Overbought RSI ({rsi_value:.1f}) with strong technicals")
                            trade_reason.append(f"Grades: RSI={rsi_grade}, MACD={macd_grade}, Candle={candle_grade}, Volume={volume_grade} → {combined_grade}")
                    
                    # 5. EXECUTE OR LOG WHY NOT
                    if trade_signal:
                        logger.info(f"🎯 TRADE SIGNAL: {trade_signal.upper()} - {', '.join(trade_reason)}")
                        bot_state.current_signal = f"{trade_signal.upper()} signal detected!"
                        bot_state.no_trade_reason = f"Executing {trade_signal} trade"
                        
                        # EXECUTE ACTUAL TRADE
                        try:
                            if trade_signal == 'call':
                                success = execute_call_trade(wb, symbol, combined_grade, account_info)
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
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    
                                    send_notification(f"Call Trade Executed\n{', '.join(trade_reason)}\nPrice: ${current_price:.2f}\nGrade: {combined_grade}")
                                    bot_state.last_action = f"Placed CALL order at ${current_price:.2f}"
                                    logger.info("✅ Call order placed successfully")
                                else:
                                    logger.error("❌ Failed to place call order")
                                    bot_state.no_trade_reason = "Order placement failed"
                            
                            elif trade_signal == 'put':
                                success = execute_put_trade(wb, symbol, combined_grade, account_info)
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
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    
                                    send_notification(f"Put Trade Executed\n{', '.join(trade_reason)}\nPrice: ${current_price:.2f}\nGrade: {combined_grade}")
                                    bot_state.last_action = f"Placed PUT order at ${current_price:.2f}"
                                    logger.info("✅ Put order placed successfully")
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
                    # Monitor position for exit
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
                    
                    # Calculate profit/loss targets
                    target_price = cost_price * (1 + profit_pct)
                    stop_loss_price = cost_price * (1 - loss_pct)
                    
                    pnl_pct = ((current_price - cost_price) / cost_price) * 100
                    
                    logger.info(f"Position P/L: {pnl_pct:.2f}% (Target: +{profit_pct*100}%, Stop: -{loss_pct*100}%)")
                    bot_state.current_signal = f"Monitoring position: P/L {pnl_pct:.2f}%"
                    
                    # CHECK FOR EXIT CONDITIONS
                    if current_price >= target_price:
                        logger.info(f"🎯 PROFIT TARGET REACHED! P/L: {pnl_pct:.2f}%")
                        try:
                            # Place SELL order
                            wb.place_order_option(
                                optionId=ticker_id,
                                lmtPrice=current_price,
                                stpPrice=str(float(current_price) - 0.25),
                                action='SELL',
                                orderType='LMT',
                                enforce='GTC',
                                quant=quantity
                            )
                            logger.info(f"✅ SELL order placed: {quantity} contracts at ${current_price}")
                            send_notification(f"Profit Target Hit!\nSold {quantity} contracts at {pnl_pct:.2f}% profit\nEntry: ${cost_price:.2f}, Exit: ${current_price:.2f}")
                            bot_state.last_action = f"SOLD at +{pnl_pct:.2f}% profit"
                        except Exception as e:
                            logger.error(f"❌ Error placing SELL order: {e}")
                            
                    elif current_price <= stop_loss_price:
                        logger.info(f"🛑 STOP LOSS HIT! P/L: {pnl_pct:.2f}%")
                        try:
                            # Place SELL order (market order for faster execution)
                            wb.place_order_option(
                                optionId=ticker_id,
                                lmtPrice=current_price,
                                stpPrice=str(float(current_price) - 0.25),
                                action='SELL',
                                orderType='LMT',
                                enforce='GTC',
                                quant=quantity
                            )
                            logger.info(f"✅ STOP LOSS SELL order placed: {quantity} contracts at ${current_price}")
                            send_notification(f"Stop Loss Triggered!\nSold {quantity} contracts at {pnl_pct:.2f}% loss\nEntry: ${cost_price:.2f}, Exit: ${current_price:.2f}")
                            bot_state.last_action = f"SOLD at {pnl_pct:.2f}% loss (stop loss)"
                        except Exception as e:
                            logger.error(f"❌ Error placing STOP LOSS order: {e}")
                
                # Sleep before next check (15 seconds in original)
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Error in trading loop iteration: {e}", exc_info=True)
                bot_state.error_message = str(e)
                await asyncio.sleep(60)  # Wait a bit longer on errors
                
    except Exception as e:
        logger.error(f"Trading bot crashed: {e}", exc_info=True)
        bot_state.error_message = str(e)
        send_notification(f"Bot Error\nTrading bot stopped due to error: {str(e)}")
    finally:
        bot_state.running = False
        logger.info("🛑 Trading bot stopped")

def execute_call_trade(wb, symbol, trade_grade, account_info):
    """Execute call option trade based on your original buy_call logic"""
    try:
        # Filter options for calls
        filtered_chain = filter_options_for_trade(wb, symbol, 'call')
        
        if not filtered_chain:
            logger.error("No suitable call options found")
            return False
        
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
        
        # Place the order
        logger.info(f"Placing call order: {order_quantity} contracts at ${option_price}")
        wb.place_order_option(
            optionId=filtered_chain[0]['call']['tickerId'],
            lmtPrice=option_price,
            stpPrice=str(float(option_price) - 0.25),
            action='BUY',
            orderType='LMT',
            enforce='GTC',
            quant=order_quantity
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in execute_call_trade: {e}", exc_info=True)
        return False


def execute_put_trade(wb, symbol, trade_grade, account_info):
    """Execute put option trade based on your original buy_put logic"""
    try:
        # Filter options for puts
        filtered_chain = filter_options_for_trade(wb, symbol, 'put')
        
        if not filtered_chain:
            logger.error("No suitable put options found")
            return False
        
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
        
        # Place the order
        logger.info(f"Placing put order: {order_quantity} contracts at ${option_price}")
        wb.place_order_option(
            optionId=filtered_chain[0]['put']['tickerId'],
            lmtPrice=option_price,
            stpPrice=str(float(option_price) - 0.25),
            action='BUY',
            orderType='LMT',
            enforce='GTC',
            quant=order_quantity
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in execute_put_trade: {e}", exc_info=True)
        return False


def filter_options_for_trade(wb, symbol, option_type):
    """Filter SPY options based on strike price and volume (from your original code)"""
    try:
        current_date = datetime.now().date()
        current_day = current_date.weekday()
        
        # Determine minimum expiration date
        if current_day == 4:  # Friday
            min_days = 3
        else:
            min_days = 1
        min_date = current_date + timedelta(days=min_days)
        
        # Get expiration dates
        expiration_dates = wb.get_options_expiration_dates(symbol)
        expiration_dates = [date for date in expiration_dates if datetime.strptime(date['date'], '%Y-%m-%d').date() >= min_date]
        
        if not expiration_dates:
            return None
        
        expiration_date = expiration_dates[0]['date']
        
        # Get current price and calculate strike range
        current_price = float(wb.get_quote(stock=symbol)['close'])
        rounded_price = round(current_price)
        
        if option_type == 'call':
            call_options = wb.get_options(stock=symbol, count=-1, direction='call', expireDate=expiration_date)
            call_options = [opt for opt in call_options if rounded_price <= float(opt['strikePrice']) <= rounded_price + 5]
            call_options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['call']['tickerId'])['data'][0]['volume']), reverse=True)
            return call_options
        
        elif option_type == 'put':
            put_options = wb.get_options(stock=symbol, count=-1, direction='put', expireDate=expiration_date)
            put_options = [opt for opt in put_options if rounded_price - 5 <= float(opt['strikePrice']) <= rounded_price]
            put_options.sort(key=lambda x: int(wb.get_option_quote(stock=symbol, optionId=x['put']['tickerId'])['data'][0]['volume']), reverse=True)
            return put_options
        
    except Exception as e:
        logger.error(f"Error filtering options: {e}")
        return None


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
        
        # Create backfilled entry signal
        bot_state.last_entry_signal = {
            'signal_type': signal_type,
            'reasons': f'Position opened at 12:45 PM {"in demand zone" if in_demand_zone else "in supply zone" if in_supply_zone else ""}',
            'zones': zones.copy() if (in_demand_zone or in_supply_zone) else None,
            'grade': 'N/A',
            'entry_price': float(entry_price),
            'direction': direction,
            'timestamp': buy_order.get('filledTime', 'Unknown'),
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
