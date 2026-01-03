#!/usr/bin/env python3

import requests
import re
import json
from typing import Dict, List
import sys

class JSAnalyzer:
    def __init__(self):
        self.sensitive_keywords = self.load_keywords()
        
    def load_keywords(self) -> List[str]:
        """Load sensitive keywords to look for"""
        try:
            with open('../config/keywords.txt', 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except:
            return [
                'api_key', 'apikey', 'secret', 'password', 'token',
                'auth', 'credential', 'private', 'internal', 'admin',
                'access_key', 'secret_key', 'jwt', 'bearer', 'oauth',
                'endpoint', 'database', 'connection', 'config',
                'aws_key', 'aws_secret', 's3_bucket', 'github_token'
            ]
    
    def download_file(self, url: str) -> str:
        """Download JS file content"""
        try:
            response = requests.get(url, timeout=30, verify=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return ""
    
    def analyze_content(self, content: str) -> Dict:
        """Analyze JS content for sensitive information"""
        findings = {
            'sensitive_patterns': [],
            'endpoints': [],
            'comments': [],
            'file_size': len(content),
            'line_count': content.count('\n') + 1
        }
        
        # Look for sensitive patterns
        for keyword in self.sensitive_keywords:
            pattern = re.compile(rf'\b{keyword}\b', re.IGNORECASE)
            matches = pattern.findall(content)
            if matches:
                # Get context around matches
                for match in set(matches):
                    # Find line numbers
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if match.lower() in line.lower():
                            # Extract context (2 lines before and after)
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context = '\n'.join(lines[start:end])
                            
                            findings['sensitive_patterns'].append({
                                'keyword': match,
                                'line': i + 1,
                                'context': context[:500]  # Limit context length
                            })
                            break
        
        # Look for API endpoints
        endpoint_patterns = [
            r'["\'](https?://[^"\']+?/api/[^"\']*?)["\']',
            r'["\'](/api/[^"\']*?)["\']',
            r'fetch\(["\']([^"\']+?)["\']',
            r'axios\.(?:get|post|put|delete)\(["\']([^"\']+?)["\']',
            r'\.ajax\([^)]*?url:\s*["\']([^"\']+?)["\']'
        ]
        
        for pattern in endpoint_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match and len(match) < 200:  # Sanity check
                    findings['endpoints'].append(match)
        
        # Extract comments (potential information disclosure)
        comment_patterns = [
            r'//\s*(.*?)$',  # Single line comments
            r'/\*\*(.*?)\*/',  # JSDoc comments
            r'/\*!(.*?)\*/',  # Important comments
        ]
        
        for pattern in comment_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
            for match in matches:
                clean_comment = ' '.join(match.strip().split())
                if len(clean_comment) > 20:  # Only significant comments
                    findings['comments'].append(clean_comment[:200])  # Limit length
        
        # Look for hardcoded credentials patterns
        credential_patterns = [
            r'["\'](eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)["\']',  # JWT
            r'["\'](AKIA[0-9A-Z]{16})["\']',  # AWS Access Key
            r'["\']([0-9a-f]{40})["\']',  # SHA1 hash
            r'["\']([0-9a-f]{64})["\']',  # SHA256 hash
        ]
        
        for pattern in credential_patterns:
            matches = re.findall(pattern, content)
            findings['sensitive_patterns'].extend([
                {'keyword': 'POTENTIAL_CREDENTIAL', 'pattern': match[:50]}
                for match in matches
            ])
        
        return findings
    
    def get_summary(self, findings: Dict) -> Dict:
        """Generate summary of findings"""
        risk_level = "LOW"
        
        if len(findings['sensitive_patterns']) > 5:
            risk_level = "HIGH"
        elif len(findings['sensitive_patterns']) > 2:
            risk_level = "MEDIUM"
        
        return {
            'risk_level': risk_level,
            'sensitive_pattern_count': len(findings['sensitive_patterns']),
            'endpoint_count': len(findings['endpoints']),
            'comment_count': len(findings['comments']),
            'file_size': findings['file_size'],
            'line_count': findings['line_count']
        }

def main():
    if len(sys.argv) != 2:
        print("Usage: analyze_js.py <js_file_url>")
        sys.exit(1)
    
    url = sys.argv[1]
    analyzer = JSAnalyzer()
    
    print(f"Analyzing: {url}")
    
    # Download file
    content = analyzer.download_file(url)
    if not content:
        print("Failed to download file")
        sys.exit(1)
    
    # Analyze content
    findings = analyzer.analyze_content(content)
    summary = analyzer.get_summary(findings)
    
    # Output results
    result = {
        'url': url,
        'summary': summary,
        'findings': findings
    }
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
