#!/bin/bash

################################################################################
# push_to_git_plus.sh - Enhanced Git Push Script for App AMB W TDS v6.0.0
#
# Purpose: Easy automated Git push with smart defaults and enhanced features
# Version: 4.1.2
# Date: October 17, 2025
# Author: MiniMax Agent
#
# Usage: 
#   ./push_to_git_plus.sh                    # Auto-commit with smart message
#   ./push_to_git_plus.sh "commit message"   # Custom commit message
#   ./push_to_git_plus.sh "message" v1.0.0   # Custom message with tag
#   ./push_to_git_plus.sh --interactive      # Interactive mode
#   ./push_to_git_plus.sh --dry-run          # Show what would happen
#   ./push_to_git_plus.sh --feature "name"   # Create feature branch
################################################################################

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - Configurable via environment variables
REMOTE="${GIT_REMOTE:-origin}"
REPO_URL="${GIT_REMOTE_URL:-git@github.com:rogerboy38/rnd_warehouse_management.git}"
APP_VERSION="v8.1.0"
SCRIPT_VERSION="4.1.2"

# Auto-detect current branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

################################################################################
# Enhanced Functions
################################################################################

print_status() {
    echo -e "${BLUE}➤${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

show_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   App AMB W TDS Git Helper                    ║"
    echo "║                        Version $SCRIPT_VERSION                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Repository: https://github.com/rogerboy38/app_rnd_warehouse_management"
    echo "Authentication: SSH (git@github.com)"
    echo "Current Version: $APP_VERSION"
    echo "Current Branch: $BRANCH"
    echo "Remote: $REMOTE"
    echo "================================================================"
    echo ""
}

check_ssh_connection() {
    print_status "Testing SSH connection to GitHub..."
    
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        print_success "SSH connection to GitHub verified"
        return 0
    else
        print_warning "SSH connection test failed or inconclusive"
        print_status "This script is designed for SSH authentication."
        echo ""
        print_status "To set up SSH:"
        echo "  1. Generate SSH key: ssh-keygen -t ed25519 -C \"your_email@example.com\""
        echo "  2. Add to ssh-agent: ssh-add ~/.ssh/id_ed25519" 
        echo "  3. Add to GitHub: https://github.com/settings/keys"
        echo ""
        return 1
    fi
}

