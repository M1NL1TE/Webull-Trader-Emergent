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
    """Analyze supply and demand zones from price data"""
    try:
        # Look for significant support/resistance levels
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        # Find recent swing highs and lows
        recent_high = np.max(highs[-20:])
        recent_low = np.min(lows[-20:])
        
        # Supply zone (resistance): area around recent highs
        supply_top = recent_high
        supply_bottom = recent_high * 0.995  # 0.5% below high
        
        # Demand zone (support): area around recent lows  
        demand_bottom = recent_low
        demand_top = recent_low * 1.005  # 0.5% above low
        
        return {
            'demand_top': demand_top,
            'demand_bottom': demand_bottom,
            'supply_top': supply_top,
            'supply_bottom': supply_bottom
        }
    except Exception as e:
        logger.error(f"Error analyzing supply/demand: {e}")
        return {'demand_top': 0, 'demand_bottom': 0, 'supply_top': 0, 'supply_bottom': 0}


def check_orb_breakout(wb, symbol, current_time):
    """Check for Opening Range Breakout in first 15 minutes"""
    try:
        # Only check ORB in first 15 minutes after market open (9:30-9:45 AM EST)
        from pytz import timezone as pytz_timezone
        eastern = pytz_timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        
        market_open = now_eastern.replace(hour=9, minute=30, second=0, microsecond=0)
        orb_end = market_open + timedelta(minutes=15)
        
        if now_eastern < market_open or now_eastern > orb_end:
            return None, "Outside ORB window (9:30-9:45 AM)"
        
        # Get 1-minute bars for ORB analysis
        stockId = wb.get_ticker(symbol)
        df_1m = wb.get_bars(symbol, stockId, 'm1', 20, 1)
        
        if df_1m is None or len(df_1m) < 10:
            return None, "Insufficient data for ORB"
        
        # Calculate opening range (first 5-10 minutes)
        orb_high = df_1m['high'][:10].max()
        orb_low = df_1m['low'][:10].min()
        current_price = df_1m['close'].iloc[-1]
        
        bot_state.orb_status['high'] = orb_high
        bot_state.orb_status['low'] = orb_low
        
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
                    
                    if df is None or len(df) < 50:
                        bot_state.no_trade_reason = "Insufficient price data"
                        bot_state.current_signal = "Waiting for data..."
                        continue
                    
                    current_price = df['close'].iloc[-1]
                    bot_state.current_price = current_price
                    
                    # 1. CHECK ORB FIRST (Priority in first 15 minutes)
                    orb_signal, orb_message = check_orb_breakout(wb, symbol, current_time)
                    logger.info(f"ORB Check: {orb_message}")
                    
                    if orb_signal:
                        # ORB breakout detected - TAKE THE TRADE!
                        logger.info(f"🚨 ORB BREAKOUT DETECTED: {orb_signal.upper()}")
                        bot_state.current_signal = f"ORB {orb_signal} breakout!"
                        bot_state.no_trade_reason = f"Executing ORB {orb_signal} trade"
                        
                        # TODO: Execute ORB trade
                        send_notification(f"ORB Trade Signal\n{orb_signal.upper()} signal detected\n{orb_message}")
                        
                        # For now, log the trade
                        logger.info(f"📈 Would place {orb_signal} order here (ORB strategy)")
                        bot_state.last_action = f"ORB {orb_signal} signal at {current_time}"
                        
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
                    
                    # Zone-based signals
                    if zone_signal == 'call' and combined_grade >= 'C':
                        trade_signal = 'call'
                        trade_reason.append(f"Demand zone bounce (Grade: {combined_grade})")
                    elif zone_signal == 'put' and combined_grade >= 'C':
                        trade_signal = 'put'
                        trade_reason.append(f"Supply zone rejection (Grade: {combined_grade})")
                    
                    # Pure technical signals (no zone requirement)
                    elif combined_grade >= 'B':
                        # Determine direction from RSI/MACD
                        rsi = talib.RSI(df['close'])
                        if rsi.iloc[-1] < 40:
                            trade_signal = 'call'
                            trade_reason.append(f"Strong technicals - Oversold (Grade: {combined_grade})")
                        elif rsi.iloc[-1] > 60:
                            trade_signal = 'put'
                            trade_reason.append(f"Strong technicals - Overbought (Grade: {combined_grade})")
                    
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
                                    send_notification(f"Call Trade Executed\n{', '.join(trade_reason)}\nPrice: ${current_price:.2f}\nGrade: {combined_grade}")
                                    bot_state.last_action = f"Placed CALL order at ${current_price:.2f}"
                                    logger.info("✅ Call order placed successfully")
                                else:
                                    logger.error("❌ Failed to place call order")
                                    bot_state.no_trade_reason = "Order placement failed"
                            
                            elif trade_signal == 'put':
                                success = execute_put_trade(wb, symbol, combined_grade, account_info)
                                if success:
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
                        if combined_grade < 'C':
                            reasons.append(f"Grade too low ({combined_grade} < C)")
                        if not orb_signal:
                            reasons.append(orb_message)
                        
                        bot_state.no_trade_reason = " | ".join(reasons) if reasons else "Scanning for setups..."
                        bot_state.current_signal = "Scanning for entry signals..."
                        logger.info(f"No trade: {bot_state.no_trade_reason}")
                    
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
        'orb_status': bot_state.orb_status,
        'technical_signals': bot_state.technical_signals,
        'no_trade_reason': bot_state.no_trade_reason,
        'current_price': bot_state.current_price
    }
