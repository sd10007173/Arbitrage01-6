#!/bin/bash
# Cron wrapper script to handle macOS security restrictions

# Set working directory
cd /Users/chenhourun/Desktop/Arbitrage01-3

# Set environment variables
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Create log directory if it doesn't exist
mkdir -p logs

# Get current date for log filename
LOG_DATE=$(date +%Y-%m-%d)
LOG_FILE="logs/batch_execution_${LOG_DATE}.log"

# Log start time
echo "=== Cron job started at $(date) ===" >> "$LOG_FILE"

# Run the Python script with full path
/Users/chenhourun/Desktop/Arbitrage01-3/venv/bin/python3 /Users/chenhourun/Desktop/Arbitrage01-3/get_return_run_all_users.py >> "$LOG_FILE" 2>&1

# Log completion
echo "=== Cron job completed at $(date) ===" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"