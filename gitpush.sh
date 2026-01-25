#!/bin/bash
# gitpush.sh - Enhanced Git push script for Frappe apps

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_status() { echo -e "${BLUE}➤${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_info() { echo -e "${CYAN}ℹ${NC} $1"; }

# Header
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Git Push Helper v2.0                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Get directory info
APP_NAME=$(basename $(pwd))
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "(detached HEAD)")
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

if [ -n "$REMOTE_URL" ]; then
    REPO_INFO=$(echo "$REMOTE_URL" | sed -n 's/.*github.com[:/]\([^/]*\)\/\([^.]*\).*/\1\/\2/p')
    [ -z "$REPO_INFO" ] && REPO_INFO="unknown/unknown"
else
    REPO_INFO="no remote"
fi

# Display info
echo "App: $APP_NAME"
echo "Remote: $([ -n "$REMOTE_URL" ] && echo "✓ $REPO_INFO" || echo "✗ Not set")"
echo "Branch: $CURRENT_BRANCH"
echo "User: $(git config user.name 2>/dev/null || echo "Not set")"
echo "================================================================"

# Function to setup git identity
setup_git_identity() {
    if [ -z "$(git config user.email 2>/dev/null)" ] || [ -z "$(git config user.name 2>/dev/null)" ]; then
        print_warning "Git identity not configured"
        echo "Please set your git identity:"
        echo "  git config user.email \"your-email@example.com\""
        echo "  git config user.name \"Your Name\""
        exit 1
    fi
}

# Check SSH connection
check_ssh() {
    print_status "Testing SSH connection..."
    if ssh -o ConnectTimeout=5 -T git@github.com 2>&1 | grep -qi "successfully\|authenticated"; then
        print_success "SSH connection verified"
        return 0
    else
        print_error "SSH connection failed"
        print_info "Run: ssh-keygen -t ed25519 -C \"your-email@example.com\""
        print_info "Add key to GitHub: https://github.com/settings/keys"
        exit 1
    fi
}

# Check remote setup
check_remote() {
    if [ -z "$REMOTE_URL" ]; then
        print_error "No remote 'origin' configured"
        print_info "Set it with: git remote add origin git@github.com:YOUR_USERNAME/${APP_NAME}.git"
        print_info "First create the repository on GitHub"
        exit 1
    fi
}

# Check branch status
check_branch() {
    if [ "$CURRENT_BRANCH" = "(detached HEAD)" ]; then
        print_warning "You are in detached HEAD state"
        print_info "To fix: git checkout -b main"
        print_info "Or: git checkout main"
        exit 1
    fi
}

# Main flow
setup_git_identity
check_ssh
check_remote
check_branch

# Check for changes
if [ -n "$(git status --porcelain)" ]; then
    print_status "Adding changes..."
    git add .
    
    # Commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        echo -n "Enter commit message (or press Enter for default): "
        read USER_MSG
        if [ -n "$USER_MSG" ]; then
            COMMIT_MSG="$USER_MSG"
        else
            COMMIT_MSG="Update: $(date '+%Y-%m-%d %H:%M:%S')"
        fi
    fi
    
    print_status "Committing: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
    
    # Push
    print_status "Pushing to origin/$CURRENT_BRANCH..."
    if git push origin "$CURRENT_BRANCH"; then
        print_success "✅ Push completed successfully!"
        echo -e "${GREEN}"
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                      Push Successful!                         ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
        echo "View at: https://github.com/$REPO_INFO"
    else
        print_error "Push failed"
        print_info "If branch doesn't exist remotely, use: git push -u origin $CURRENT_BRANCH"
        exit 1
    fi
else
    print_status "No changes to commit"
fi

# Show status
echo ""
print_status "Final status:"
git status --short
echo ""
print_info "Branch: $CURRENT_BRANCH"
print_info "Remote: $REMOTE_URL"
