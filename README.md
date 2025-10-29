# Webull Trader - Automated SPY Options Trading Bot

A full-stack web application for automated SPY options trading using the Webull API with technical analysis indicators.

## Features

### 🎯 Trading Capabilities
- **Automated Options Trading**: Execute CALL/PUT trades on SPY options
- **Paper & Real Trading**: Toggle between paper trading (test mode) and real trading
- **Smart Option Selection**: Automatically filters options by volume and strike price
- **Position Sizing**: Grades-based capital allocation (A+ = 20%, D = 5%)
- **Risk Management**: Automatic stop-loss orders and profit-taking

### 📊 Technical Analysis
- **RSI Indicator**: Identifies overbought/oversold conditions
- **MACD Indicator**: Detects trend changes and momentum
- **Candlestick Patterns**: Recognizes bullish/bearish patterns
- **Supply/Demand Zones**: Key support and resistance levels
- **Trade Grades**: A+ to D grading system for signal confidence

### 📈 Dashboard
- **Account Overview**: Real-time account balance, P/L, buying power
- **Position Monitoring**: Track open positions with live P/L
- **Order Management**: View and cancel pending orders
- **Trading Signals**: Real-time technical indicators and signals
- **Manual Trading**: Execute trades manually with grade selection

## Usage

### 1. Login
- Enter your Webull username (email or phone)
- Enter your Webull password
- Enter your 6-digit trade PIN
- Toggle Paper Trading (recommended for testing)
- Optional: Enter Device ID if you have one

### 2. View Dashboard
- **Overview Tab**: Account balance, positions, orders
- **Trade Tab**: Manual trade execution
- **Signals Tab**: Real-time technical analysis
- **Settings Tab**: Configure automation and risk parameters

### 3. Execute Trades
- Select CALL (bullish) or PUT (bearish)
- Choose trade grade (A+ to D) based on confidence
- System automatically finds best options and executes

## ⚠️ Disclaimer
**This is for educational purposes only. Trading options involves significant risk. Only trade with capital you can afford to lose. Always test in paper trading mode first!**
