# Contributing to FuzzForge OSS

Thank you for your interest in contributing to FuzzForge OSS! We welcome contributions from the community and are excited to collaborate with you.

**Our Vision**: FuzzForge aims to be a **universal platform for security research** across all cybersecurity domains. Through our modular architecture, any security tool—from fuzzing engines to cloud scanners, from mobile app analyzers to IoT security tools—can be integrated as a containerized module and controlled via AI agents.

## Ways to Contribute

- **Security Modules** - Create modules for any cybersecurity domain (AppSec, NetSec, Cloud, IoT, etc.)
- **Bug Reports** - Help us identify and fix issues
- **Feature Requests** - Suggest new capabilities and improvements
- **Core Features** - Contribute to the MCP server, runner, or CLI
- **Documentation** - Improve guides, tutorials, and module documentation
- **Testing** - Help test new features and report issues
- **AI Integration** - Improve MCP tools and AI agent interactions
- **Tool Integrations** - Wrap existing security tools as FuzzForge modules

## Contribution Guidelines

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
feat(modules): add cloud security scanner module
fix(mcp): resolve module listing timeout
docs(sdk): update module development guide
test(runner): add container execution tests
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
   # Test modules
   FUZZFORGE_MODULES_PATH=./fuzzforge-modules uv run fuzzforge modules list
   
   # Run a module
   uv run fuzzforge modules run your-module --assets ./test-assets
   
   # Test MCP integration (if applicable)
   uv run fuzzforge mcp status
   ```

4. **Submit Pull Request**
   - Use a clear, descriptive title
   - Provide detailed description of changes
   - Link related issues using `Fixes #123` or `Closes #123`
   - Ensure all CI checks pass

## Module Development

FuzzForge uses a modular architecture where security tools run as isolated containers. The `fuzzforge-modules-sdk` provides everything you need to create new modules.

**Documentation:**
- [Module SDK Documentation](fuzzforge-modules/fuzzforge-modules-sdk/README.md) - Complete SDK reference
- [Module Template](fuzzforge-modules/fuzzforge-module-template/) - Starting point for new modules
- [USAGE Guide](USAGE.md) - Setup and installation instructions

### Creating a New Module

1. **Use the Module Template**
   ```bash
   # Generate a new module from template
   cd fuzzforge-modules/
   cp -r fuzzforge-module-template my-new-module
   cd my-new-module
   ```

2. **Module Structure**
   ```
   my-new-module/
   ├── Dockerfile              # Container definition
   ├── Makefile                # Build commands
   ├── README.md               # Module documentation
   ├── pyproject.toml          # Python dependencies
   ├── mypy.ini                # Type checking config
   ├── ruff.toml               # Linting config
   └── src/
       └── module/
           ├── __init__.py
           ├── __main__.py     # Entry point
           ├── mod.py          # Main module logic
           ├── models.py       # Pydantic models
           └── settings.py     # Configuration
   ```

3. **Implement Your Module**
   
   Edit `src/module/mod.py`:
   ```python
   from fuzzforge_modules_sdk.api.modules import BaseModule
   from fuzzforge_modules_sdk.api.models import ModuleResult
   from .models import MyModuleConfig, MyModuleOutput
   
   class MyModule(BaseModule[MyModuleConfig, MyModuleOutput]):
       """Your module description."""
       
       def execute(self) -> ModuleResult[MyModuleOutput]:
           """Main execution logic."""
           # Access input assets
           assets = self.input_path
           
           # Your security tool logic here
           results = self.run_analysis(assets)
           
           # Return structured results
           return ModuleResult(
               success=True,
               output=MyModuleOutput(
                   findings=results,
                   summary="Analysis complete"
               )
           )
   ```

4. **Define Configuration Models**
   
   Edit `src/module/models.py`:
   ```python
   from pydantic import BaseModel, Field
   from fuzzforge_modules_sdk.api.models import BaseModuleConfig, BaseModuleOutput
   
   class MyModuleConfig(BaseModuleConfig):
       """Configuration for your module."""
       timeout: int = Field(default=300, description="Timeout in seconds")
       max_iterations: int = Field(default=1000, description="Max iterations")
   
   class MyModuleOutput(BaseModuleOutput):
       """Output from your module."""
       findings: list[dict] = Field(default_factory=list)
       coverage: float = Field(default=0.0)
   ```

5. **Build Your Module**
   ```bash
   # Build the SDK first (if not already done)
   cd ../fuzzforge-modules-sdk
   uv build
   mkdir -p .wheels
   cp ../../dist/fuzzforge_modules_sdk-*.whl .wheels/
   cd ../..
   docker build -t localhost/fuzzforge-modules-sdk:0.1.0 fuzzforge-modules/fuzzforge-modules-sdk/
   
   # Build your module
   cd fuzzforge-modules/my-new-module
   docker build -t fuzzforge-my-new-module:0.1.0 .
   ```

