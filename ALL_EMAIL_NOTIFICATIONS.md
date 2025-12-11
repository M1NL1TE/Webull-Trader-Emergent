# Complete List of Email Notifications

## Format
All notifications now include account type prefix:
- 💰 LIVE | [notification message]
- 📄 PAPER | [notification message]

---

## 1. BOT STATUS NOTIFICATIONS

### 🤖 Bot Online (Daily - Market Open)
**When:** First time market opens each day (9:30 AM EST)
**Example:**
```
📄 PAPER | 🤖 Trading Bot Online

Bot is now active and monitoring SPY for trading signals.

Market Hours: 9:30 AM - 4:00 PM EST
Started: 9:30 AM EST

You'll receive notifications for:
• Trade entries
• Trade exits
• Stop-loss/profit alerts
• Zone entry signals
```

### 🏁 Bot Finished (Daily - Market Close)
**When:** When market closes (4:00 PM EST)
**Example:**
```
💰 LIVE | 🏁 Trading Bot Finished for Today

Market closed at 4:00 PM EST

Status:
• Open Positions: 1
• Open Orders: 0
• Bot Status: Idle (waiting for tomorrow)

The bot will resume monitoring when market opens tomorrow at 9:30 AM EST.

Check your dashboard for detailed P/L and trade history.
```

### ❌ Bot Error
**When:** Bot encounters fatal error and stops
**Example:**
```
💰 LIVE | ❌ Bot Error

Trading bot stopped due to error: [error details]
```

---

## 2. TRADE ENTRY NOTIFICATIONS

### 🔄 Order Attempt - CALL (NEW)
**When:** BEFORE placing call order
**Example:**
```
💰 LIVE | 🔄 ATTEMPTING CALL Order

Symbol: SPY251210C00686000
Quantity: 1 contracts
Limit Price: $0.82
DTE: 1
Time: 10:45 AM EST

Waiting for Webull API response...
```

### 🔄 Order Attempt - PUT (NEW)
**When:** BEFORE placing put order
**Example:**
```
📄 PAPER | 🔄 ATTEMPTING PUT Order

Symbol: SPY251210P00683000
Quantity: 2 contracts
Limit Price: $1.15
DTE: 2
Time: 2:30 PM EST

Waiting for Webull API response...
```

### ✅ Call Trade Executed
**When:** Call order successfully placed
**Example:**
```
💰 LIVE | ✅ Call Trade Executed (1DTE)

Demand zone bounce, Technical Grade: B
Price: $682.50
Grade: B

Symbol: SPY251210C00686000
Quantity: 1 contracts
Entry Price: $0.81
Time: 10:45 AM EST
```

### ✅ Put Trade Executed
**When:** Put order successfully placed
**Example:**
```
📄 PAPER | ✅ Put Trade Executed (2DTE)

Supply zone rejection, Technical Grade: A
Price: $688.25
Grade: A

Symbol: SPY251212P00685000
Quantity: 2 contracts
Entry Price: $1.20
Time: 1:15 PM EST
```

### ✅ ORB Call Trade
**When:** ORB upside breakout trade (call)
**Example:**
```
💰 LIVE | ✅ ORB Call Trade (1DTE)

ORB upside breakout at 10:05 AM
ORB breakout strategy

Symbol: SPY251210C00686000
Quantity: 1 contracts
Entry Price: $0.75
```

### ✅ ORB Put Trade
**When:** ORB downside breakout trade (put)
**Example:**
```
📄 PAPER | ✅ ORB Put Trade (2DTE)

ORB downside breakout at 9:45 AM
ORB breakout strategy

Symbol: SPY251212P00683000
Quantity: 2 contracts
Entry Price: $1.10
```

---

## 3. TRADE EXIT NOTIFICATIONS

### 💰 Profit Target Hit (Initial Phase)
**When:** Position hits profit target, sells half
**Example:**
```
💰 LIVE | 💰 Profit Target Hit! (1DTE)

Sold 1/2 contracts at 50.00% profit
Keeping 1 for trailing stop
Entry: $0.81, Exit: $1.22

Position enters trailing stop phase.
```

### 💰 Profit Target Hit (Trailing Phase)
**When:** Position hits final profit target
**Example:**
```
📄 PAPER | 💰 Profit Target Hit (Trailing)! (1DTE)

Sold 1 contracts at 75.00% profit
Entry: $0.81, Exit: $1.42

Full position closed.
```

### 🛑 Stop Loss Triggered (Initial Phase)
**When:** Position hits stop-loss
**Example:**
```
💰 LIVE | 🛑 Stop Loss Triggered! (1DTE)

Sold 2 contracts at -25.00% loss
Entry: $1.20, Exit: $0.90

Position closed.
```

### 🛑 Stop Loss Triggered (Trailing Phase)
**When:** Trailing stop triggered
**Example:**
```
📄 PAPER | 🛑 Stop Loss Triggered (Trailing)! (1DTE)

Sold 1 contracts at 30.00% profit
Entry: $0.81, Exit: $1.05

Trailing stop hit, position closed.
```

