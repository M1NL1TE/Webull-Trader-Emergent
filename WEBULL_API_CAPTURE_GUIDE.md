# How to Capture Webull API Calls for Closing Positions

## Method 1: Chrome DevTools (Easiest)

### Step 1: Open Webull Web Platform
1. Go to: https://app.webull.com/
2. Log into your account
3. Navigate to your positions

### Step 2: Open Developer Tools
- **Windows/Linux:** Press `F12` or `Ctrl+Shift+I`
- **Mac:** Press `Cmd+Option+I`

### Step 3: Prepare Network Tab
1. Click on the **"Network"** tab in DevTools
2. Click the **filter icon** (looks like a funnel)
3. Check **"Fetch/XHR"** to show only API calls
4. Optional: Click the **clear** button (🚫) to remove old requests

### Step 4: Close a Position
1. Find a position you want to close (preferably a small one for testing)
2. Click "Sell" or "Close Position"
3. Confirm the sell order
4. **DO NOT close DevTools yet!**

### Step 5: Find the API Call
1. In the Network tab, look for requests that appeared when you clicked sell
2. Look for URLs containing:
   - `placeOrder`
   - `option`
   - `sell`
   - `close`
3. Click on the suspicious request

### Step 6: Extract the Details
Once you click on the request, you'll see tabs: Headers, Payload, Response

**A. Headers Tab:**
```
Request URL: https://trade.webull.com/api/trade/v2/option/placeOrder/[YOUR_ACCOUNT_ID]
Request Method: POST
```

**B. Payload Tab (Request Payload):**
This is the MOST IMPORTANT part. Copy the entire JSON payload.
Example of what to look for:
```json
{
  "orderType": "MKT" or "LMT",
  "timeInForce": "DAY" or "GTC",
  "serialId": "some-uuid",
  "orders": [{
    "quantity": 1,
    "action": "SELL",
    "tickerId": 123456789,
    "tickerType": "OPTION"
  }],
  "lmtPrice": 0.50  // Only if orderType is LMT
}
```

**C. Response Tab:**
Check if the response shows success or error:
```json
{
  "success": true,
  "data": {...}
}
```

### Step 7: Take Screenshots
Take screenshots of:
1. The full Network tab showing all requests
2. The Headers tab showing Request URL
3. The Payload tab showing Request body
4. The Response tab showing the result

### Step 8: Share with Me
Send me:
- Screenshots (all 4)
- Copy the Request Payload JSON (from Payload tab)
- Copy the Request URL

---

## Method 2: Charles Proxy (Advanced)

### Setup Charles
1. Download Charles Proxy: https://www.charlesproxy.com/download/
2. Install and open Charles
3. Install SSL certificate for HTTPS capture:
   - Help → SSL Proxying → Install Charles Root Certificate
   - Trust the certificate

### Configure SSL Proxying
1. Proxy → SSL Proxying Settings
2. Add `*.webull.com` to the list

### Capture the Request
1. Start recording (Proxy → Start Recording)
2. Open Webull in browser
3. Close a position
4. Stop recording
5. Find the `placeOrder` request
6. Right-click → Copy → Copy as cURL
7. Send me the cURL command

---

## Method 3: Browser HAR Export (Comprehensive)

### Chrome/Edge:
1. Open DevTools (F12)
2. Go to Network tab
3. Click **Export HAR** button (download icon)
4. Perform the sell action
5. Stop recording
6. Export the HAR file
7. Send me the HAR file (I can analyze all requests)

**Note:** HAR files contain sensitive data (cookies, tokens). Remove or redact:
- Authorization headers
- Session tokens
- Personal account IDs

---

## What I'm Looking For

### Key Differences to Identify:
1. **Different orderType?** (MKT vs LMT)
2. **Different endpoint URL?** (maybe `/closePosition` instead of `/placeOrder`)
3. **Additional parameters?** (fields we're not sending)
4. **Different headers?** (maybe special headers for closing)
5. **Different account ID format?**

### Common Issues to Check:
- Is `tickerId` formatted differently?
- Is there a `comboId` or `orderId` field?
- Is there a `positionId` field?
- Is `timeInForce` different (IOC, FOK)?
- Are there additional fields like `outsideRegularTradingHour`?

---

## Quick Test Checklist

Before capturing, test these scenarios:
1. ✅ Close a profitable position (small)
2. ✅ Close a losing position (small)
3. ✅ Close a 1DTE position
4. ✅ Close a 0DTE position (if you have one)

Each scenario might use different parameters!

---

## Safety Notes

⚠️ **IMPORTANT:**
- Use a small position for testing (1 contract)
- Never share your full cookies/tokens
- Redact `access_token`, `refresh_token`, `trade_token` if visible
- Account IDs can stay (already logged in our system)

Once I have the working API call format, I can:
1. Update the `place_order_option` function
2. Add a new `close_position` function if needed
3. Modify headers/payload to match the working format
