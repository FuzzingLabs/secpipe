# How to Create a Custom Module in FuzzForge

This guide will walk you through the process of developing a custom security analysis module for FuzzForge. Modules are the building blocks of FuzzForge workflows, enabling you to add new analysis capabilities or extend existing ones.

---

## Prerequisites

Before you start, make sure you have:

- A working FuzzForge development environment (see [Contributing](/reference/contributing.md))
- Familiarity with Python and async programming
- Basic understanding of Docker and the FuzzForge architecture

---

## Step 1: Understand the Module Architecture

All FuzzForge modules inherit from a common `BaseModule` interface and use Pydantic models for type safety and result standardization.

**Key components:**

- `BaseModule`: Abstract base class for all modules
- `ModuleFinding`: Represents a single finding
- `ModuleResult`: Standardized result format for module execution
- `ModuleMetadata`: Describes module capabilities and requirements

Modules are located in `backend/toolbox/modules/`.

---

## Step 2: Create Your Module File

Let’s create a simple example: a **License Scanner** module that detects license files and extracts license information.

Create a new file:
`backend/toolbox/modules/license_scanner.py`

```python
import re
from pathlib import Path
from typing import Dict, Any, List
from .base import BaseModule, ModuleResult, ModuleMetadata, ModuleFinding

class LicenseScanner(BaseModule):
    """Scans for license files and extracts license information"""

    LICENSE_PATTERNS = {
        'MIT': r'MIT License|Permission is hereby granted',
        'Apache-2.0': r'Apache License|Version 2\\.0',
        'GPL-3.0': r'GNU GENERAL PUBLIC LICENSE|Version 3',
        'BSD-3-Clause': r'BSD 3-Clause|Redistribution and use',
    }

    LICENSE_FILES = [
        'LICENSE', 'LICENSE.txt', 'LICENSE.md',
        'COPYING', 'COPYRIGHT'
    ]

    def get_metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="License Scanner",
            version="1.0.0",
            description="Scans for license files and extracts license information",
            category="scanner",
            tags=["license", "compliance"]
        )

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        findings = []
        for license_name in self.LICENSE_FILES:
            license_file = workspace / license_name
            if license_file.is_file():
                content = license_file.read_text(encoding='utf-8', errors='ignore')
                detected = self._detect_license_type(content)
                findings.append(self.create_finding(
                    title=f"License file: {detected or 'Unknown'}",
                    description=f"Found license file with {detected or 'unknown'} license",
                    severity="info",
                    category="license",
                    file_path=str(license_file.relative_to(workspace)),
                    metadata={'license_type': detected}
                ))
        return self.create_result(findings=findings)

    def _detect_license_type(self, content: str) -> str:
        for license_type, pattern in self.LICENSE_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                return license_type
        return 'Unknown'

    def validate_config(self, config: Dict[str, Any]) -> bool:
        # No required config for this simple example
        return True
```

---

## Step 3: Register Your Module

Add your module to `backend/toolbox/modules/__init__.py`:

```python
from .license_scanner import LicenseScanner

__all__ = ['LicenseScanner']
```

---

## Step 4: Test Your Module

Create a test file (e.g., `test_license_scanner.py`) and run your module against a sample workspace:

```python
import asyncio
from pathlib import Path
from toolbox.modules.license_scanner import LicenseScanner

async def main():
    workspace = Path("/path/to/your/test/project")
    scanner = LicenseScanner()
    result = await scanner.execute({}, workspace)
    for finding in result.findings:
        print(f"{finding.file_path}: {finding.metadata.get('license_type')}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Module Types

FuzzForge supports several module types:

- **Scanner Modules:** Discover files, extract metadata (e.g., license scanner, dependency scanner)
- **Analyzer Modules:** Perform deep security analysis (e.g., static analyzer, secret detector)
- **Reporter Modules:** Format and output results (e.g., SARIF reporter, JSON reporter)

Each module type follows the same interface but focuses on a different stage of the workflow.

---

## Best Practices

- **Error Handling:** Never let a single file or tool error stop the whole module. Log errors and continue.
- **Async Operations:** Use async/await for file and network operations to maximize performance.
- **Configuration:** Validate all config parameters and provide sensible defaults.
- **Resource Limits:** Respect memory and CPU limits; process files in batches if needed.
- **Security:** Never execute untrusted code; sanitize file paths and inputs.

---

## Testing Your Module

- Write unit tests for your module’s logic and edge cases.
- Test integration by running your module as part of a FuzzForge workflow.
- Use temporary directories and mock files to simulate real-world scenarios.

---

## Advanced Tips

- Use Pydantic models for robust config validation.
- Implement progress reporting for long-running modules.
- Compose modules by orchestrating multiple sub-modules for complex analysis.
