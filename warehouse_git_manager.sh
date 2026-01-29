#!/bin/bash
echo "=== Warehouse Management Git Manager ==="
echo "App: rnd_warehouse_management"
echo "Repo: git@github.com:rogerboy38/rnd_warehouse_management.git"
echo ""
echo "Current status:"
git status --short
echo ""
echo "Branch: $(git branch --show-current)"
echo "Remote: $(git remote get-url origin)"
echo ""
echo "Ready for development! 🚀"
