# CALL vs PUT Order Investigation

## Current Status (Updated)

### What Works:
- ✅ **PUT orders**: Successfully placing on LIVE account via bot
- ❌ **CALL orders**: Failing on LIVE account (user must place manually)
- ✅ **Both work on PAPER account**

### What We Know:
1. User manually placed the call order (SPY251210C00686000)
2. Bot detected the signal correctly
3. Bot attempted to place call order but failed
4. PUT orders have successfully executed via bot
5. The code for calls and puts is nearly identical

## Code Comparison

### Order Placement (IDENTICAL):
```python
# CALLS (line 1895)
order_result = wb.place_order_option(
    optionId=option_id,
    lmtPrice=ask_price,
    stpPrice=None,
    action='BUY',
    orderType='LMT',
    enforce='GTC',
    quant=order_quantity
)

# PUTS (line 2046)  
order_result = wb.place_order_option(
    optionId=option_id,
    lmtPrice=ask_price,
    stpPrice=None,
    action='BUY',
    orderType='LMT',
    enforce='GTC',
    quant=order_quantity
)
```

**Conclusion**: Order placement code is IDENTICAL. The difference must be in:
1. The option selection (strike/expiry)
2. Account permissions/restrictions
3. Webull API treating calls differently
4. Option availability or liquidity

## Theories

### Theory 1: Strike Selection Difference
**Call strikes**: Current price to Current price + $5 (OTM/ATM)
**Put strikes**: Current price - $5 to Current price (OTM/ATM)

**Possible issue**: 
- Calls might be selecting strikes that Webull doesn't allow for live automated trading
- Account might have restrictions on certain strike ranges
- OTM calls might have different risk classification

### Theory 2: Account Permissions
- Webull may have different approval levels for different option strategies
- CALL buying might require higher options trading level
- PUT buying might be approved at lower level

### Theory 3: Liquidity/Volume Filtering
Both filter by volume, but:
```python
# Line 2175
call_options.sort(key=lambda x: int(wb.get_option_quote(...)['data'][0]['volume']), reverse=True)
put_options.sort(key=lambda x: int(wb.get_option_quote(...)['data'][0]['volume']), reverse=True)
```

**Possible issue**:
- Calls might have lower volume at selected strikes
- API might reject low-volume options for live accounts
- Volume requirement might be stricter for calls

### Theory 4: Webull API Security
- Webull might treat call buying as higher risk
- Could require additional verification for calls
- API might have asymmetric security policies

### Theory 5: Option Availability
- Selected call options might not be available for trading when order attempts
- Expiration handling might differ for calls vs puts
- DTE selection might work differently

## What Will Help Diagnose

### Email Notifications (NOW ENABLED):
Next call order attempt will send email with:
1. **Attempt notification**: Confirms bot tried, shows symbol/strike/expiry
2. **Error notification**: Shows actual API error message
3. **Logs**: Raw API response logged for debugging

### Key Data Needed:
- Exact error message from Webull API
- Option symbol that failed
- Strike price selected
- Expiration date
- Volume of the option
- Time of day
- Account buying power

## Next Steps

1. **Wait for next CALL signal**
   - Bot will send attempt email
   - Check email for error details
   - Check logs for API response

2. **Compare with working PUT**
   - Note strike selection difference
   - Compare option symbols
   - Check volume differences

3. **Potential Fixes** (based on error):

   **If volume/liquidity issue**:
   - Increase minimum volume requirement for calls
   - Select more ATM strikes
   - Add liquidity checks before order

   **If strike range issue**:
   - Adjust call strike selection range
   - Match put strategy (more conservative)
   - Filter based on bid-ask spread

   **If account permission**:
   - Check Webull account options approval level
   - May need to upgrade options trading level
   - Contact Webull support

   **If API limitation**:
   - Add retry logic with different parameters
   - Try DAY instead of GTC for calls
   - Try different orderType combinations

## Files to Monitor

- `/app/backend/trading_bot_service.py` (lines 1816-1928: execute_call_trade)
- `/app/backend/my_webull.py` (line 829: place_order_option for live)
- Email notifications for actual error messages
- Backend logs after next call attempt

## Manual Testing Checklist

To test why puts work but calls don't:
1. Note the exact option symbol that PUT order succeeded with
2. Note the exact option symbol that CALL order failed with
3. Compare: strike relative to current price, DTE, volume, bid-ask spread
4. Check if option was actively trading at attempt time
5. Verify account has same approval level for both

---

**Status**: Waiting for next CALL signal to capture actual error message via new email notifications.