ensure_ssh_remote() {
    local remote_name="$1"
    local current_url=$(git remote get-url "$remote_name" 2>/dev/null || echo "")
    
    if [ -z "$current_url" ]; then
        print_status "Adding remote '$remote_name' with SSH URL..."
        git remote add "$remote_name" "$REPO_URL"
        print_success "Added remote '$remote_name' -> $REPO_URL"
    elif [[ "$current_url" == https://* ]]; then
        print_warning "Remote '$remote_name' is using HTTPS: $current_url"
        print_status "Converting to SSH for better security..."
        
        # Convert HTTPS URL to SSH URL
        local ssh_url=$(echo "$current_url" | sed 's|https://github.com/|git@github.com:|')
        git remote set-url "$remote_name" "$ssh_url"
        print_success "Converted remote '$remote_name' to SSH: $ssh_url"
    elif [[ "$current_url" == git@* ]]; then
        print_success "Remote '$remote_name' is using SSH: $current_url"
    else
        print_warning "Unknown URL format for remote '$remote_name': $current_url"
        print_status "Setting to default SSH URL..."
        git remote set-url "$remote_name" "$REPO_URL"
        print_success "Set remote '$remote_name' -> $REPO_URL"
    fi
}

check_requirements() {
    if [ ! -d ".git" ]; then
        print_error "Not a git repository"
        exit 1
    fi

    # Ensure remote uses SSH
    ensure_ssh_remote "$REMOTE"

    # Check for SSH key
    if [ ! -f ~/.ssh/id_rsa ] && [ ! -f ~/.ssh/id_ed25519 ] && [ ! -f ~/.ssh/id_ecdsa ]; then
        print_warning "No default SSH key found in ~/.ssh/"
        print_status "Make sure your SSH key is added to ssh-agent: ssh-add ~/.ssh/your_key"
    fi

    # Set git config if missing
    if ! git config user.name > /dev/null; then
        git config user.name "Git User"
        print_warning "Set default git user.name to 'Git User'"
    fi
    if ! git config user.email > /dev/null; then
        git config user.email "user@example.com"
        print_warning "Set default git user.email to 'user@example.com'"
    fi
}

validate_tag() {
    local tag="$1"
    if ! [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_warning "Tag '$tag' doesn't follow semantic versioning pattern (vX.Y.Z)"
        read -p "Continue anyway? (y/N): " confirm
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            print_error "Tag validation failed - operation cancelled"
            exit 1
        fi
    fi
}

run_pre_push_checks() {
    if [ -f ".git/hooks/pre-push" ] && [ -x ".git/hooks/pre-push" ]; then
        print_status "Running pre-push hooks..."
        if ! .git/hooks/pre-push; then
            print_error "Pre-push hooks failed"
            exit 1
        fi
        print_success "Pre-push checks passed"
    fi
}

load_config() {
    local config_file=".gitpushrc"
    if [ -f "$config_file" ]; then
        print_status "Loading configuration from $config_file..."
        source "$config_file"
        print_success "Configuration loaded"
    fi
}

auto_commit_message() {
    local changed_files=$(git status --porcelain | wc -l)
    local modified_files=$(git diff --name-only | head -5 | tr '\n' ',' | sed 's/,/, /g')
    
    if [ -n "$1" ]; then
        echo "$1"
    else
        if [ "$changed_files" -eq 1 ]; then
            echo "Update: ${modified_files%, }"
        elif [ "$changed_files" -le 5 ]; then
            echo "Update: ${modified_files%, }"
        else
            echo "Update: ${modified_files%, } and $((changed_files - 5)) other files"
        fi
    fi
}

backup_changes() {
    local backup_dir=".git_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # Copy modified and new files
    git status --porcelain | while IFS= read -r line; do
        file_status="${line:0:2}"
        file_path="${line:3}"
        
        if [ "$file_status" != "??" ] && [ -f "$file_path" ]; then
            cp --parents "$file_path" "$backup_dir/" 2>/dev/null || true
        fi
    done
    
    echo "$backup_dir"
}

rollback_on_error() {
    local backup_dir="$1"
    if [ -d "$backup_dir" ]; then
        print_error "Error detected! Rolling back changes from backup..."
        cp -r "$backup_dir"/* ./ 2>/dev/null || true
        rm -rf "$backup_dir"
        print_success "Rollback completed"
    fi
}

sync_with_remote() {
    print_status "Syncing with remote repository..."
    git fetch "$REMOTE"
    
    # Check if we need to pull
    LOCAL=$(git rev-parse @)
    REMOTE_REF=$(git rev-parse "$REMOTE/$BRANCH")
    BASE=$(git merge-base @ "$REMOTE/$BRANCH")

    if [ "$LOCAL" = "$REMOTE_REF" ]; then
        print_success "Already up-to-date with $REMOTE/$BRANCH"
    elif [ "$LOCAL" = "$BASE" ]; then
        print_status "Your branch is behind remote. Pulling changes..."
        git pull --rebase "$REMOTE" "$BRANCH"
        print_success "Successfully pulled latest changes"
    elif [ "$REMOTE_REF" = "$BASE" ]; then
        print_warning "Your branch is ahead of remote. You may need to push."
    else
        print_warning "Your branch and remote have diverged."
        print_status "Attempting to rebase..."
        git pull --rebase "$REMOTE" "$BRANCH"
    fi
}

show_changes_summary() {
    print_status "Changes to be committed:"
    echo "----------------------------------------"
    git status --short
    echo "----------------------------------------"
    
    local changed_files=$(git status --porcelain | wc -l)
    local modified=$(git status --porcelain | grep -E '^M' | wc -l)
    local added=$(git status --porcelain | grep -E '^A' | wc -l)
    local deleted=$(git status --porcelain | grep -E '^D' | wc -l)
    local untracked=$(git status --porcelain | grep -E '^\?\?' | wc -l)
    
    echo "Summary: $changed_files total changes"
    [ "$modified" -gt 0 ] && echo "  Modified: $modified"
    [ "$added" -gt 0 ] && echo "  Added: $added" 
    [ "$deleted" -gt 0 ] && echo "  Deleted: $deleted"
    [ "$untracked" -gt 0 ] && echo "  Untracked: $untracked"
    echo ""
}

dry_run() {
    print_status "🚀 DRY RUN MODE - No changes will be made"
    echo "================================================"
    
    # Show what would happen
    show_changes_summary
    
    local commit_msg=$(auto_commit_message "$1")
    print_status "Commit message that would be used:"
    echo "  \"$commit_msg\""
    
    if [ -n "$2" ]; then
        print_status "Tag that would be created: $2"
        validate_tag "$2"
    fi
    
    print_status "Would push to: $REMOTE/$BRANCH (via SSH)"
    
    # Show pre-push hooks that would run
    if [ -f ".git/hooks/pre-push" ]; then
        print_status "Pre-push hooks would be executed"
    fi
    
    echo ""
    print_warning "This was a dry run. Use --interactive or run without --dry-run to execute."
}

interactive_mode() {
    show_header
    
    print_status "🔍 Interactive Git Push Mode"
    echo "========================================"
    
    # Check requirements first (this will ensure SSH remote)
    check_requirements
    check_ssh_connection
    
    # Show current status
    print_status "Current repository status:"
    git status --short
    
    echo ""
    
    # Ask for commit message
    read -p "📝 Enter commit message (or press enter for auto-generated): " user_message
    COMMIT_MSG=$(auto_commit_message "$user_message")
    
    # Ask for tag
    read -p "🏷️  Enter tag name (optional, press enter to skip): " tag_name
    
    # Validate tag if provided
    if [ -n "$tag_name" ]; then
        validate_tag "$tag_name"
    fi
    
    # Show summary
    echo ""
    echo "📋 ACTION SUMMARY:"
    echo "----------------------------------------"
    echo "Commit: \"$COMMIT_MSG\""
    if [ -n "$tag_name" ]; then
        echo "Tag: $tag_name"
    else
        echo "Tag: (none)"
    fi
    echo "Remote: $REMOTE (SSH)"
    echo "Branch: $BRANCH"
    echo "----------------------------------------"
    
    # Confirm
    read -p "🚀 Proceed with these actions? (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo ""
        simple_push "$COMMIT_MSG" "$tag_name"
    else
        print_error "Operation cancelled by user"
        exit 0
    fi
}

create_feature_branch() {
    local branch_name="$1"
    
    if [ -z "$branch_name" ]; then
        read -p "Enter feature branch name: " branch_name
    fi
    
    if [ -z "$branch_name" ]; then
        print_error "Feature branch name cannot be empty"
        exit 1
    fi
    
    # Ensure we're on main and up to date
    git checkout "$BRANCH"
    sync_with_remote
    
    # Create feature branch
    local full_branch_name="feature/$branch_name"
    git checkout -b "$full_branch_name"
    print_success "Created and switched to feature branch: $full_branch_name"
    
    # Set upstream via SSH
    git push -u "$REMOTE" "$full_branch_name"
    print_success "Set upstream to $REMOTE/$full_branch_name (via SSH)"
    
    echo ""
    print_success "Feature branch '$full_branch_name' is ready for development!"
    print_status "You are now on branch: $full_branch_name"
}

simple_push() {
    local commit_msg="$1"
    local tag_name="$2"
    local backup_dir=""
    
    print_status "Starting Git push process..."
    
    # Load configuration
    load_config
    
    # Create backup
    backup_dir=$(backup_changes)
    
    # Set error trap for rollback
    trap 'rollback_on_error "$backup_dir"' ERR
    
    # Check requirements (this ensures SSH remote)
    check_requirements
    
    # Test SSH connection
    check_ssh_connection
    
    # Run pre-push checks
    run_pre_push_checks
    
    # Sync with remote first
    sync_with_remote
    
    # Show changes
    show_changes_summary
    
    # Stage all changes
    if [ -n "$(git status --porcelain)" ]; then
        git add .
        print_success "All changes staged"
        
        # Commit
        git commit -m "$commit_msg"
        print_success "Changes committed: $commit_msg"
    else
        print_status "No changes to commit"
    fi
    
    # Create tag if specified
    if [ -n "$tag_name" ]; then
        validate_tag "$tag_name"
        git tag -a "$tag_name" -m "Release $tag_name"
        print_success "Tag created: $tag_name"
    fi
    
    # Push everything via SSH
    print_status "Pushing to $REMOTE/$BRANCH (via SSH)..."
    git push "$REMOTE" "$BRANCH"
    
    # Push tag if created
    if [ -n "$tag_name" ]; then
        git push "$REMOTE" "$tag_name"
    fi
    
    # Cleanup backup
    if [ -d "$backup_dir" ]; then
        rm -rf "$backup_dir"
    fi
    
    # Remove error trap
    trap - ERR
    
    # Show summary
    echo ""
    print_success "🎉 Push completed successfully!"
    echo "----------------------------------------"
    print_success "Branch: $BRANCH"
    print_success "Commit: $(git log -1 --pretty=format:'%h') - $(git log -1 --pretty=format:'%s')"
    [ -n "$tag_name" ] && print_success "Tag: $tag_name"
    print_success "Remote: $REMOTE (SSH)"
    echo -e "View repo: ${BLUE}https://github.com/rogerboy38/app_rnd_warehouse_management${NC}"
    echo "----------------------------------------"
}

show_help() {
    show_header
    echo "Usage:"
    echo "  ./push_to_git_plus.sh                    # Auto-commit with smart message"
    echo "  ./push_to_git_plus.sh \"commit message\"   # Custom commit message" 
    echo "  ./push_to_git_plus.sh \"message\" v1.0.0   # Custom message with tag"
    echo "  ./push_to_git_plus.sh --interactive      # Interactive mode"
    echo "  ./push_to_git_plus.sh --dry-run          # Show what would happen"
    echo "  ./push_to_git_plus.sh --feature \"name\"   # Create feature branch"
    echo "  ./push_to_git_plus.sh --help             # Show this help"
    echo ""
    echo "Environment Variables:"
    echo "  GIT_REMOTE      - Set custom remote (default: origin)"
    echo "  GIT_REMOTE_URL  - Set custom remote URL"
    echo ""
    echo "SSH Configuration:"
    echo "  This script uses SSH authentication. Ensure your SSH key is:"
    echo "  1. Generated: ssh-keygen -t ed25519 -C \"your_email@example.com\""
    echo "  2. Added to ssh-agent: ssh-add ~/.ssh/id_ed25519"
    echo "  3. Added to GitHub: https://github.com/settings/keys"
    echo ""
    echo "Examples:"
    echo "  GIT_REMOTE=upstream ./push_to_git_plus.sh --interactive"
    echo "  ./push_to_git_plus.sh \"Add API layer for v6.0.0\" v6.0.0"
    echo "  ./push_to_git_plus.sh --feature \"api-integration\""
    echo "  ./push_to_git_plus.sh --dry-run \"Test commit message\" v1.2.3"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    local commit_msg=""
    local tag_name=""
    
    # Parse command line arguments
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --interactive|-i)
            interactive_mode
            exit 0
            ;;
        --dry-run|-d)
            dry_run "$2" "$3"
            exit 0
            ;;
        --feature|-f)
            create_feature_branch "$2"
            exit 0
            ;;
        --version|-v)
            show_header
            exit 0
            ;;
        *)
            # Generate commit message from first arg if provided
            commit_msg=$(auto_commit_message "$1")
            tag_name="$2"
            ;;
    esac
    
    show_header
    
    # Execute push
    simple_push "$commit_msg" "$tag_name"
}

# Run main function with all arguments
main "$@"
