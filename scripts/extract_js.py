#!/usr/bin/env python3

import requests
from urllib.parse import urljoin, urlparse
import re
import hashlib
import json
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Set
import os

class JSExtractor:
    def __init__(self, domain: str):
        self.domain = domain
        self.base_url = f"https://{domain}"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.js_files = {}
        
    def get_page_content(self, url: str) -> str:
        """Fetch page content with error handling"""
        try:
            response = self.session.get(url, timeout=30, verify=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""
    
    def extract_js_from_html(self, html: str, base_url: str) -> Set[str]:
        """Extract JS file URLs from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        js_urls = set()
        
        # Find script tags with src attribute
        for script in soup.find_all('script', src=True):
            src = script['src']
            if src:
                # Handle relative URLs
                if src.startswith('//'):
                    src = f"https:{src}"
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith(('http://', 'https://')):
                    src = urljoin(base_url, src)
                
                # Filter only .js files
                if src.endswith('.js') or '.js?' in src:
                    js_urls.add(src)
        
        # Also look for JS files in link tags (uncommon but possible)
        for link in soup.find_all('link', href=True):
            href = link['href']
            if href.endswith('.js'):
                if href.startswith('//'):
                    href = f"https:{href}"
                elif href.startswith('/'):
                    href = urljoin(base_url, href)
                js_urls.add(href)
        
        return js_urls
    
    def extract_from_response_text(self, text: str, base_url: str) -> Set[str]:
        """Extract JS file patterns from raw response text"""
        js_patterns = [
            r'src=["\']([^"\']+\.js[^"\']*)["\']',
            r'url\(["\']?([^"\'\)]+\.js[^"\'\)]*)["\']?\)',
            r'["\']([^"\']+\.js\?[^"\']+)["\']',
            r'([a-zA-Z0-9_\-]+\.js\b)'
        ]
        
        found_urls = set()
        for pattern in js_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.startswith('//'):
                    match = f"https:{match}"
                elif match.startswith('/'):
                    match = urljoin(base_url, match)
                elif not match.startswith(('http://', 'https://')):
                    match = urljoin(base_url, match)
                
                if '.js' in match.lower():
                    found_urls.add(match)
        
        return found_urls
    
    def get_file_hash(self, url: str) -> str:
        """Get hash of JS file content"""
        try:
            response = self.session.get(url, timeout=30, verify=True)
            if response.status_code == 200:
                content = response.text
                return hashlib.sha256(content.encode()).hexdigest()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        
        return ""
    
    def crawl_for_js(self, max_pages: int = 10) -> List[Dict]:
        """Crawl the website to find JS files"""
        visited = set()
        to_visit = [self.base_url]
        all_js_files = {}
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            
            print(f"Crawling: {url}")
            visited.add(url)
            
            try:
                # Get page content
                html = self.get_page_content(url)
                if not html:
                    continue
                
                # Extract JS files from HTML
                html_js = self.extract_js_from_html(html, url)
                
                # Extract JS files from raw text
                text_js = self.extract_from_response_text(html, url)
                
                # Combine all JS files
                page_js = html_js.union(text_js)
                
                # Process each JS file
                for js_url in page_js:
                    if js_url not in all_js_files:
                        file_hash = self.get_file_hash(js_url)
                        if file_hash:  # Only include files we can access
                            filename = os.path.basename(urlparse(js_url).path)
                            if not filename:
                                filename = js_url.split('/')[-1]
                            
                            all_js_files[js_url] = {
                                'url': js_url,
                                'filename': filename,
                                'hash': file_hash,
                                'source_page': url
                            }
                
                # Extract links for further crawling
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(url, href)
                    
                    # Only follow links within the same domain
                    if self.domain in full_url and full_url not in visited:
                        to_visit.append(full_url)
                
                # Be polite
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        return list(all_js_files.values())
    
    def save_snapshot(self, files: List[Dict]):
        """Save current snapshot of JS files"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snapshot_dir = f"/storage/snapshots/{self.domain}"
        os.makedirs(snapshot_dir, exist_ok=True)
        
        snapshot_file = f"{snapshot_dir}/snapshot_{timestamp}.json"
        with open(snapshot_file, 'w') as f:
            json.dump({
                'domain': self.domain,
                'timestamp': timestamp,
                'total_files': len(files),
                'files': files
            }, f, indent=2)
        
        print(f"Snapshot saved: {snapshot_file}")
        return snapshot_file

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: extract_js.py <domain>")
        sys.exit(1)
    
    domain = sys.argv[1]
    extractor = JSExtractor(domain)
    
    print(f"Extracting JS files from {domain}...")
    js_files = extractor.crawl_for_js(max_pages=20)
    
    print(f"Found {len(js_files)} JS files")
    
    # Save snapshot
    snapshot_path = extractor.save_snapshot(js_files)
    
    # Output for pipeline
    print(json.dumps({
        'domain': domain,
        'files': js_files,
        'snapshot': snapshot_path
    }))

if __name__ == "__main__":
    main()
