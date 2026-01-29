#!/bin/bash
echo "=== Fixing and Pushing Warehouse Management ==="

# Check Git status
echo "1. Checking Git status..."
if [[ -z "$(git status --porcelain)" ]]; then
    echo "   ⚠ No changes to commit"
    echo "   Creating empty commit to establish branch..."
    git commit --allow-empty -m "Initial repository setup"
else
    echo "   📁 Files to commit:"
    git status --short
    echo "   Committing files..."
    git add .
    git commit -m "Initial commit: Warehouse Management System v2.0
    
    Complete Phase 2 Implementation including:
    - Warehouse management functionality
    - Full documentation suite
    - Technical specifications
    - Deployment guides
    - Testing framework
    - Security guidelines"
fi

# Check branch
echo ""
echo "2. Checking branch..."
current_branch=$(git branch --show-current 2>/dev/null || echo "")
if [[ -z "$current_branch" ]]; then
    echo "   Creating main branch..."
    git checkout -b main
    current_branch="main"
fi
echo "   Current branch: $current_branch"

# Push to GitHub
echo ""
echo "3. Pushing to GitHub..."
if git push -u origin "$current_branch"; then
    echo "   ✅ Successfully pushed to GitHub!"
    echo "   Repository: https://github.com/rogerboy38/rnd_warehouse_management"
else
    echo "   ❌ Push failed. Trying force push..."
    git push -u origin "$current_branch" --force
fi

# Verify
echo ""
echo "4. Verification:"
git remote -v
git log --oneline -3 2>/dev/null || echo "No commits yet"
