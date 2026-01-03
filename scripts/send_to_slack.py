#!/usr/bin/env python3

import json
import requests
import sys
import argparse
from datetime import datetime

def send_slack_alert(args):
    """Send alert to Slack"""
    
    # Load Slack configuration
    with open('../config/slack_config.json', 'r') as f:
        config = json.load(f)
    
    webhook_url = config['webhook_url']
    
    # Parse analysis if provided
    analysis = None
    if args.analysis:
        try:
            analysis = json.loads(args.analysis)
        except:
            analysis = {'summary': args.analysis}
    
    # Create message based on alert type
    if args.alert_type == "new_file":
        message = create_new_file_message(
            args.domain, args.file_url, args.file_hash, analysis
        )
    elif args.alert_type == "modified_file":
        message = create_modified_file_message(
            args.domain, args.file_url, args.file_hash, analysis, args.diff
        )
    else:
        message = create_generic_message(
            args.domain, args.file_url, args.alert_type
        )
    
    # Send to Slack
    response = requests.post(
        webhook_url,
        json=message,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        print(f"Alert sent successfully for {args.file_url}")
        return True
    else:
        print(f"Failed to send alert: {response.status_code}")
        return False

def create_new_file_message(domain, file_url, file_hash, analysis):
    """Create Slack message for new file detection"""
    
    risk_level = analysis.get('summary', {}).get('risk_level', 'UNKNOWN') if analysis else 'UNKNOWN'
    risk_color = {
        'HIGH': '#FF0000',
        'MEDIUM': '#FFA500',
        'LOW': '#00FF00',
        'UNKNOWN': '#808080'
    }.get(risk_level, '#808080')
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🚨 NEW JavaScript File Detected",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Domain:*\n`{domain}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Risk Level:*\n`{risk_level}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*File Hash:*\n`{file_hash[:16]}...`"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*File URL:*\n<{file_url}|{file_url.split('/')[-1][:50]}>"
            }
        }
    ]
    
    if analysis:
        summary = analysis.get('summary', {})
        if summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Analysis Summary:*\n"
                           f"• Sensitive Patterns: `{summary.get('sensitive_pattern_count', 0)}`\n"
                           f"• API Endpoints: `{summary.get('endpoint_count', 0)}`\n"
                           f"• File Size: `{summary.get('file_size', 0):,} bytes`\n"
                           f"• Lines: `{summary.get('line_count', 0)}`"
                }
            })
        
        # Add sensitive findings if any
        findings = analysis.get('findings', {}).get('sensitive_patterns', [])
        if findings and len(findings) > 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Sensitive Patterns Found:*\n"
                           f"Found `{len(findings)}` potential sensitive patterns"
                }
            })
            
            # Show first 3 findings
            for i, finding in enumerate(findings[:3]):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{i+1}. {finding.get('keyword', 'Pattern')}* (Line {finding.get('line', '?')})\n"
                               f"```{finding.get('context', '')[:100]}...```"
                    }
                })
    
    blocks.append({
        "type": "divider"
    })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"🔍 *JS File Monitor* | Detected new file on {domain}"
            }
        ]
    })
    
    return {
        "blocks": blocks,
        "attachments": [
            {
                "color": risk_color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Quick Actions:*\n"
                                   f"• <{file_url}|🔗 View File>\n"
                                   f"• <https://securityheaders.com/?q={domain}|🔍 Security Headers>\n"
                                   f"• <{file_url.replace('https://', 'https://web.archive.org/web/*/')}|📜 View on Archive>"
                        }
                    }
                ]
            }
        ]
    }

def create_modified_file_message(domain, file_url, file_hash, analysis, diff):
    """Create Slack message for modified file"""
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📝 JavaScript File Modified",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Domain:*\n`{domain}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*File:*\n`{file_url.split('/')[-1][:20]}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*New Hash:*\n`{file_hash[:16]}...`"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*File URL:*\n<{file_url}|{file_url}>"
            }
        }
    ]
    
    # Add diff if available
    if diff:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Changes Detected:*\nFile content has been modified. Hash changed from previous version."
            }
        })
    
    if analysis:
        summary = analysis.get('summary', {})
        if summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Current Analysis:*\n"
                           f"• Risk: `{summary.get('risk_level', 'UNKNOWN')}`\n"
                           f"• Patterns: `{summary.get('sensitive_pattern_count', 0)}`\n"
                           f"• Endpoints: `{summary.get('endpoint_count', 0)}`"
                }
            })
    
    blocks.append({
        "type": "divider"
    })
    
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"🔍 *JS File Monitor* | Detected modification on {domain}"
            }
        ]
    })
    
    return {"blocks": blocks}

def main():
    parser = argparse.ArgumentParser(description='Send JS file alerts to Slack')
    parser.add_argument('--domain', required=True, help='Domain name')
    parser.add_argument('--file-url', required=True, help='JS file URL')
    parser.add_argument('--file-hash', required=True, help='File content hash')
    parser.add_argument('--alert-type', required=True, choices=['new_file', 'modified_file', 'removed_file'])
    parser.add_argument('--analysis', help='JSON analysis results')
    parser.add_argument('--diff', help='Diff information')
    
    args = parser.parse_args()
    send_slack_alert(args)

if __name__ == "__main__":
    main()
