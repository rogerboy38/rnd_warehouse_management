#!/bin/bash
# gitpush.sh - Generic Git push script for any Frappe app

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${BLUE}➤${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Get current directory info
APP_NAME=$(basename $(pwd))
REMOTE=$(git remote get-url origin 2>/dev/null | sed -n 's/.*github.com[:/]\([^/]*\)\/\([^.]*\).*/\1\/\2/p' || echo "unknown/unknown")

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                      Git Push Helper                          ║"
echo "║                        Version 1.0.0                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "App: $APP_NAME"
echo "Repository: https://github.com/$REMOTE"
echo "Current Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo "================================================================"

# Check SSH
print_status "Testing SSH connection..."
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    print_success "SSH connection verified"
else
    print_error "SSH connection failed"
    exit 1
fi

# Check if remote exists
if ! git remote get-url origin > /dev/null 2>&1; then
    print_error "No remote 'origin' found"
    echo "Set it with: git remote add origin git@github.com:rogerboy38/${APP_NAME}.git"
    exit 1
fi

# Add, commit, push
if [ -n "$(git status --porcelain)" ]; then
    print_status "Adding changes..."
    git add .
    
    COMMIT_MSG="${1:-Update: $(date '+%Y-%m-%d %H:%M:%S')}"
    print_status "Committing: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
    
    BRANCH=$(git branch --show-current)
    print_status "Pushing to origin/$BRANCH..."
    git push origin $BRANCH
    
    print_success "✅ Push completed!"
else
    print_status "No changes to commit"
fi