6. **Test Your Module**
   ```bash
   # Run with test assets
   uv run fuzzforge modules run my-new-module --assets ./test-assets
   
   # Check module info
   uv run fuzzforge modules info my-new-module
   ```

### Module Development Guidelines

**Important Conventions:**
- **Input/Output**: Use `/fuzzforge/input` for assets and `/fuzzforge/output` for results
- **Configuration**: Support JSON configuration via stdin or file
- **Logging**: Use structured logging (structlog is pre-configured)
- **Error Handling**: Return proper exit codes and error messages
- **Security**: Run as non-root user when possible
- **Documentation**: Include clear README with usage examples
- **Dependencies**: Minimize container size, use multi-stage builds

**See also:**
- [Module SDK API Reference](fuzzforge-modules/fuzzforge-modules-sdk/src/fuzzforge_modules_sdk/api/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

### Module Types

FuzzForge is designed to support modules across **all cybersecurity domains**. The modular architecture allows any security tool to be containerized and integrated. Here are the main categories:

**Application Security**
- Fuzzing engines (coverage-guided, grammar-based, mutation-based)
- Static analysis (SAST, code quality, dependency scanning)
- Dynamic analysis (DAST, runtime analysis, instrumentation)
- Test validation and coverage analysis
- Crash analysis and exploit detection

**Network & Infrastructure Security**
- Network scanning and service enumeration
- Protocol analysis and fuzzing
- Firewall and configuration testing
- Cloud security (AWS/Azure/GCP misconfiguration detection, IAM analysis)
- Container security (image scanning, Kubernetes security)

**Web & API Security**
- Web vulnerability scanners (XSS, SQL injection, CSRF)
- Authentication and session testing
- API security (REST/GraphQL/gRPC testing, fuzzing)
- SSL/TLS analysis

**Binary & Reverse Engineering**
- Binary analysis and disassembly
- Malware sandboxing and behavior analysis
- Exploit development tools
- Firmware extraction and analysis

**Mobile & IoT Security**
- Mobile app analysis (Android/iOS static/dynamic analysis)
- IoT device security and firmware analysis
- SCADA/ICS and industrial protocol testing
- Automotive security (CAN bus, ECU testing)

**Data & Compliance**
- Database security testing
- Encryption and cryptography analysis
- Secrets and credential detection
- Privacy tools (PII detection, GDPR compliance)
- Compliance checkers (PCI-DSS, HIPAA, SOC2, ISO27001)

**Threat Intelligence & Risk**
- OSINT and reconnaissance tools
- Threat hunting and IOC correlation
- Risk assessment and attack surface mapping
- Security audit and policy validation

**Emerging Technologies**
- AI/ML security (model poisoning, adversarial testing)
- Blockchain and smart contract analysis
- Quantum-safe cryptography testing

**Custom & Integration**
- Domain-specific security tools
- Bridges to existing security tools
- Multi-tool orchestration and result aggregation

### Example: Simple Security Scanner Module

```python
# src/module/mod.py
from pathlib import Path
from fuzzforge_modules_sdk.api.modules import BaseModule
from fuzzforge_modules_sdk.api.models import ModuleResult
from .models import ScannerConfig, ScannerOutput

class SecurityScanner(BaseModule[ScannerConfig, ScannerOutput]):
    """Scans for common security issues in code."""
    
    def execute(self) -> ModuleResult[ScannerOutput]:
        findings = []
        
        # Scan all source files
        for file_path in self.input_path.rglob("*"):
            if file_path.is_file():
                findings.extend(self.scan_file(file_path))
        
        return ModuleResult(
            success=True,
            output=ScannerOutput(
                findings=findings,
                files_scanned=len(list(self.input_path.rglob("*")))
            )
        )
    
    def scan_file(self, path: Path) -> list[dict]:
        """Scan a single file for security issues."""
        # Your scanning logic here
        return []
```

### Testing Modules

Create tests in `tests/`:
```python
import pytest
from module.mod import MyModule
from module.models import MyModuleConfig

def test_module_execution():
    config = MyModuleConfig(timeout=60)
    module = MyModule(config=config, input_path=Path("test_assets"))
    result = module.execute()
    
    assert result.success
    assert len(result.output.findings) >= 0
```

Run tests:
```bash
uv run pytest
```

### Security Guidelines

**Critical Requirements:**
- Never commit secrets, API keys, or credentials
- Focus on **defensive security** tools and analysis
- Do not create tools for malicious purposes
- Test modules thoroughly before submission
- Follow responsible disclosure for security issues
- Use minimal, secure base images for containers
- Avoid running containers as root when possible

**Security Resources:**
- [OWASP Container Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [CIS Docker Benchmarks](https://www.cisecurity.org/benchmark/docker)

## Contributing to Core Features

Beyond modules, you can contribute to FuzzForge's core components.

**Useful Resources:**
- [Project Structure](README.md) - Overview of the codebase
- [USAGE Guide](USAGE.md) - Installation and setup
- Python best practices: [PEP 8](https://pep8.org/)

### Core Components

- **fuzzforge-mcp** - MCP server for AI agent integration
- **fuzzforge-runner** - Module execution engine
- **fuzzforge-cli** - Command-line interface
- **fuzzforge-common** - Shared utilities and sandbox engines
- **fuzzforge-types** - Type definitions and schemas

### Development Setup

1. **Clone and Install**
   ```bash
   git clone https://github.com/FuzzingLabs/fuzzforge-oss.git
   cd fuzzforge-oss
   uv sync --all-extras
   ```

2. **Run Tests**
   ```bash
   # Run all tests
   make test
   
   # Run specific package tests
   cd fuzzforge-mcp
   uv run pytest
   ```

3. **Type Checking**
   ```bash
   # Type check all packages
   make typecheck
   
   # Type check specific package
   cd fuzzforge-runner
   uv run mypy .
   ```

4. **Linting and Formatting**
   ```bash
   # Format code
   make format
   
   # Lint code
   make lint
   ```

## Bug Reports

When reporting bugs, please include:

- **Environment**: OS, Python version, Docker version, uv version
- **FuzzForge Version**: Output of `uv run fuzzforge --version`
- **Module**: Which module or component is affected
- **Steps to Reproduce**: Clear steps to recreate the issue
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Logs**: Relevant error messages and stack traces
- **Container Logs**: For module issues, include Docker/Podman logs
- **Screenshots**: If applicable

**Example:**
```markdown
**Environment:**
- OS: Ubuntu 22.04
- Python: 3.14.2
- Docker: 24.0.7
- uv: 0.5.13

**Module:** my-custom-scanner

**Steps to Reproduce:**
1. Run `uv run fuzzforge modules run my-scanner --assets ./test-target`
2. Module fails with timeout error

**Expected:** Module completes analysis
**Actual:** Times out after 30 seconds

**Logs:**
```
ERROR: Module execution timeout
...
```
```

## Feature Requests

For new features, please provide:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Implementation**: Technical considerations (optional)
- **Module vs Core**: Should this be a module or core feature?

**Example Feature Requests:**
- New module for cloud security posture management (CSPM)
- Module for analyzing smart contract vulnerabilities
- MCP tool for orchestrating multi-module workflows
- CLI command for batch module execution across multiple targets
- Support for distributed fuzzing campaigns
- Integration with CI/CD pipelines
- Module marketplace/registry features

## Documentation

Help improve our documentation:

- **Module Documentation**: Document your modules in their README.md
- **API Documentation**: Update docstrings and type hints
- **User Guides**: Improve USAGE.md and tutorial content
- **Module SDK Guides**: Help document the SDK for module developers
- **MCP Integration**: Document AI agent integration patterns
- **Examples**: Add practical usage examples and workflows

### Documentation Standards

- Use clear, concise language
- Include code examples
- Add command-line examples with expected output
- Document all configuration options
- Explain error messages and troubleshooting

### Module README Template

```markdown
# Module Name

Brief description of what this module does.

## Features

- Feature 1
- Feature 2

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| timeout   | int  | 300     | Timeout in seconds |

## Usage

\`\`\`bash
uv run fuzzforge modules run module-name --assets ./path/to/assets
\`\`\`

## Output

Describes the output structure and format.

## Examples

Practical usage examples.
```

## Recognition

Contributors will be:

- Listed in our [Contributors](CONTRIBUTORS.md) file
- Mentioned in release notes for significant contributions
- Credited in module documentation (for module authors)
- Invited to join our [Discord community](https://discord.gg/8XEX33UUwZ)

## Module Submission Checklist

Before submitting a new module:

- [ ] Module follows SDK structure and conventions
- [ ] Dockerfile builds successfully
- [ ] Module executes without errors
- [ ] Configuration options are documented
- [ ] README.md is complete with examples
- [ ] Tests are included (pytest)
- [ ] Type hints are used throughout
- [ ] Linting passes (ruff)
- [ ] Security best practices followed
- [ ] No secrets or credentials in code
- [ ] License headers included

## Review Process

1. **Initial Review** - Maintainers review for completeness
2. **Technical Review** - Code quality and security assessment
3. **Testing** - Module tested in isolated environment
4. **Documentation Review** - Ensure docs are clear and complete
5. **Approval** - Module merged and included in next release

## License

By contributing to FuzzForge OSS, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

For module contributions:
- Modules you create remain under the project license
- You retain credit as the module author
- Your module may be used by others under the project license terms

---

## Getting Help

Need help contributing?

- Join our [Discord](https://discord.gg/8XEX33UUwZ)
- Read the [Module SDK Documentation](fuzzforge-modules/fuzzforge-modules-sdk/README.md)
- Check the module template for examples
- Contact: contact@fuzzinglabs.com

---

**Thank you for making FuzzForge better!**

Every contribution, no matter how small, helps build a stronger security research platform. Whether you're creating a module for web security, cloud scanning, mobile analysis, or any other cybersecurity domain, your work makes FuzzForge more powerful and versatile for the entire security community!
