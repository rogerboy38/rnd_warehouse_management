# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of RND Warehouse Management seriously. If you discover a security vulnerability, please follow these steps:

### 🔒 Private Disclosure

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues privately by emailing:

📧 **security@minimax.com**

### What to Include

Please include the following information in your report:

1. **Description**: A clear description of the vulnerability
2. **Impact**: Potential impact and severity assessment
3. **Steps to Reproduce**: Detailed steps to reproduce the vulnerability
4. **Proof of Concept**: Code or screenshots demonstrating the issue (if possible)
5. **Suggested Fix**: Any recommendations for remediation (optional)
6. **Your Contact**: How we can reach you for follow-up questions

### Response Timeline

- **Initial Response**: Within 48 hours
- **Assessment**: Within 1 week
- **Fix Timeline**: Based on severity
  - Critical: 7 days
  - High: 14 days
  - Medium: 30 days
  - Low: 60 days

### Security Update Process

1. **Acknowledgment**: We will acknowledge receipt of your vulnerability report
2. **Investigation**: Our team will investigate and verify the issue
3. **Fix Development**: We will develop and test a fix
4. **Disclosure**: We will coordinate public disclosure with you
5. **Credit**: We will credit you in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices

### For Users

#### Installation Security
```bash
# Always verify the source
git clone https://github.com/minimax/rnd_warehouse_management.git

# Check signatures (when available)
git verify-commit HEAD

# Use specific versions in production
bench get-app rnd_warehouse_management --branch v1.0.0
```

#### Configuration Security

1. **Restrict Permissions**
   - Assign roles based on principle of least privilege
   - Regular audit of role assignments
   - Remove unused user accounts

2. **Secure API Access**
   ```python
   # In site_config.json
   {
       "enable_cors": false,
       "use_ssl": true,
       "session_expiry": "06:00:00"
   }
   ```

3. **Signature Validation**
   - Enable signature verification
   - Use strong signature capture
   - Audit signature logs regularly

4. **Database Security**
   - Use strong database passwords
   - Limit database user permissions
   - Enable SSL for database connections
   - Regular backups with encryption

#### Network Security

1. **HTTPS Only**
   ```nginx
   # Force HTTPS
   server {
       listen 80;
       return 301 https://$server_name$request_uri;
   }
   ```

2. **API Rate Limiting**
   ```python
   # Custom rate limiting
   frappe.conf.rate_limit = {
       "window": 60,
       "limit": 100
   }
   ```

3. **Firewall Rules**
   - Restrict access to database ports
   - Limit API access to trusted IPs
   - Use VPN for administrative access

### For Developers

#### Code Security

1. **Input Validation**
   ```python
   import frappe
   from frappe.utils import validate_email_address, sanitize_html
   
   @frappe.whitelist()
   def secure_function(email, content):
       # Always validate and sanitize inputs
       validate_email_address(email)
       content = sanitize_html(content)
       # Process safely...
   ```

2. **SQL Injection Prevention**
   ```python
   # GOOD - Use parameterized queries
   frappe.db.sql("""
       SELECT * FROM `tabItem` 
       WHERE item_code = %s
   """, (item_code,))
   
   # BAD - Never use string formatting
   # frappe.db.sql(f"SELECT * FROM `tabItem` WHERE item_code = '{item_code}'")
   ```

3. **Permission Checks**
   ```python
   @frappe.whitelist()
   def update_warehouse(warehouse_name, data):
       # Always check permissions
       if not frappe.has_permission("Warehouse", "write"):
           frappe.throw(_("Insufficient permissions"))
       
       # Verify document access
       doc = frappe.get_doc("Warehouse", warehouse_name)
       if not doc.has_permission("write"):
           frappe.throw(_("No permission to modify this warehouse"))
   ```

4. **Signature Security**
   ```python
   # Validate signature integrity
   def validate_signature(doc):
       if doc.custom_warehouse_supervisor_signature:
           # Verify timestamp
           if not doc.custom_warehouse_signature_timestamp:
               frappe.throw(_("Invalid signature - missing timestamp"))
           
           # Verify user
           if not frappe.has_permission("Stock Entry", ptype="approve"):
               frappe.throw(_("Invalid signature - insufficient permissions"))
   ```

#### Dependency Management

```bash
# Regularly update dependencies
bench update --patch

# Audit dependencies
pip-audit

# Check for vulnerabilities
npm audit
```

#### Secrets Management

```python
# NEVER commit secrets
# Use environment variables or site_config.json

import frappe
from frappe.utils.password import get_decrypted_password

# Store sensitive data encrypted
api_key = get_decrypted_password("Integration", "API Service", "api_key")
```

## Known Security Considerations

### Signature Storage
- Signatures are stored as base64-encoded images
- Stored in database text fields
- **Recommendation**: Consider encryption at rest for sensitive deployments

### API Endpoints
- All utility functions are whitelisted for API access
- Rate limiting should be configured at nginx/proxy level
- **Recommendation**: Implement API key authentication for production

### Workflow Bypass
- Role-based permissions prevent workflow bypass
- Direct SQL operations could bypass validation
- **Recommendation**: Regular permission audits

## Security Checklist for Deployment

### Pre-Deployment

- [ ] Review all custom configurations
- [ ] Audit user roles and permissions
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall rules
- [ ] Set up database backups with encryption
- [ ] Review API access controls
- [ ] Test authentication mechanisms
- [ ] Enable audit logging
- [ ] Configure rate limiting
- [ ] Review error handling (no sensitive data in error messages)

### Post-Deployment

- [ ] Monitor logs for suspicious activity
- [ ] Regular security audits
- [ ] Keep system updated
- [ ] Test backup restoration
- [ ] Review access logs
- [ ] Penetration testing (recommended)

## Compliance

### Data Protection

- **GDPR**: User data handling and right to erasure
- **SOC 2**: Audit logging and access controls
- **ISO 27001**: Information security management

### Audit Logging

The app logs critical security events:
- Signature captures with timestamps
- Zone status changes
- Approval workflow transitions
- Material assessment calculations
- Permission violations

```python
# Example audit log
frappe.log_error(
    title="Security Event",
    message=f"Unauthorized access attempt by {user} to {resource}"
)
```

## Security Contact

For security concerns, contact:

- **Email**: security@minimax.com
- **PGP Key**: [Available upon request]
- **Response Time**: Within 48 hours

## Hall of Fame

We acknowledge security researchers who responsibly disclose vulnerabilities:

*No vulnerabilities reported yet.*

---

**Last Updated**: 2025-01-20
**Next Review**: 2025-04-20
