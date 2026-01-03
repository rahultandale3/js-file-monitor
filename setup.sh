#!/bin/bash

echo "Setting up JS File Monitoring System..."

# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    jq \
    curl \
    cron \
    sqlite3

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p storage/snapshots
mkdir -p storage/diffs
mkdir -p storage/database
mkdir -p logs
mkdir -p config

# Initialize database
cd api
python -c "from app import init_db; init_db()"
cd ..

# Create default config files if they don't exist
if [ ! -f config/targets.json ]; then
    cat > config/targets.json << EOF
{
    "domains": [
        "heckerone.com",
        "tesla.com",
        "apple.com"
    ],
    "scan_frequency_minutes": 1440,
    "max_pages_per_domain": 20
}
EOF
fi

if [ ! -f config/slack_config.json ]; then
    cat > config/slack_config.json << EOF
{
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "channel": "#js-monitor-alerts"
}
EOF
    echo "Please update config/slack_config.json with your Slack webhook URL"
fi

# Make scripts executable
chmod +x scripts/*.py
chmod +x scripts/*.sh

# Setup crontab
(crontab -l 2>/dev/null; echo "0 */6 * * * cd $(pwd) && ./scripts/fetch_js_files.sh >> logs/cron.log 2>&1") | crontab -

echo "Setup completed!"
echo ""
echo "To start the API server:"
echo "  cd api && python app.py"
echo ""
echo "To run a manual scan:"
echo "  ./scripts/fetch_js_files.sh"
echo ""
echo "Don't forget to update your Slack webhook in config/slack_config.json"
