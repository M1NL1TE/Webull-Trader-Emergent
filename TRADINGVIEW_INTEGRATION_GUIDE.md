# TradingView Charting Library Integration Guide

## Overview
This guide shows how to embed TradingView charts in your React dashboard and programmatically draw supply/demand zone rectangles.

**IMPORTANT:** This requires TradingView Charting Library license ($399/month).
You cannot modify charts on TradingView.com remotely.

---

## Step 1: Purchase TradingView Charting Library License

### 1.1 Request Access
- Go to: https://www.tradingview.com/HTML5-stock-forex-bitcoin-charting-library/
- Click "Request a demo"
- Fill out form with your details
- Use case: "Automated trading bot with supply/demand zone visualization"

### 1.2 Sales Process
- TradingView sales team will contact you (1-3 days)
- They'll provide:
  - Demo access (14-30 days free trial)
  - Pricing details ($399/month standard)
  - Contract terms
  - Private npm registry credentials

### 1.3 Sign Contract
- Review terms
- Sign agreement
- Provide payment info
- Receive library access credentials

**Cost Breakdown:**
- Setup fee: Usually $0 (waived)
- Monthly fee: $399
- Annual option: ~$3,990 (save ~$800)

---

## Step 2: Install Charting Library

### 2.1 Add Private Registry
```bash
# Add TradingView's private npm registry
npm config set @tradingview:registry https://npm.tradingview.com
npm config set //npm.tradingview.com/:_authToken YOUR_TOKEN_HERE
```

### 2.2 Install Package
```bash
cd /app/frontend
npm install @tradingview/charting_library
```

### 2.3 Copy Static Files
```bash
# Copy charting library static files to public folder
cp -r node_modules/@tradingview/charting_library/charting_library/ public/charting_library/
cp -r node_modules/@tradingview/charting_library/datafeeds/ public/datafeeds/
```

---

## Step 3: Create React Component

### 3.1 Create TradingViewChart Component

**File:** `/app/frontend/src/components/TradingViewChart.js`

```javascript
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function TradingViewChart() {
  const chartContainerRef = useRef(null);
  const widgetRef = useRef(null);
  const supplyBoxRef = useRef(null);
  const demandBoxRef = useRef(null);

  useEffect(() => {
    // Initialize TradingView widget
    const script = document.createElement('script');
    script.src = '/charting_library/charting_library.js';
    script.async = true;
    script.onload = initializeWidget;
    document.body.appendChild(script);

    return () => {
      if (widgetRef.current) {
        widgetRef.current.remove();
      }
    };
  }, []);

  const initializeWidget = () => {
    const widget = new window.TradingView.widget({
      container: chartContainerRef.current,
      library_path: '/charting_library/',
      locale: 'en',
      symbol: 'SPY',
      interval: '5', // 5-minute candles
      fullscreen: false,
      autosize: true,
      theme: 'dark',
      timezone: 'America/New_York',
      toolbar_bg: '#1e293b',
      enable_publishing: false,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      studies_overrides: {},
      overrides: {
        'mainSeriesProperties.candleStyle.upColor': '#10b981',
        'mainSeriesProperties.candleStyle.downColor': '#ef4444',
      },
      disabled_features: [
        'use_localstorage_for_settings',
        'volume_force_overlay'
      ],
      enabled_features: [
        'study_templates',
        'create_volume_indicator_by_default'
      ],
      datafeed: new window.Datafeeds.UDFCompatibleDatafeed('/api/tradingview/datafeed'),
    });

    widget.onChartReady(() => {
      console.log('TradingView chart ready');
      widgetRef.current = widget;
      
      // Start fetching and drawing zones
      fetchAndDrawZones();
      setInterval(fetchAndDrawZones, 60000); // Update every minute
    });
  };

  const fetchAndDrawZones = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      const zones = response.data.zones;

      if (!zones || !widgetRef.current) return;

      const chart = widgetRef.current.activeChart();

      // Remove old rectangles
      if (supplyBoxRef.current) {
        chart.removeEntity(supplyBoxRef.current);
      }
      if (demandBoxRef.current) {
        chart.removeEntity(demandBoxRef.current);
      }

      // Calculate time coordinates (show last 50 bars and extend 10 bars forward)
      const currentTime = Math.floor(Date.now() / 1000);
      const startTime = currentTime - (50 * 5 * 60); // 50 bars of 5-min candles
      const endTime = currentTime + (10 * 5 * 60); // Extend 10 bars forward

      // Draw Supply Zone (RED)
      supplyBoxRef.current = chart.createMultipointShape(
        [
          { time: startTime, price: zones.supply_bottom },
          { time: endTime, price: zones.supply_top }
        ],
        {
          shape: 'rectangle',
          overrides: {
            backgroundColor: 'rgba(239, 68, 68, 0.1)', // Red transparent
            borderColor: '#ef4444',
            borderWidth: 2,
            extendLeft: false,
            extendRight: true,
            showLabel: true,
            text: `Supply Zone: $${zones.supply_bottom.toFixed(2)} - $${zones.supply_top.toFixed(2)}`,
            textColor: '#ef4444',
            fontSize: 12
          }
        }
      );

      // Draw Demand Zone (GREEN)
      demandBoxRef.current = chart.createMultipointShape(
        [
          { time: startTime, price: zones.demand_bottom },
          { time: endTime, price: zones.demand_top }
        ],
        {
          shape: 'rectangle',
          overrides: {
            backgroundColor: 'rgba(16, 185, 129, 0.1)', // Green transparent
            borderColor: '#10b981',
            borderWidth: 2,
            extendLeft: false,
            extendRight: true,
            showLabel: true,
            text: `Demand Zone: $${zones.demand_bottom.toFixed(2)} - $${zones.demand_top.toFixed(2)}`,
            textColor: '#10b981',
            fontSize: 12
          }
        }
      );

      console.log('Zones updated:', zones);
    } catch (error) {
      console.error('Error fetching zones:', error);
    }
  };

  return (
    <div 
      ref={chartContainerRef} 
      style={{ 
        width: '100%', 
        height: '600px',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
    />
  );
}

export default TradingViewChart;
```

