#!/bin/bash
# Install Playwright browsers for Webull automation
# This script should be run after installing Python dependencies

echo "🔧 Installing Playwright browsers..."

cd /app/backend

# Install chromium browser (build 1187 to match playwright 1.55.0)
python3 -m playwright install chromium

if [ $? -eq 0 ]; then
    echo "✅ Playwright browsers installed successfully!"
    echo "📍 Browsers installed at: /pw-browsers/chromium-1187"
else
    echo "❌ Failed to install Playwright browsers"
    exit 1
fi
