# Contributing to FuzzForge 🤝

Thank you for your interest in contributing to FuzzForge! We welcome contributions from the community and are excited to collaborate with you.

## 🌟 Ways to Contribute

- 🐛 **Bug Reports** - Help us identify and fix issues
- 💡 **Feature Requests** - Suggest new capabilities and improvements
- 🔧 **Code Contributions** - Submit bug fixes, features, and enhancements
- 📚 **Documentation** - Improve guides, tutorials, and API documentation
- 🧪 **Testing** - Help test new features and report issues
- 🛡️ **Security Workflows** - Contribute new security analysis workflows

## 📋 Contribution Guidelines

### Code Style

- Follow [PEP 8](https://pep8.org/) for Python code
- Use type hints where applicable
- Write clear, descriptive commit messages
- Include docstrings for all public functions and classes
- Add tests for new functionality

### Commit Message Format

We use conventional commits for clear history:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code formatting (no logic changes)
- `refactor:` Code restructuring without changing functionality
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

**Examples:**
```
feat(workflows): add new static analysis workflow for Go
fix(api): resolve authentication timeout issue
docs(readme): update installation instructions
```

### Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Make Your Changes**
   - Write clean, well-documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   # Test workflows
   cd test_projects/vulnerable_app/
   ff workflow security_assessment .
   ```

4. **Submit Pull Request**
   - Use a clear, descriptive title
   - Provide detailed description of changes
   - Link related issues using `Fixes #123` or `Closes #123`
   - Ensure all CI checks pass

## 🛡️ Security Workflow Development

### Creating New Workflows

1. **Workflow Structure**
   ```
   backend/toolbox/workflows/your_workflow/
   ├── __init__.py
   ├── workflow.py          # Main Temporal workflow
   ├── activities.py        # Workflow activities (optional)
   ├── metadata.yaml        # Workflow metadata (includes vertical field)
   └── requirements.txt     # Additional dependencies (optional)
   ```

2. **Register Your Workflow**
   Add your workflow to `backend/toolbox/workflows/registry.py`:
   ```python
   # Import your workflow
   from .your_workflow.workflow import main_flow as your_workflow_flow

   # Add to registry
   WORKFLOW_REGISTRY["your_workflow"] = {
       "flow": your_workflow_flow,
       "module_path": "toolbox.workflows.your_workflow.workflow",
       "function_name": "main_flow",
       "description": "Description of your workflow",
       "version": "1.0.0",
       "author": "Your Name",
       "tags": ["tag1", "tag2"]
   }
   ```

3. **Testing Workflows**
   - Create test cases in `test_projects/vulnerable_app/`
   - Ensure SARIF output format compliance
   - Test with various input scenarios

### Security Guidelines

- 🔐 Never commit secrets, API keys, or credentials
- 🛡️ Focus on **defensive security** tools and analysis
- ⚠️ Do not create tools for malicious purposes
- 🧪 Test workflows thoroughly before submission
- 📋 Follow responsible disclosure for security issues

## 🐛 Bug Reports

When reporting bugs, please include:

- **Environment**: OS, Python version, Docker version
- **Steps to Reproduce**: Clear steps to recreate the issue
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Logs**: Relevant error messages and stack traces
- **Screenshots**: If applicable

Use our [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md).

## 💡 Feature Requests

For new features, please provide:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Implementation**: Technical considerations (optional)

Use our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md).

## 📚 Documentation

Help improve our documentation:

- **API Documentation**: Update docstrings and type hints
- **User Guides**: Create tutorials and how-to guides
- **Workflow Documentation**: Document new security workflows
- **Examples**: Add practical usage examples

## 🙏 Recognition

Contributors will be:

- Listed in our [Contributors](CONTRIBUTORS.md) file
- Mentioned in release notes for significant contributions
- Invited to join our Discord community
- Eligible for FuzzingLabs Academy courses and swag

## 📜 License

By contributing to FuzzForge, you agree that your contributions will be licensed under the same [Business Source License 1.1](LICENSE) as the project.

---

**Thank you for making FuzzForge better! 🚀**

Every contribution, no matter how small, helps build a stronger security community.
