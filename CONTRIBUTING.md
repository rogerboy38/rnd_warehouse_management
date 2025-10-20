# Contributing to RND Warehouse Management

We love your input! We want to make contributing to RND Warehouse Management as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## Pull Requests

Pull requests are the best way to propose changes to the codebase. We actively welcome your pull requests:

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Development Setup

### Prerequisites

- ERPNext development environment
- Python 3.8+
- Node.js 16+
- Git

### Local Development

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/rnd_warehouse_management.git
   cd rnd_warehouse_management
   ```

2. **Create Development Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Install in Development Mode**
   ```bash
   cd ~/frappe-bench
   bench get-app ~/path/to/rnd_warehouse_management
   bench --site development.localhost install-app rnd_warehouse_management
   bench start
   ```

4. **Enable Developer Mode**
   ```bash
   bench --site development.localhost set-config developer_mode 1
   bench --site development.localhost clear-cache
   ```

### Code Structure

```
rnd_warehouse_management/
├── rnd_warehouse_management/
│   ├── warehouse_management/     # Core business logic
│   │   ├── stock_entry.py        # Stock Entry customizations
│   │   ├── work_order.py         # Work Order enhancements
│   │   ├── warehouse.py          # Warehouse management
│   │   └── tasks.py              # Background tasks
│   ├── fixtures/                  # Installation data
│   ├── patches/                   # Migration scripts
│   ├── public/                    # Client-side assets
│   │   ├── js/                   # JavaScript files
│   │   └── css/                  # Stylesheets
│   └── templates/                 # Jinja templates
├── docs/                          # Documentation
├── tests/                         # Test files
└── README.md                      # Main documentation
```

## Testing

### Running Tests

```bash
# Run all tests
bench --site development.localhost run-tests --app rnd_warehouse_management

# Run specific test file
bench --site development.localhost run-tests --app rnd_warehouse_management --module rnd_warehouse_management.tests.test_stock_entry

# Run with coverage
bench --site development.localhost run-tests --app rnd_warehouse_management --coverage
```

### Writing Tests

Create test files in the `tests/` directory:

```python
# tests/test_stock_entry.py
import frappe
import unittest
from rnd_warehouse_management.warehouse_management.stock_entry import CustomStockEntry

class TestStockEntry(unittest.TestCase):
    def setUp(self):
        self.stock_entry = frappe.new_doc("Stock Entry")
        self.stock_entry.purpose = "Material Issue"
        self.stock_entry.custom_sap_movement_type = "261"
    
    def test_sap_movement_validation(self):
        """Test SAP movement type validation"""
        custom_se = CustomStockEntry(self.stock_entry.as_dict())
        # Add test logic here
        self.assertTrue(True)  # Replace with actual test
```

### Test Guidelines

- Write tests for all new functionality
- Test both positive and negative scenarios
- Include edge cases
- Use descriptive test names
- Keep tests isolated and independent

## Code Style

### Python Code Style

We follow PEP 8 with some modifications:

```python
# Good
def calculate_zone_status(doc):
    """Calculate zone status based on material availability."""
    if not doc.custom_work_order_reference:
        return
    
    completion = calculate_material_completeness(doc)
    if completion >= 100:
        doc.custom_zone_status = "Green Zone"
    else:
        doc.custom_zone_status = "Red Zone"

# Use descriptive variable names
warehouse_supervisor_signature = doc.custom_warehouse_supervisor_signature

# Add docstrings to all functions
def validate_sap_movement_type(doc):
    """Validate SAP Movement Type and set appropriate mappings.
    
    Args:
        doc: Stock Entry document
        
    Raises:
        frappe.ValidationError: If invalid movement type
    """
    pass
```

### JavaScript Code Style

```javascript
// Use consistent indentation (tabs)
frappe.ui.form.on('Stock Entry', {
	refresh: function(frm) {
		// Add custom buttons
		add_custom_buttons(frm);
		
		// Update displays
		update_zone_status_display(frm);
	}
});

// Use descriptive function names
function validate_signature_requirements(frm) {
	if (!frm.doc.custom_warehouse_supervisor_signature) {
		frappe.validated = false;
		frappe.msgprint({
			title: __('Missing Signature'),
			message: __('Warehouse Supervisor signature is required'),
			indicator: 'red'
		});
	}
}
```

### CSS Code Style

```css
/* Use BEM naming convention */
.warehouse-dashboard__zone-status {
    padding: 15px;
    border-radius: 5px;
}

