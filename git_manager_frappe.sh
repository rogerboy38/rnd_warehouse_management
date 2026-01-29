#!/bin/bash
# git_manager_frappe.sh - Optimized for Warehouse Management on Frappe Cloud

set -euo pipefail

# Configuration
APP_NAME="rnd_warehouse_management"
GITHUB_USER="rogerboy38"
REPO_NAME="rnd_warehouse_management"
REPO_URL="git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
SCRIPT_VERSION="1.0.0"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}➤${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

show_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║     Warehouse Management Git Manager (Frappe Cloud)  ║"
    echo "║                     Version: $SCRIPT_VERSION               ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "App: $APP_NAME"
    echo "Repo: $REPO_URL"
    echo "════════════════════════════════════════════════════════"
}

frappe_health_check() {
    log_info "Frappe Cloud Health Check"
    
    # SSH Check
    if ssh -T git@github.com 2>&1 | grep -q -E "authenticated|Hi ${GITHUB_USER}"; then
        log_success "SSH connection verified"
    else
        log_warning "SSH connection issues"
        return 1
    fi
    
    # Git Check
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Not a git repository"
        return 1
    fi
    log_success "Git repository OK"
    
    # Remote Check
    if ! git remote get-url origin > /dev/null 2>&1; then
        log_error "No remote origin configured"
        return 1
    fi
    log_success "Git remote OK"
    
    # Branch Check
    local branch=$(git branch --show-current)
    if [[ -n "$branch" ]]; then
        log_success "On branch: $branch"
    else
        log_warning "Detached HEAD (common after bench rebuild)"
    fi
    
    log_success "✅ All systems normal"
    return 0
}

frappe_git_sync() {
    log_info "Git Sync"
    
    # Check for changes
    if [[ -z "$(git status --porcelain)" ]]; then
        log_info "No changes to commit"
        return 0
    fi
    
    # Show changes
    log_info "Changes detected:"
    git status --short
    
    # Stage and commit
    git add .
    git commit -m "Update: $(date '+%Y-%m-%d %H:%M:%S') - Frappe Cloud"
    
    # Push
    local branch=$(git branch --show-current)
    log_info "Pushing to origin/$branch..."
    if git push origin "$branch"; then
        log_success "✅ Successfully pushed to GitHub"
    else
        log_error "Push failed"
        return 1
    fi
}

frappe_fix_ssh() {
    log_info "Fixing SSH for Frappe Cloud"
    
    # Generate key if missing
    if [[ ! -f ~/.ssh/id_ed25519 ]]; then
        log_info "Generating SSH key..."
        mkdir -p ~/.ssh
        ssh-keygen -t ed25519 -C "${GITHUB_USER}@github" -f ~/.ssh/id_ed25519 -N "" -q
        chmod 600 ~/.ssh/id_ed25519
        log_success "SSH key generated"
        
        echo ""
        echo "=== ADD THIS KEY TO GITHUB ==="
        cat ~/.ssh/id_ed25519.pub
        echo "=== END ==="
        echo ""
        echo "Go to: https://github.com/settings/keys"
        echo "Add this key, then press Enter..."
        read -r
    fi
    
    # Test
    if ssh -T git@github.com 2>&1 | grep -q "authenticated"; then
        log_success "SSH is working"
    else
        log_error "SSH still not working"
    fi
}

show_menu() {
    while true; do
        clear
        show_banner
        
        echo "1) 🔍 Health Check"
        echo "2) ⚡ Quick Sync"
        echo "3) 🛠️  Fix SSH"
        echo "4) 📊 Status"
        echo "5) 🚪 Exit"
        echo "════════════════════════════════════════════════════════"
        
        read -r -p "Choice [1-5]: " choice
        
        case $choice in
            1) frappe_health_check ;;
            2) frappe_git_sync ;;
            3) frappe_fix_ssh ;;
            4) 
                echo "=== STATUS ==="
                git status
                echo ""
                echo "=== BRANCHES ==="
                git branch -a
                ;;
            5) exit 0 ;;
            *) echo "Invalid option" ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Main
case "${1:-}" in
    "--health"|"-h") frappe_health_check ;;
    "--sync"|"-s") frappe_git_sync ;;
    "--fix"|"-f") frappe_fix_ssh ;;
    "--menu"|"-m"|"") show_menu ;;
    "--help")
        echo "Usage: $0 [OPTION]"
        echo "Options:"
        echo "  --health, -h    Health check"
        echo "  --sync, -s      Sync changes"
        echo "  --fix, -f       Fix SSH"
        echo "  --menu, -m      Interactive menu (default)"
        ;;
    *) echo "Unknown option: $1" ;;
esac
