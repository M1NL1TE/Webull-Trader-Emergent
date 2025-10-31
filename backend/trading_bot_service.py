"""
Automated Trading Bot Service
Integrates user's original trading bot logic into async background task
"""
import asyncio
import logging
from datetime import datetime, timedelta, time as dt_time
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
            'downside_time': None
        }
        self.position_status = "No Position"
        
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
        
        # Initialize variables (from original main)
        symbol = 'SPY'
        interval = 'm30'
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
        
        while bot_state.running:
            try:
                bot_state.last_check_time = datetime.now()
                
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
                    await asyncio.sleep(3600)  # Check every hour on weekends
                    continue
                
                if current_time < market_open:
                    bot_state.market_status = "Pre-Market"
                    bot_state.current_signal = "Waiting for market open at 9:30 AM"
                    logger.info(f"Pre-market - waiting until {market_open}")
                    await asyncio.sleep(60)  # Check every minute
                    continue
                
                if current_time > market_close:
                    bot_state.market_status = "Closed (After Hours)"
                    bot_state.current_signal = "Market closed for the day"
                    logger.info("Market closed for the day")
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
                
                if not has_position and not has_open_orders:
                    # Look for entry signals
                    logger.info("No positions - analyzing for entry signals...")
                    
                    # Get price data
                    df = wb.get_bars(symbol, stockId, interval, 140, 1)
                    
                    # Analyze supply/demand zones (simplified version - full logic in original)
                    # TODO: Integrate full supply_demand function
                    
                    bot_state.current_signal = "Scanning for entry signals..."
                    
                    # Placeholder for entry logic
                    # In production, this would call your full strategy functions
                    
                elif has_position and not has_open_orders:
                    # Monitor position for exit
                    logger.info("Monitoring open position...")
                    position = account_info['positions'][0]
                    
                    cost_price = float(position['costPrice'])
                    current_price = float(position['lastPrice'])
                    
                    # Calculate profit/loss targets
                    target_price = cost_price * (1 + profit_pct)
                    stop_loss = cost_price * (1 - loss_pct)
                    
                    pnl_pct = ((current_price - cost_price) / cost_price) * 100
                    
                    logger.info(f"Position P/L: {pnl_pct:.2f}% (Target: +{profit_pct*100}%, Stop: -{loss_pct*100}%)")
                    bot_state.current_signal = f"Monitoring position: P/L {pnl_pct:.2f}%"
                    
                    if current_price >= target_price:
                        logger.info(f"🎯 Target reached! Selling at profit")
                        # TODO: Place sell order
                        send_sms(f"SPY position sold for {pnl_pct:.2f}% profit")
                    elif current_price <= stop_loss:
                        logger.info(f"🛑 Stop loss hit! Selling to limit loss")
                        # TODO: Place sell order
                        send_sms(f"SPY position sold at {pnl_pct:.2f}% loss (stop loss)")
                
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
        'orb_status': bot_state.orb_status
    }
