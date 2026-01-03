#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import difflib

class ChangeDetector:
    def __init__(self, domain: str):
        self.domain = domain
        self.snapshot_dir = f"../storage/snapshots/{domain}"
    
    def get_latest_snapshot(self) -> Optional[Dict]:
        """Get the most recent snapshot for this domain"""
        if not os.path.exists(self.snapshot_dir):
            return None
        
        snapshots = [f for f in os.listdir(self.snapshot_dir) 
                    if f.startswith('snapshot_') and f.endswith('.json')]
        
        if not snapshots:
            return None
        
        # Sort by timestamp (newest first)
        snapshots.sort(reverse=True)
        
        # Get the second latest for comparison
        if len(snapshots) > 1:
            latest_file = os.path.join(self.snapshot_dir, snapshots[1])
        else:
            latest_file = os.path.join(self.snapshot_dir, snapshots[0])
        
        try:
            with open(latest_file, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def compare_files(self, old_files: List[Dict], new_files: List[Dict]) -> Dict:
        """Compare two sets of files and identify changes"""
        old_by_url = {f['url']: f for f in old_files}
        new_by_url = {f['url']: f for f in new_files}
        
        added = [f for url, f in new_by_url.items() if url not in old_by_url]
        removed = [f for url, f in old_by_url.items() if url not in new_by_url]
        changed = []
        
        for url, new_file in new_by_url.items():
            if url in old_by_url:
                old_file = old_by_url[url]
                if old_file['hash'] != new_file['hash']:
                    changed.append({
                        'url': url,
                        'old_hash': old_file['hash'],
                        'new_hash': new_file['hash'],
                        'filename': new_file['filename']
                    })
        
        return {
            'added': added,
            'removed': removed,
            'changed': changed,
            'total_old': len(old_files),
            'total_new': len(new_files)
        }
    
    def get_file_content_diff(self, url: str, old_content: str, new_content: str) -> str:
        """Generate a diff between old and new content"""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile='old', tofile='new',
            lineterm='\n'
        )
        
        return ''.join(diff)

def main():
    if len(sys.argv) != 3:
        print("Usage: compare_changes.py <domain> <file_url>")
        sys.exit(1)
    
    domain = sys.argv[1]
    file_url = sys.argv[2]
    
    detector = ChangeDetector(domain)
    
    # Get latest snapshot
    snapshot = detector.get_latest_snapshot()
    
    if not snapshot:
        print("No previous snapshot found")
        sys.exit(0)
    
    # Find the file in snapshot
    old_file = None
    for f in snapshot['files']:
        if f['url'] == file_url:
            old_file = f
            break
    
    if not old_file:
        print("File not found in previous snapshot")
        sys.exit(0)
    
    # In a real implementation, you would fetch the old content
    # For now, just return basic comparison
    result = {
        'domain': domain,
        'file_url': file_url,
        'previous_snapshot': snapshot['timestamp'],
        'file_was_present': True,
        'hash_changed': True  # We know this from the API check
    }
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
