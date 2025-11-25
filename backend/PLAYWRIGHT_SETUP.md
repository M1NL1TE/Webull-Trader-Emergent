# Playwright Browser Setup

## Why is this needed?

This application uses **Playwright** for automated browser login to Webull. Playwright requires browser binaries (Chromium) to be installed separately from the Python package.

## The Problem

In containerized environments, Playwright browsers can be deleted during:
- Container restarts
- System updates
- Platform redeployments

When browsers are missing, you'll see this error:
```
BrowserType.launch: Executable doesn't exist at /pw-browsers/chromium_headless_shell-1187/...
```

## Solution 1: Automatic Installation (Recommended)

The backend now automatically checks and installs Playwright browsers on startup. This is handled in `server.py` via the `ensure_playwright_browsers()` function.

**How it works:**
- On startup, checks if `/pw-browsers/chromium_headless_shell-1187/chrome-linux/headless_shell` exists
- If missing, automatically runs `playwright install chromium`
- Logs the installation status

**No action needed** - browsers will auto-install on first startup!

## Solution 2: Manual Installation

If you need to manually install browsers:

```bash
cd /app/backend
python3 -m playwright install chromium
```

Or use the provided script:

```bash
cd /app/backend
./install_playwright.sh
```

## Solution 3: Add to Deployment Scripts

If you have custom deployment scripts, add this step after installing Python dependencies:

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

## Verification

Check if browsers are installed:

```bash
ls -la /pw-browsers/ | grep 1187
```

You should see:
- `chromium-1187`
- `chromium_headless_shell-1187`

## Version Compatibility

**Important:** Playwright Python library version must match browser version!

- **Current Setup:**
  - Playwright library: `1.55.0` (in requirements.txt)
  - Browser build: `1187`

If you upgrade Playwright, you may need to reinstall browsers:

```bash
pip install playwright==<new-version>
python3 -m playwright install chromium
```

## Troubleshooting

### Login fails with "Executable doesn't exist"
- **Cause:** Browsers are missing or wrong version installed
- **Fix (Quick):** Run this command immediately:
  ```bash
  cd /app/backend && python3 -m playwright install chromium --force
  ```
- **Fix (Auto):** Restart the backend (auto-install should fix it)

### Wrong browser version installed (1194 instead of 1187)
- **Cause:** System reinstalled browsers during restart, but installed wrong version
- **Symptoms:** Error says looking for build 1187 but only 1194 is installed
- **Fix:** Force reinstall correct version:
  ```bash
  cd /app/backend
  pip show playwright  # Verify version 1.55.0
  python3 -m playwright install chromium --force
  ```

### Browsers keep getting deleted
- **Cause:** Platform/container cleanup or redeployment
- **Fix:** The auto-install function in `server.py` should handle this automatically
- **If auto-install fails:** Run manual command above

### Auto-install runs but installs wrong version
- **Cause:** The auto-install uses `playwright install` which might install cached/wrong version
- **Fix:** After any login failure, run:
  ```bash
  cd /app/backend && python3 -m playwright install chromium --force
  ```
  The `--force` flag ensures correct version is downloaded

### Quick Fix Command (Copy & Paste)
```bash
cd /app/backend && python3 -m playwright install chromium --force && sudo supervisorctl restart backend
```
This command:
1. Installs correct browser version (1187 for Playwright 1.55.0)
2. Restarts backend to pick up new browsers

## Technical Details

- **Browser location:** `/pw-browsers/`
- **Environment variable:** `PLAYWRIGHT_BROWSERS_PATH=/pw-browsers` (set in server.py)
- **Browser size:** ~281 MB (Chromium + Headless Shell)
- **Installation time:** ~30-60 seconds depending on network speed

## Platform-Specific Notes

On Emergent platform:
- Supervisor config is read-only (cannot modify startup scripts)
- Solution: Auto-install on application startup (implemented ✅)
- Browsers may be removed during platform updates (auto-install handles this ✅)
