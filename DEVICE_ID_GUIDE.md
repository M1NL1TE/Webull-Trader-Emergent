# How to Get Your Webull Device ID (DID)

Due to Webull's new CAPTCHA/image verification system, you need to extract your Device ID from a successful browser login.

## Step-by-Step Guide

### 1. Open Webull in Browser
- Go to: https://app.webullbroker.com
- Use Chrome, Firefox, or Edge (must support Developer Tools)

### 2. Open Developer Tools
- **Windows/Linux**: Press `F12` or `Ctrl+Shift+I`
- **Mac**: Press `Cmd+Option+I`

### 3. Go to Network Tab
- Click on the "Network" tab in Developer Tools
- Make sure it's recording (red circle should be active)

### 4. Login to Webull
- Enter your username and password
- **Complete the image verification/CAPTCHA**
- Login successfully

### 5. Find the Device ID
After successful login:
- Look for any API request in the Network tab (usually starts with `login`, `account`, or `user`)
- Click on the request
- Go to the **Headers** section
- Scroll down to **Request Headers**
- Find the `did` field
- Copy the value (it's a 32-character hexadecimal string)

Example DID format: `97468314e9674207be4aa99b13f749c9`

### 6. Use the DID in Your App
- Paste the DID into the "Device ID" field on the login page
- This DID will be saved and reused for future logins
- You only need to do this once

## Screenshots Guide

### Finding DID in Chrome DevTools:
```
1. F12 → Network tab
2. Login to Webull
3. Click any request (e.g., "login" or "account")
4. Headers → Request Headers → did: [YOUR_32_CHAR_HEX]
```

### Example Request Headers:
```
Accept: application/json
Content-Type: application/json
did: 97468314e9674207be4aa99b13f749c9  ← COPY THIS
platform: web
User-Agent: Mozilla/5.0...
```

## Troubleshooting

### "Cannot find 'did' in headers"
- Make sure you're looking at the **Request Headers**, not Response Headers
- Try a different API request - look for requests to `userapi.webull.com` or `tradeapi.webullbroker.com`
- Ensure you completed login successfully

### "Invalid Device ID"
- Make sure the DID is exactly 32 characters
- Should only contain lowercase letters (a-f) and numbers (0-9)
- No spaces or special characters

### "Still getting CAPTCHA error"
- The DID might be expired
- Try getting a fresh DID by logging out and in again in the browser
- Make sure you're using the same Webull account

## Why is This Needed?

Webull implemented image verification (CAPTCHA) in 2023 to prevent automated bot trading. The Device ID is a unique identifier that Webull uses to recognize "trusted" devices that have completed image verification. By extracting the DID from a successful browser login, we can reuse it for API access.

## Alternative: Use Existing DID

If you've successfully logged in before and the code created a `did.bin` file, you can find the DID in that file:
- Location: `/app/backend/did.bin` (if running locally)
- Open with a hex editor or Python pickle loader

## Security Note

⚠️ Keep your Device ID private! Anyone with your DID could potentially bypass CAPTCHA for your account.

## References

- Official Workaround Guide: https://github.com/tedchou12/webull/wiki/Workaround-for-Login
- GitHub Issue: https://github.com/tedchou12/webull/issues/409