### 🚪 Zone Exit Triggered
**When:** Price exits S/D zone (early exit strategy)
**Example:**
```
💰 LIVE | 🚪 Zone Exit Triggered! (1DTE)

Price exited supply zone
Sold 1 contracts at -15.50% loss
Entry: $0.81, Exit: $0.68

Exited due to zone break.
```

---

## 4. MARKET STRUCTURE NOTIFICATIONS

### 🎯 Price in Zone
**When:** Price enters any S/D zone (15-min or 1-hour)
**Frequency:** Max once every 5 minutes
**Example:**
```
💰 LIVE | 🎯 Price in Zone!

SPY: $683.50

Active Zones:
• 15-Min Demand Zone #1: $681.31 - $683.01
• 1-Hour Demand Zone #1: $681.57 - $683.27

Time: 11:30 AM EST
```

---

## 5. ORDER FAILURE NOTIFICATIONS (NEW)

### ❌ CALL Order Failed
**When:** Call order placement fails
**Example:**
```
💰 LIVE | ❌ CALL Order FAILED

Error: The system is busy
Symbol: SPY251210C00686000
Response: {"success": false, "msg": "The system is busy"}
Time: 2:45 PM EST
```

### ❌ PUT Order Failed
**When:** Put order placement fails
**Example:**
```
📄 PAPER | ❌ PUT Order FAILED

Error: Insufficient buying power
Symbol: SPY251212P00685000
Response: {"success": false, "msg": "Insufficient funds"}
Time: 10:15 AM EST
```

### ❌ Sell Order Failed
**When:** Stop-loss or profit-taking sell order fails
**Example:**
```
💰 LIVE | ❌ Sell Order Failed

Could not close position automatically.
Symbol: SPY251211P00683000
Quantity: 2 contracts
Reason: API error / 2FA required

Please close manually via Webull app.
```

---

## 6. POSITION MONITORING ALERTS

### ⚠️ Stop-Loss Alert (Without Sell)
**When:** Position should trigger stop-loss but sell fails
**Example:**
```
💰 LIVE | ⚠️ Stop-Loss Alert

Position hit stop-loss threshold but could not close automatically.

Symbol: SPY251211P00683000
Current P/L: -28.50%
Entry: $0.93, Current: $0.66

MANUAL ACTION REQUIRED:
Please close this position via Webull app.
```

### ⚠️ Profit Alert (Without Sell)
**When:** Position should take profit but sell fails
**Example:**
```
📄 PAPER | ⚠️ Profit Target Alert

Position hit profit target but could not close automatically.

Symbol: SPY251210C00686000
Current P/L: 52.00%
Entry: $0.81, Current: $1.23

MANUAL ACTION REQUIRED:
Consider closing via Webull app.
```

---

## SUMMARY BY CATEGORY

### Daily Status: 2 notifications
- Bot Online (once per day)
- Bot Finished (once per day)

### Order Attempts: 2 notifications (NEW)
- Call order attempt
- Put order attempt

### Trade Entries: 4 notifications
- Call executed
- Put executed
- ORB call executed
- ORB put executed

### Trade Exits: 5 notifications
- Profit target (initial)
- Profit target (trailing)
- Stop-loss (initial)
- Stop-loss (trailing)
- Zone exit

### Order Failures: 3 notifications (NEW)
- Call failed
- Put failed
- Sell failed

### Market Signals: 1 notification
- Price in zone (throttled to 5-min intervals)

### Alerts: 2 notifications
- Stop-loss alert (manual action needed)
- Profit alert (manual action needed)

### Errors: 1 notification
- Bot error/crash

---

## TOTAL: 20 NOTIFICATION TYPES

**All now include account type prefix (💰 LIVE or 📄 PAPER)**

---

## Email Settings

Email notifications are sent to: `[configured email from .env]`

To configure:
- Set `SMTP_EMAIL` in `/app/backend/.env`
- Set `SMTP_PASSWORD` for app-specific password
- Set `NOTIFICATION_EMAIL` for recipient

---

## Frequency Rules

**Once per day:**
- Bot Online (at market open)
- Bot Finished (at market close)

**Throttled (max once per 5 min):**
- Price in zone notifications

**Real-time (immediate):**
- All trade entries
- All trade exits
- All order failures
- All alerts

**On error:**
- Bot error notification

---

## Notification Priority

**🔴 CRITICAL (Immediate Action Required):**
- Sell order failed
- Stop-loss alert (manual close needed)
- Bot error

**🟡 IMPORTANT (Monitor):**
- Order attempt (before placement)
- Order failure (call/put)
- Profit alert (manual close suggested)

**🟢 INFORMATIONAL:**
- Trade executed successfully
- Zone entry
- Daily status updates
- Profit/stop-loss successful

---

Last Updated: December 11, 2025
