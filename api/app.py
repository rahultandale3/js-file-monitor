from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import hashlib
import json
import os
from typing import Dict, List, Set

app = Flask(__name__)
CORS(app)

def init_db():
    """Initialize database with tables for JS file tracking"""
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    
    # Table for tracking discovered JS files
    c.execute('''CREATE TABLE IF NOT EXISTS js_files
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  domain TEXT NOT NULL,
                  url TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  hash TEXT NOT NULL,
                  first_seen TIMESTAMP NOT NULL,
                  last_seen TIMESTAMP NOT NULL,
                  is_active BOOLEAN DEFAULT 1,
                  UNIQUE(domain, url))''')
    
    # Table for alert history
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  domain TEXT NOT NULL,
                  file_url TEXT NOT NULL,
                  alert_type TEXT NOT NULL,
                  content_hash TEXT NOT NULL,
                  alerted_at TIMESTAMP NOT NULL,
                  UNIQUE(domain, file_url, alert_type, content_hash))''')
    
    # Table for file contents (store hashed content)
    c.execute('''CREATE TABLE IF NOT EXISTS file_contents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  domain TEXT NOT NULL,
                  url TEXT NOT NULL,
                  content_hash TEXT NOT NULL,
                  snapshot_date TIMESTAMP NOT NULL)''')
    
    conn.commit()
    conn.close()

@app.route('/api/check-new-files', methods=['POST'])
def check_new_files():
    """Check which files are new compared to historical data"""
    data = request.json
    domain = data['domain']
    current_files = data['files']  # List of dicts: {url, filename, hash}
    
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    
    # Get known files for this domain
    c.execute('''SELECT url, hash, filename FROM js_files 
                 WHERE domain=? AND is_active=1''', (domain,))
    known_files = {row[0]: {'hash': row[1], 'filename': row[2]} for row in c.fetchall()}
    
    new_files = []
    modified_files = []
    
    for file in current_files:
        url = file['url']
        file_hash = file['hash']
        
        if url not in known_files:
            # New file
            new_files.append(file)
        elif known_files[url]['hash'] != file_hash:
            # Modified file
            modified_files.append(file)
    
    conn.close()
    
    return jsonify({
        'new_files': new_files,
        'modified_files': modified_files,
        'total_current': len(current_files),
        'total_known': len(known_files)
    })

@app.route('/api/register-files', methods=['POST'])
def register_files():
    """Register newly discovered files in database"""
    data = request.json
    domain = data['domain']
    files = data['files']
    
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    now = datetime.now()
    
    # Mark all current files as inactive first
    c.execute('UPDATE js_files SET is_active=0 WHERE domain=?', (domain,))
    
    for file in files:
        url = file['url']
        filename = file['filename']
        file_hash = file['hash']
        
        # Check if file already exists
        c.execute('''SELECT id FROM js_files WHERE domain=? AND url=?''', 
                  (domain, url))
        result = c.fetchone()
        
        if result:
            # Update existing record
            c.execute('''UPDATE js_files SET 
                         hash=?, last_seen=?, is_active=1 
                         WHERE id=?''',
                      (file_hash, now, result[0]))
        else:
            # Insert new record
            c.execute('''INSERT INTO js_files 
                         (domain, url, filename, hash, first_seen, last_seen)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (domain, url, filename, file_hash, now, now))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'registered': len(files)})

@app.route('/api/should-alert', methods=['POST'])
def should_alert():
    """Check if we should alert about this file (deduplication)"""
    data = request.json
    domain = data['domain']
    file_url = data['file_url']
    content_hash = data['content_hash']
    alert_type = data.get('alert_type', 'new_file')
    
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    
    # Check if same alert was sent in last 7 days
    cutoff = datetime.now() - timedelta(days=7)
    c.execute('''SELECT COUNT(*) FROM alerts 
                 WHERE domain=? AND file_url=? AND alert_type=? 
                 AND content_hash=? AND alerted_at > ?''',
              (domain, file_url, alert_type, content_hash, cutoff))
    
    count = c.fetchone()[0]
    conn.close()
    
    return jsonify({'should_alert': count == 0})

@app.route('/api/record-alert', methods=['POST'])
def record_alert():
    """Record that an alert was sent"""
    data = request.json
    domain = data['domain']
    file_url = data['file_url']
    alert_type = data['alert_type']
    content_hash = data['content_hash']
    
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO alerts 
                 (domain, file_url, alert_type, content_hash, alerted_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (domain, file_url, alert_type, content_hash, datetime.now()))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/stats/<domain>', methods=['GET'])
def get_stats(domain):
    """Get statistics for a domain"""
    conn = sqlite3.connect('/storage/database/js_monitor.db')
    c = conn.cursor()
    
    # Total files tracked
    c.execute('''SELECT COUNT(*) FROM js_files WHERE domain=?''', (domain,))
    total = c.fetchone()[0]
    
    # Currently active files
    c.execute('''SELECT COUNT(*) FROM js_files WHERE domain=? AND is_active=1''', 
              (domain,))
    active = c.fetchone()[0]
    
    # New files in last 24 hours
    cutoff = datetime.now() - timedelta(days=1)
    c.execute('''SELECT COUNT(*) FROM js_files 
                 WHERE domain=? AND first_seen > ?''',
              (domain, cutoff))
    recent = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'domain': domain,
        'total_files_tracked': total,
        'currently_active_files': active,
        'new_files_last_24h': recent
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
