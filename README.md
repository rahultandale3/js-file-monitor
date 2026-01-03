Project Structure


data-monitoring-system/
├── api/
│   ├── app.py
│   ├── requirements.txt
│   ├── database.py
│   ├── models.py
│   └── config.py
├── scripts/
│   ├── data_fetcher.sh
│   ├── process_data.py
│   ├── send_to_slack.py
│   └── deduplicate.py
├── config/
│   ├── environment.conf
│   └── domains.list
├── storage/
│   ├── data_cache/
│   └── sent_history/
├── logs/
├── setup.sh
├── docker-compose.yml
├── Dockerfile
├── README.md
└── systemd/
    ├── data-monitor.service
    └── data-monitor.timer
