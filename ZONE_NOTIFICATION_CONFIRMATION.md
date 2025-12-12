# Zone Notification Email Confirmation

## ✅ EMAIL NOTIFICATIONS ARE CONFIGURED FOR ALL ZONES

### What Triggers Zone Notification Emails:

The bot sends **ONE notification** when price enters **ANY** of these zones:

---

## 1. 15-Minute Zones (1 Supply + 1 Demand)

### 15-Min Supply Zone:
- **When:** Price >= supply_bottom AND price <= supply_top
- **Email includes:** "15-Min Supply Zone: $[bottom] - $[top]"
- **Lookback:** 195 candles (3 trading days)
- **Example:** If SPY = $689.75 and supply zone is $689.51 - $691.24
  → Email sent: "🎯 Price in Zone! SPY: $689.75 • 15-Min Supply Zone: $689.51 - $691.24"

### 15-Min Demand Zone:
- **When:** Price >= demand_bottom AND price <= demand_top
- **Email includes:** "15-Min Demand Zone: $[bottom] - $[top]"
- **Lookback:** 195 candles (3 trading days)
- **Example:** If SPY = $682.50 and demand zone is $681.31 - $683.01
  → Email sent: "🎯 Price in Zone! SPY: $682.50 • 15-Min Demand Zone: $681.31 - $683.01"

---

## 2. 1-Hour Zones (2 Supply + 2 Demand)

### 1-Hour Supply Zone #1 (Highest):
- **When:** Price is within top supply zone from 60-day lookback
- **Email includes:** "1-Hour Supply Zone #1: $[bottom] - $[top]"
- **Lookback:** 400 candles (60 calendar days)
- **Example:** If SPY = $688.50 and zone #1 is $687.25 - $688.97
  → Email sent: "🎯 Price in Zone! SPY: $688.50 • 1-Hour Supply Zone #1: $687.25 - $688.97"

### 1-Hour Supply Zone #2 (Second Highest):
- **When:** Price is within second-highest supply zone
- **Email includes:** "1-Hour Supply Zone #2: $[bottom] - $[top]"
- **Lookback:** 400 candles (60 calendar days)

### 1-Hour Demand Zone #1 (Lowest):
- **When:** Price is within lowest demand zone from 60-day lookback
- **Email includes:** "1-Hour Demand Zone #1: $[bottom] - $[top]"
- **Lookback:** 400 candles (60 calendar days)
- **Example:** If SPY = $651.00 and zone #1 is $649.45 - $651.07
  → Email sent: "🎯 Price in Zone! SPY: $651.00 • 1-Hour Demand Zone #1: $649.45 - $651.07"

### 1-Hour Demand Zone #2 (Second Lowest):
- **When:** Price is within second-lowest demand zone
- **Email includes:** "1-Hour Demand Zone #2: $[bottom] - $[top]"
- **Lookback:** 400 candles (60 calendar days)

---

## Combined Zone Notification

If price is in **MULTIPLE zones simultaneously**, the email includes ALL of them:

### Example 1: In both 15-min and 1-hour supply:
```
📄 PAPER | 🎯 Price in Zone!

SPY: $688.75

Active Zones:
• 15-Min Supply Zone: $687.25 - $688.97
• 1-Hour Supply Zone #1: $687.25 - $688.97

Time: 10:45 AM EST
```

### Example 2: In multiple 1-hour zones:
```
💰 LIVE | 🎯 Price in Zone!

SPY: $650.50

Active Zones:
• 1-Hour Demand Zone #1: $649.45 - $651.07
• 1-Hour Demand Zone #2: $648.00 - $649.80

Time: 2:30 PM EST
```

---

## Code Location (Lines 1122-1166)

```python
# Check 15-min zones
if zones['demand_bottom'] <= current_price <= zones['demand_top']:
    in_any_zone = True
    zone_details.append(f"15-Min Demand Zone: ${zones['demand_bottom']:.2f} - ${zones['demand_top']:.2f}")

if zones['supply_bottom'] <= current_price <= zones['supply_top']:
    in_any_zone = True
    zone_details.append(f"15-Min Supply Zone: ${zones['supply_bottom']:.2f} - ${zones['supply_top']:.2f}")

# Check 1-hour zones
if bot_state.zones_1hr and bot_state.zones_1hr.get('supply_zones'):
    for idx, zone in enumerate(bot_state.zones_1hr['supply_zones']):
        if zone['bottom'] <= current_price <= zone['top']:
            in_any_zone = True
            zone_details.append(f"1-Hour Supply Zone #{idx+1}: ${zone['bottom']:.2f} - ${zone['top']:.2f}")

if bot_state.zones_1hr and bot_state.zones_1hr.get('demand_zones'):
    for idx, zone in enumerate(bot_state.zones_1hr['demand_zones']):
        if zone['bottom'] <= current_price <= zone['top']:
            in_any_zone = True
            zone_details.append(f"1-Hour Demand Zone #{idx+1}: ${zone['bottom']:.2f} - ${zone['top']:.2f}")

# Send notification if in zone and haven't notified recently
if in_any_zone and (not bot_state.last_zone_notification or 
    (datetime.now(timezone.utc) - bot_state.last_zone_notification).total_seconds() > 300):
    send_notification(...)
```

---

## Notification Rules

### When Emails ARE Sent:
✅ Price enters 15-min supply zone
✅ Price enters 15-min demand zone
✅ Price enters 1-hour supply zone #1
✅ Price enters 1-hour supply zone #2
✅ Price enters 1-hour demand zone #1
✅ Price enters 1-hour demand zone #2
✅ Price enters MULTIPLE zones simultaneously (one email lists all)

### When Emails Are NOT Sent:
❌ Price is between zones (not in any zone)
❌ Less than 5 minutes since last zone notification (throttled)
❌ Gmail daily limit reached (now has fallback to secondary account)

---

## Throttling (Spam Prevention)

- **Throttle Duration:** 5 minutes (300 seconds)
- **Purpose:** Prevent email spam when price hovers at zone boundaries
- **Example:** 
  - 10:00 AM: Price enters zone → Email sent
  - 10:02 AM: Price still in zone → No email (only 2 min passed)
  - 10:05 AM: Price still in zone → Email sent (5 min passed)

---

## Summary

**Total possible zone notifications:**
- 1x 15-min supply
- 1x 15-min demand
- 2x 1-hour supply (zone #1 and #2)
- 2x 1-hour demand (zone #1 and #2)

**= 6 possible zones that trigger notifications**

**Email frequency:**
- Max once per 5 minutes when in zones
- Can list multiple zones in single email

**Current status:**
- ✅ Code is active (fixed bug earlier today)
- ✅ Checks ALL zones on every bot loop
- ✅ Works with or without open positions
- ⚠️ Primary Gmail currently blocked (daily limit)
- ✅ Secondary Gmail fallback now configured

---

Last Updated: December 12, 2025
