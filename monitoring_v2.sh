#!/bin/bash

FETCH="./fetch_metrics.sh"
ANALYZER="./log_analyzer_v2.py"


# Check fetch script
if [ ! -f "$FETCH" ]; then
    echo "ERROR: Script for download logs ($FETCH) not found."
    exit 1
fi

# Check analyze scripts
if [ ! -f "$ANALYZER" ]; then
    echo "ERROR: Script for analyze logs ($ANALYZER) not found."
    exit 1
fi

# Download logs
echo "Download logs from servers..."
bash "$FETCH"


# Do scripts for starting
chmod +x "$ANALYZER"

# Analyze logs
echo "Start analyzing logs..."
python3 "$ANALYZER"

echo "Analysing logs is succes. Report send to Telegram."
