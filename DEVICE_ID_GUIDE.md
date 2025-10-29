# How to Get Your Webull Device ID (DID)

## Important: New Authentication Method

As of late 2024, Webull has implemented additional security measures that block traditional API logins. This app now uses **Playwright browser automation** to handle login automatically - **you no longer need to manually bypass CAPTCHA!**

**What you need:**
1. Your Device ID (DID) - a 32-character code that identifies your device
2. Your Webull username and password
3. Your trading PIN

Once you provide these, our system automates the browser login process for you.

---

## Getting Your Device ID (One-Time Setup)

### Step-by-Step Guide

#### 1. Open Webull in Browser
- Go to: https://app.webullbroker.com
- Use Chrome, Firefox, or Edge

#### 2. Open Developer Tools
- **Windows/Linux**: Press `F12` or `Ctrl+Shift+I`
- **Mac**: Press `Cmd+Option+I`

#### 3. Prepare Network Tab
- Click on the **"Network"** tab
- ✅ **CHECK** the "Preserve log" option (important!)
- Make sure recording is active (red circle)

#### 4. Login to Webull
- Enter your credentials
- **Complete any CAPTCHA/image verification if shown**
- Login successfully

#### 5. Extract the Device ID
After successful login:
- In the Network tab, you'll see many requests
- Click on **any request** (usually ones starting with "account", "login", or "trade")
- In the right panel, click **"Headers"**
- Scroll down to **"Request Headers"** section
- Find the line that says: `did: [32-character-code]`
- **Copy the 32-character code**

Example:
```
did: 97468314e9674207be4aa99b13f749c9
```

#### 6. Use in the App
- Paste your DID into the "Device ID" field on the login page
- The DID is saved and reused automatically
- You won't need to get it again unless it expires

---

## What Changed from Traditional Login?

### Old Method (No Longer Works)
❌ Direct API login → blocked by Webull's new security headers  
❌ Manual CAPTCHA bypass → too complex and unreliable  
❌ Chrome extension hacks → requires manual intervention

### New Method (Playwright Automation) ✅
✅ Automated browser login → handles all security checks  
✅ Set DID as cookie → bypasses CAPTCHA automatically  
✅ Captures tokens from network → works like real browser  
✅ Fully automated → no manual intervention needed

---

## How the New System Works

1. **You provide**: Username, Password, Trade PIN, and DID
2. **System starts**: Headless Chrome browser (in background)
3. **Sets DID cookie**: Before navigating to login page
4. **Automates login**: Fills form and clicks login
5. **Captures tokens**: Intercepts network responses
6. **Saves session**: Stores tokens for future use
7. **Closes browser**: Clean up

**Time**: Takes 30-60 seconds  
**CAPTCHA**: Should not appear (DID cookie prevents it)  
**Security**: Credentials used once, never stored

---

## Troubleshooting

### "Device ID must be exactly 32 characters"
- Check you copied the full DID value
- Should only contain: `0-9` and `a-f` (hex characters)
- Remove any quotes or spaces

### "CAPTCHA still appears"
- Your DID may be expired or from different browser
- Get a fresh DID following the steps above
- Make sure you're using the same Webull account

### "Login timeout"
- Internet connection may be slow
- Try again - sometimes Webull's servers are slow
- Check backend logs for specific errors

### "Cannot find 'did' in headers"
- Make sure "Preserve log" is checked in Network tab
- Look at **Request Headers**, not Response Headers
- Try different API requests - some show it, some don't
- Common requests with DID: `/account`, `/login`, `/trade`

### DID Expired?
DIDs typically last 4-6 weeks. Signs of expiration:
- Login keeps failing
- CAPTCHA appears despite DID
- "Illegal Client" or 403 errors

**Solution**: Get a fresh DID from a new browser login

---

## Security Notes

### Is This Safe?
✅ **Yes** - The browser automation:
- Runs in a controlled environment
- Only accesses Webull's official website
- Doesn't store your credentials
- Uses the same security as manual browser login

### What Gets Stored?
- ✅ Device ID (DID)
- ✅ Access Token (temporary)
- ✅ Refresh Token (temporary)
- ✅ UUID (session identifier)
- ❌ NOT stored: Username, Password, Trade PIN

### Keep Your DID Private
⚠️ Your DID can be used to authenticate as your device. Don't share it publicly.

---

## Why Webull Made These Changes

Webull added these security measures to prevent:
- Unauthorized bot trading
- API abuse
- Account takeovers
- Rate limit bypassing

The Playwright approach respects these security measures by:
- Using legitimate browser automation
- Passing all security checks
- Not attempting to crack or bypass protections
- Working within Webull's intended flow

---

## Alternative: Using Saved Tokens

Once you've logged in successfully once, the app saves your tokens. These tokens typically last for weeks, so you won't need to login every time.

**Session persistence**:
- Tokens stored in MongoDB
- Automatically restored on page reload
- Trade PIN still required for trading
- Valid for 4-6 weeks typically

---

## Reference

- **Webull GitHub Issue**: https://github.com/tedchou12/webull/issues/456
- **Original Workaround**: Based on solution by @brenosilver
- **Playwright Docs**: https://playwright.dev/python/

---

## Need Help?

If you're still having issues:
1. Check backend logs: `/var/log/supervisor/backend.err.log`
2. Verify your DID is exactly 32 characters
3. Try getting a fresh DID
4. Ensure you're using Paper Trading mode for testing
5. Contact support with error messages

