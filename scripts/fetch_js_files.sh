#!/bin/bash

# Configuration
CONFIG_DIR="../config"
STORAGE_DIR="../storage"
LOG_DIR="../logs"
API_URL="http://localhost:5000"

# Load configuration
TARGETS_FILE="$CONFIG_DIR/targets.json"
DOMAINS=$(jq -r '.domains[]' "$TARGETS_FILE")

# Create directories
mkdir -p "$LOG_DIR"
mkdir -p "$STORAGE_DIR/snapshots"
mkdir -p "$STORAGE_DIR/diffs"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/fetch_$TIMESTAMP.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

process_domain() {
    local domain=$1
    log "Processing domain: $domain"
    
    # Step 1: Extract JS files
    log "Extracting JS files from $domain..."
    extraction_result=$(python3 extract_js.py "$domain")
    
    if [ -z "$extraction_result" ]; then
        log "Failed to extract JS files from $domain"
        return 1
    fi
    
    # Parse extraction results
    domain_name=$(echo "$extraction_result" | jq -r '.domain')
    files_json=$(echo "$extraction_result" | jq '.files')
    snapshot_path=$(echo "$extraction_result" | jq -r '.snapshot')
    
    # Step 2: Check for new files via API
    log "Checking for new/modified files..."
    check_response=$(curl -s -X POST "$API_URL/api/check-new-files" \
        -H "Content-Type: application/json" \
        -d "{\"domain\": \"$domain_name\", \"files\": $files_json}")
    
    new_files=$(echo "$check_response" | jq '.new_files')
    modified_files=$(echo "$check_response" | jq '.modified_files')
    
    new_count=$(echo "$new_files" | jq 'length')
    modified_count=$(echo "$modified_files" | jq 'length')
    
    log "Found $new_count new files and $modified_count modified files"
    
    # Step 3: Process new files
    if [ "$new_count" -gt 0 ]; then
        log "Processing $new_count new files..."
        
        for i in $(seq 0 $((new_count - 1))); do
            file=$(echo "$new_files" | jq ".[$i]")
            file_url=$(echo "$file" | jq -r '.url')
            file_hash=$(echo "$file" | jq -r '.hash')
            
            # Check if we should alert (deduplication)
            alert_check=$(curl -s -X POST "$API_URL/api/should-alert" \
                -H "Content-Type: application/json" \
                -d "{\"domain\": \"$domain_name\", \"file_url\": \"$file_url\", \"content_hash\": \"$file_hash\", \"alert_type\": \"new_file\"}")
            
            should_alert=$(echo "$alert_check" | jq -r '.should_alert')
            
            if [ "$should_alert" = "true" ]; then
                log "New file detected: $file_url"
                
                # Download and analyze file
                analyze_result=$(python3 analyze_js.py "$file_url")
                
                # Send to Slack
                python3 send_to_slack.py \
                    --domain "$domain_name" \
                    --file-url "$file_url" \
                    --file-hash "$file_hash" \
                    --alert-type "new_file" \
                    --analysis "$analyze_result"
                
                # Record alert
                curl -s -X POST "$API_URL/api/record-alert" \
                    -H "Content-Type: application/json" \
                    -d "{\"domain\": \"$domain_name\", \"file_url\": \"$file_url\", \"alert_type\": \"new_file\", \"content_hash\": \"$file_hash\"}" > /dev/null
            fi
        done
    fi
    
    # Step 4: Process modified files
    if [ "$modified_count" -gt 0 ]; then
        log "Processing $modified_count modified files..."
        
        for i in $(seq 0 $((modified_count - 1))); do
            file=$(echo "$modified_files" | jq ".[$i]")
            file_url=$(echo "$file" | jq -r '.url')
            file_hash=$(echo "$file" | jq -r '.hash')
            
            # Check if we should alert
            alert_check=$(curl -s -X POST "$API_URL/api/should-alert" \
                -H "Content-Type: application/json" \
                -d "{\"domain\": \"$domain_name\", \"file_url\": \"$file_url\", \"content_hash\": \"$file_hash\", \"alert_type\": \"modified_file\"}")
            
            should_alert=$(echo "$alert_check" | jq -r '.should_alert')
            
            if [ "$should_alert" = "true" ]; then
                log "Modified file detected: $file_url"
                
                # Download and analyze file
                analyze_result=$(python3 analyze_js.py "$file_url")
                
                # Get diff with previous version
                diff_result=$(python3 compare_changes.py "$domain_name" "$file_url")
                
                # Send to Slack
                python3 send_to_slack.py \
                    --domain "$domain_name" \
                    --file-url "$file_url" \
                    --file-hash "$file_hash" \
                    --alert-type "modified_file" \
                    --analysis "$analyze_result" \
                    --diff "$diff_result"
                
                # Record alert
                curl -s -X POST "$API_URL/api/record-alert" \
                    -H "Content-Type: application/json" \
                    -d "{\"domain\": \"$domain_name\", \"file_url\": \"$file_url\", \"alert_type\": \"modified_file\", \"content_hash\": \"$file_hash\"}" > /dev/null
            fi
        done
    fi
    
    # Step 5: Register all files in database
    log "Registering files in database..."
    curl -s -X POST "$API_URL/api/register-files" \
        -H "Content-Type: application/json" \
        -d "{\"domain\": \"$domain_name\", \"files\": $files_json}" > /dev/null
    
    log "Completed processing $domain"
}

# Main execution
log "Starting JS file monitoring scan"

for domain in $DOMAINS; do
    process_domain "$domain"
    
    # Rate limiting between domains
    sleep 5
done

log "Scan completed successfully"
