# Session Caching Issue - Paper vs Live Account

## What Happened

### User Experience:
1. User was on LIVE account
2. Preview refreshed/showed login screen
3. User assumed they needed to log in
4. User logged in to PAPER account
5. Bot placed a trade (user saw it succeed on paper)
6. But backend was still showing LIVE account data
7. Email notification showed order failure

### Root Cause:
**Session Caching Mismatch**

The backend has multiple layers of session storage:
1. **Database (MongoDB)**: Stores `is_paper: true/false` flag and session tokens
2. **In-Memory Cache**: Webull session object cached in Python
3. **HTTP Session**: Session restored on backend restart

### What Went Wrong:

```
Database Session: is_paper = true (PAPER account)
     ↓
Webull API Response: accountMembers[0].key = "totalMarketValue" (LIVE account)
     ↓
MISMATCH! The session tokens are for LIVE, but database says PAPER
```

## Why This Happened

### Scenario:
1. User was logged into LIVE account
2. Backend saved LIVE session tokens to database with `is_paper: false`
3. User switched to paper trading on frontend
4. Frontend updated `is_paper: true` in database
5. **BUT** the actual Webull session tokens (access_token, trade_token) were NOT updated
6. Backend still using LIVE account tokens
7. When backend restarted, it restored the old LIVE tokens but with `is_paper: true` flag

### The Problem:
Changing the `is_paper` flag in the database doesn't change which account the session tokens authenticate to. The tokens themselves determine the account.

## Current State

**Database says:** Paper account (`is_paper: true`)  
**Webull API says:** Live account ($43,046 balance, 45 contracts)  
**Bot is trading on:** LIVE account (using old tokens)

## The Fix

### What I Did:
1. ✅ Deleted all sessions from database
2. ✅ Stopped the bot
3. ✅ Restarted backend to clear in-memory cache

### What User Needs To Do:
**Log in again from the login screen:**
1. Enter Webull credentials
2. **Check the "Use Paper Trading" checkbox** (critical!)
3. Submit login
4. Backend will create fresh PAPER account session

### Important:
The checkbox on the login form determines which account Webull authenticates to. The database flag alone is not enough - you need fresh tokens for the correct account.

## How To Properly Switch Accounts

### ❌ WRONG Way:
1. Just refresh the page
2. Assume it logged you out
3. Log back in

**Problem:** Backend might restore old session

### ✅ CORRECT Way:
1. Click **"Logout"** button explicitly
2. Wait for backend to clear session
3. Refresh page to get login screen
4. Log in with correct account checkbox

### Alternative (When Logout Doesn't Work):
1. Backend restart clears session (what we just did)
2. Or manually clear database session (advanced)

## Preventing This In Future

### Backend Improvement Needed:
1. **Validate session on load**: Check if `is_paper` flag matches actual account
2. **Detect mismatch**: If mismatch detected, invalidate session
3. **Force re-login**: Show login screen if validation fails

### Code Location:
`/app/backend/server.py` - `restore_session_from_db()` function

### Proposed Fix:
```python
async def restore_session_from_db():
    session = db.sessions.find_one()
    if session:
        # Restore session
        wb.restore_session(session)
        
        # VALIDATE session matches expected account type
        account_info = wb.get_account()
        actual_is_paper = (account_info['accountMembers'][0]['key'] == 'paperAccountHoldings')
        expected_is_paper = session['is_paper']
        
        if actual_is_paper != expected_is_paper:
            logger.warning("Session mismatch detected! Clearing...")
            db.sessions.delete_many({})
            return None  # Force re-login
```

## Lesson Learned

**Session tokens are account-specific.**  
You cannot switch accounts by changing a flag - you need fresh tokens from Webull for the target account.

## Action Items

**For User:**
1. ✅ Session cleared
2. 🔄 Log in again with paper checkbox
3. ✅ Verify account type in dashboard
4. ✅ Check email notifications for account prefix (📄 PAPER)

**For Developer (future):**
1. Add session validation on restore
2. Add explicit logout endpoint
3. Show account type prominently in UI
4. Prevent session mismatch at the code level

---

**Status:** Session cleared. User needs to log in again with paper trading checkbox to establish fresh paper account session.
