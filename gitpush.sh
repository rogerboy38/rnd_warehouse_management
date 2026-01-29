#!/bin/bash
# gitpush.sh - Updated for Frappe Cloud environments

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}➤${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }

# Check SSH
print_status "Testing SSH..."
if ssh -T git@github.com 2>&1 | grep -q "authenticated"; then
    print_success "SSH connection verified"
else
    echo "SSH not configured. Run:"
    echo "ssh-keygen -t ed25519 -C 'rogerboy38@github' -f ~/.ssh/id_ed25519 -N '' -q"
    echo "Add key to: https://github.com/settings/keys"
    exit 1
fi

# Git operations
print_status "Adding changes..."
git add .

print_status "Committing..."
git commit -m "Update: $(date '+%Y-%m-%d %H:%M:%S')" || \
git commit --allow-empty -m "Empty commit to trigger sync"

print_status "Pushing to GitHub..."
git push origin main

print_success "✅ Repository updated successfully!"