.warehouse-dashboard__zone-status--red {
    background-color: #dc3545;
    color: white;
}

.warehouse-dashboard__zone-status--green {
    background-color: #28a745;
    color: white;
}

/* Group related styles */
.signature-field {
    border: 2px solid #ddd;
    border-radius: 5px;
    padding: 10px;
}

.signature-field--completed {
    border-color: #28a745;
    background-color: #f8fff9;
}
```

## Documentation

### Code Documentation

```python
def calculate_material_completeness(doc):
    """Calculate percentage of materials available for Work Order.
    
    This function checks BOM requirements against actual stock availability
    across all required warehouses. It returns a completion percentage
    that determines Red/Green zone status.
    
    Args:
        doc (Document): Stock Entry document with Work Order reference
        
    Returns:
        float: Completion percentage (0-100)
        
    Example:
        >>> doc = frappe.get_doc("Stock Entry", "SE-001")
        >>> completion = calculate_material_completeness(doc)
        >>> print(f"Completion: {completion}%")
        Completion: 85.5%
    """
    pass
```

### README Updates

When adding new features:

1. Update the main README.md
2. Add usage examples
3. Update the feature list
4. Include configuration instructions

### API Documentation

Document all public APIs:

```python
@frappe.whitelist()
def update_work_order_zone_status(work_order_name):
    """API endpoint to update Work Order zone status.
    
    This endpoint recalculates material availability and updates
    the zone status for the specified Work Order.
    
    Args:
        work_order_name (str): Name of the Work Order to update
        
    Returns:
        dict: Response with status, zone_status, completion_percentage
        
    Example:
        POST /api/method/rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status
        {
            "work_order_name": "WO-2024-001"
        }
        
        Response:
        {
            "status": "success",
            "zone_status": "Green Zone",
            "completion_percentage": 100.0,
            "last_updated": "2024-01-15 10:30:00"
        }
    """
    pass
```

## Commit Guidelines

### Commit Message Format

```
type(scope): subject

body

footer
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools

### Examples

```bash
# Good commit messages
git commit -m "feat(workflow): add dual signature validation"
git commit -m "fix(zone-status): correct material completion calculation"
git commit -m "docs(api): add endpoint documentation for zone status"
git commit -m "style(css): improve signature field styling"

# Bad commit messages
git commit -m "fixed bug"
git commit -m "update"
git commit -m "changes"
```

## Issue Guidelines

### Bug Reports

Create detailed bug reports with:

1. **Environment Details**:
   - ERPNext version
   - App version
   - Browser (if UI issue)
   - Operating system

2. **Steps to Reproduce**:
   - Clear, numbered steps
   - Expected vs actual behavior
   - Screenshots if applicable

3. **Error Logs**:
   - Console errors
   - Server logs
   - Network errors

### Feature Requests

1. **Use Case Description**:
   - Business need
   - Current workaround
   - Expected benefit

2. **Proposed Solution**:
   - Implementation ideas
   - UI mockups if applicable
   - API design if relevant

3. **Alternatives Considered**:
   - Other solutions evaluated
   - Why this approach is preferred

## Release Process

### Version Numbers

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Code Quality**:
   - [ ] All tests passing
   - [ ] Code review completed
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated

2. **Testing**:
   - [ ] Manual testing completed
   - [ ] Migration tested
   - [ ] Performance tested
   - [ ] Browser compatibility verified

3. **Documentation**:
   - [ ] API documentation updated
   - [ ] Usage guide updated
   - [ ] Installation guide verified
   - [ ] Examples working

4. **Release**:
   - [ ] Version number updated
   - [ ] Git tag created
   - [ ] GitHub release published
   - [ ] Community notified

## Community

### Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

### Getting Help

- **GitHub Discussions**: For questions and general discussion
- **GitHub Issues**: For bug reports and feature requests
- **Email**: support@minimax.com for private inquiries
- **ERPNext Forum**: Community support and discussions

### Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation
- Social media announcements

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Don't hesitate to reach out! We're here to help make your contribution experience as smooth as possible.

---

**Thank you for contributing to RND Warehouse Management! 🚀**