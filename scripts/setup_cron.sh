#!/bin/bash
# Setup cron job for daily runs on Linux/Mac
# Run: chmod +x setup_cron.sh && ./setup_cron.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)

echo "Setting up daily cron job..."
echo "Script directory: $SCRIPT_DIR"
echo "Python path: $PYTHON_PATH"

# Add cron job for 10 AM daily
(crontab -l 2>/dev/null; echo "0 10 * * * cd $SCRIPT_DIR && $PYTHON_PATH daily_run.py >> $SCRIPT_DIR/../data/daily_run.log 2>&1") | crontab -

echo "Cron job added. Current crontab:"
crontab -l

echo ""
echo "To remove: crontab -e and delete the line"
