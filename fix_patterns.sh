#!/bin/bash
echo "=== Fixing SSH Pattern Matching ==="

# Backup original
cp git_manager_frappe.sh git_manager_frappe.sh.backup

# Update health check pattern
sed -i 's/grep -q -E "authenticated|Hi \${GITHUB_USER}"/grep -q -E "successfully authenticated|Hi \${GITHUB_USER}|authenticated successfully"/' git_manager_frappe.sh

# Update fix SSH pattern
sed -i 's/grep -q "authenticated"/grep -q -E "successfully authenticated|Hi \${GITHUB_USER}|authenticated"/' git_manager_frappe.sh

echo "✅ Patterns updated"
echo ""
echo "Testing health check..."
./git_manager_frappe.sh --health