### 3.2 Add to Dashboard

**File:** `/app/frontend/src/pages/Dashboard.js`

```javascript
import TradingViewChart from '@/components/TradingViewChart';

// Add to your dashboard layout
<TabsContent value="chart" className="space-y-6">
  <TradingViewChart />
</TabsContent>
```

---

## Step 4: Create Datafeed (Optional but Recommended)

TradingView needs a datafeed to fetch price data. You can use Webull data.

**File:** `/app/backend/server.py`

```python
@api_router.get("/tradingview/datafeed/config")
async def tradingview_config():
    """TradingView UDF config"""
    return {
        "supported_resolutions": ["1", "5", "15", "30", "60", "D", "W"],
        "supports_group_request": False,
        "supports_marks": False,
        "supports_search": True,
        "supports_timescale_marks": False
    }

@api_router.get("/tradingview/datafeed/symbols")
async def tradingview_symbol_info(symbol: str):
    """Get symbol info"""
    if symbol != "SPY":
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    return {
        "name": "SPY",
        "ticker": "SPY",
        "description": "SPDR S&P 500 ETF",
        "type": "stock",
        "session": "0930-1600",
        "timezone": "America/New_York",
        "minmov": 1,
        "pricescale": 100,
        "has_intraday": True,
        "supported_resolutions": ["1", "5", "15", "30", "60", "D"],
        "data_status": "streaming"
    }

@api_router.get("/tradingview/datafeed/history")
async def tradingview_history(
    symbol: str,
    resolution: str,
    from_: int = Query(..., alias="from"),
    to: int = Query(..., alias="to")
):
    """Get historical bars"""
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
    
    # Convert TradingView resolution to Webull interval
    interval_map = {
        "1": "m1",
        "5": "m5",
        "15": "m15",
        "30": "m30",
        "60": "m60",
        "D": "d1"
    }
    interval = interval_map.get(resolution, "m5")
    
    stockId = wb.get_ticker(symbol)
    df = wb.get_bars(symbol, stockId, interval, 1000, 1)
    
    if df is None or len(df) == 0:
        return {"s": "no_data"}
    
    # Convert to TradingView format
    bars = {
        "s": "ok",
        "t": [int(row['timestamp'].timestamp()) for _, row in df.iterrows()],
        "o": df['open'].tolist(),
        "h": df['high'].tolist(),
        "l": df['low'].tolist(),
        "c": df['close'].tolist(),
        "v": df['volume'].tolist()
    }
    
    return bars
```

---

## Step 5: Test and Deploy

### 5.1 Test Locally
```bash
# Start backend and frontend
sudo supervisorctl restart backend frontend

# Open browser to your dashboard
# Navigate to "Chart" tab
# You should see TradingView chart with auto-updating zones
```

### 5.2 Verify Zone Updates
1. Watch bot calculate new zones
2. Chart should update rectangles within 60 seconds
3. Zones should extend forward on chart
4. Colors: Red (supply), Green (demand)

---

## Cost Summary

**Monthly Costs:**
- TradingView Charting Library: $399/month
- Your current hosting: $X (existing)
- **Total new cost:** $399/month

**Annual Option:**
- TradingView annual: ~$3,990/year (save ~$800)

---

## Alternative: Free Pine Script Approach

If $399/month is too expensive, use Pine Script with manual updates:

**Step 1:** Copy this Pine Script code
**Step 2:** Go to TradingView.com → Chart → Pine Editor
**Step 3:** Paste code, save as "Bot Zones"
**Step 4:** Add to SPY chart
**Step 5:** Update input values when bot recalculates zones (once/day)

**Pine Script Template:**
```pinescript
//@version=5
indicator("Bot Supply/Demand Zones", overlay=true)

// Manual inputs - update these from bot dashboard
supply_top = input.float(686.50, "Supply Top")
supply_bottom = input.float(685.80, "Supply Bottom")
demand_top = input.float(683.20, "Demand Top")
demand_bottom = input.float(682.50, "Demand Bottom")

// Draw zones
var box supplyBox = na
var box demandBox = na

if barstate.islast
    box.delete(supplyBox)
    box.delete(demandBox)
    
    supplyBox := box.new(
        bar_index - 50, supply_bottom,
        bar_index + 10, supply_top,
        border_color=color.red,
        bgcolor=color.new(color.red, 90),
        text="Supply",
        text_color=color.red
    )
    
    demandBox := box.new(
        bar_index - 50, demand_bottom,
        bar_index + 10, demand_top,
        border_color=color.green,
        bgcolor=color.new(color.green, 90),
        text="Demand",
        text_color=color.green
    )
```

**Cost:** FREE
**Effort:** 30 seconds per day to update

---

## My Recommendation

**Unless you're managing $50k+ in capital:**
- Use FREE Pine Script approach
- Update zones manually once per day
- Saves $399/month = $4,788/year

**If you have the budget:**
- Charting Library gives professional edge
- Fully automated
- Better UX for monitoring
