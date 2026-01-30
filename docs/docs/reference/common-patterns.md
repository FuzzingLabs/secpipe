# Common Patterns Cookbook 👨‍🍳

A collection of proven patterns and recipes for FuzzForge modules and workflows. Copy, paste, and adapt these examples to build your own security tools quickly!

## Module Patterns

### File Processing Patterns

#### Pattern 1: Selective File Scanner

```python
class SelectiveScanner(BaseModule):
    """Scan only specific file types with size limits"""

    SUPPORTED_EXTENSIONS = {'.py', '.js', '.java', '.cpp', '.c', '.go', '.rs'}
    DEFAULT_MAX_SIZE = 5 * 1024 * 1024  # 5MB

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        max_size = config.get('max_file_size', self.DEFAULT_MAX_SIZE)
        extensions = set(config.get('extensions', self.SUPPORTED_EXTENSIONS))

        findings = []
        processed_files = 0

        for file_path in workspace.rglob('*'):
            if (file_path.is_file() and
                file_path.suffix.lower() in extensions and
                file_path.stat().st_size <= max_size):

                try:
                    result = await self._process_file(file_path, workspace)
                    findings.extend(result)
                    processed_files += 1
                except Exception as e:
                    # Log error but continue processing
                    logger.warning(f"Failed to process {file_path}: {e}")

        return self.create_result(
            findings=findings,
            summary={'files_processed': processed_files}
        )
```

#### Pattern 2: Content-Based File Analysis

```python
class ContentAnalyzer(BaseModule):
    """Analyze file content with encoding detection"""

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        findings = []

        for file_path in workspace.rglob('*'):
            if file_path.is_file():
                content = await self._safe_read_file(file_path)
                if content:
                    analysis_result = await self._analyze_content(content, file_path, workspace)
                    findings.extend(analysis_result)

        return self.create_result(findings=findings)

    async def _safe_read_file(self, file_path: Path) -> str:
        """Safely read file with encoding detection"""
        try:
            # Try UTF-8 first
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Fall back to latin-1 for binary-like files
                return file_path.read_text(encoding='latin-1', errors='ignore')
            except Exception:
                return ""

    async def _analyze_content(self, content: str, file_path: Path, workspace: Path) -> List[ModuleFinding]:
        """Override this method in your specific analyzer"""
        # Example: Find TODO comments
        findings = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if 'TODO' in line.upper():
                findings.append(self.create_finding(
                    title="TODO comment found",
                    description=f"TODO comment: {line.strip()}",
                    severity="info",
                    category="code_quality",
                    file_path=str(file_path.relative_to(workspace)),
                    line_start=i,
                    code_snippet=line.strip()
                ))

        return findings
```

#### Pattern 3: Directory Structure Analysis

```python
class StructureAnalyzer(BaseModule):
    """Analyze project directory structure"""

    IMPORTANT_FILES = {
        'README.md': 'documentation',
        'LICENSE': 'legal',
        '.gitignore': 'vcs',
        'requirements.txt': 'dependencies',
        'package.json': 'dependencies',
        'Dockerfile': 'deployment'
    }

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        findings = []
        structure_analysis = {
            'total_directories': 0,
            'max_depth': 0,
            'important_files_found': [],
            'important_files_missing': []
        }

        # Analyze directory structure
        for item in workspace.rglob('*'):
            if item.is_dir():
                structure_analysis['total_directories'] += 1
                depth = len(item.relative_to(workspace).parts)
                structure_analysis['max_depth'] = max(structure_analysis['max_depth'], depth)

        # Check for important files
        for filename, category in self.IMPORTANT_FILES.items():
            file_path = workspace / filename
            if file_path.exists():
                structure_analysis['important_files_found'].append(filename)
            else:
                structure_analysis['important_files_missing'].append(filename)
                findings.append(self.create_finding(
                    title=f"Missing {category} file",
                    description=f"Recommended file '{filename}' not found",
                    severity="info",
                    category=category,
                    metadata={'file_type': category, 'recommended_file': filename}
                ))

        return self.create_result(
            findings=findings,
            summary=structure_analysis
        )
```

### Configuration Patterns

#### Pattern 1: Schema-Based Configuration

```python
from pydantic import BaseModel, Field, validator
from enum import Enum

class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ModuleConfig(BaseModel):
    """Type-safe configuration with validation"""
    severity_threshold: SeverityLevel = SeverityLevel.MEDIUM
    max_file_size_mb: int = Field(default=10, gt=0, le=100)
    include_patterns: List[str] = Field(default=['**/*.py', '**/*.js'])
    exclude_patterns: List[str] = Field(default=['**/node_modules/**', '**/.git/**'])
    timeout_seconds: int = Field(default=300, gt=0, le=3600)

    @validator('include_patterns')
    def validate_patterns(cls, v):
        if not v:
            raise ValueError('At least one include pattern required')
        return v

class ConfigurableModule(BaseModule):
    def validate_config(self, config: Dict[str, Any]) -> bool:
        try:
            ModuleConfig(**config)
            return True
        except Exception:
            return False

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        # Get validated configuration
        validated_config = ModuleConfig(**config)

        # Use type-safe configuration
        max_size = validated_config.max_file_size_mb * 1024 * 1024
        severity = validated_config.severity_threshold
        # ... rest of implementation
```

#### Pattern 2: Configuration Templates

```python
class TemplateBasedModule(BaseModule):
    """Module with configuration templates"""

    TEMPLATES = {
        'quick': {
            'max_file_size_mb': 5,
            'timeout_seconds': 60,
            'severity_threshold': 'medium'
        },
        'thorough': {
            'max_file_size_mb': 50,
            'timeout_seconds': 1800,
            'severity_threshold': 'low'
        },
        'critical_only': {
            'max_file_size_mb': 100,
            'timeout_seconds': 3600,
            'severity_threshold': 'critical'
        }
    }

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        # Load template if specified
        template_name = config.get('template')
        if template_name and template_name in self.TEMPLATES:
            base_config = self.TEMPLATES[template_name].copy()
            base_config.update(config)  # Override template with specific config
            config = base_config

        # Continue with normal execution
        return await self._execute_with_config(config, workspace)
```

### Error Handling Recipes

#### Pattern 1: Graceful Degradation

```python
class ResilientModule(BaseModule):
    """Module that handles errors gracefully"""

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        findings = []
        errors = []
        processed_files = 0

        for file_path in workspace.rglob('*'):
            if file_path.is_file():
                try:
                    result = await self._analyze_file(file_path, workspace, config)
                    findings.extend(result)
                    processed_files += 1
                except PermissionError as e:
                    errors.append({
                        'file': str(file_path.relative_to(workspace)),
                        'error': 'Permission denied',
                        'type': 'permission_error'
                    })
                except UnicodeDecodeError as e:
                    errors.append({
                        'file': str(file_path.relative_to(workspace)),
                        'error': 'Encoding error',
                        'type': 'encoding_error'
                    })
                except Exception as e:
                    errors.append({
                        'file': str(file_path.relative_to(workspace)),
                        'error': str(e),
                        'type': 'analysis_error'
                    })

        # Determine overall status
        total_files = processed_files + len(errors)
        if len(errors) > total_files * 0.5:  # More than 50% failed
            status = "partial"
        else:
            status = "success"

        return self.create_result(
            findings=findings,
            status=status,
            summary={
                'files_processed': processed_files,
                'files_failed': len(errors),
                'error_rate': len(errors) / total_files if total_files > 0 else 0
            },
            metadata={'errors': errors}
        )
```

#### Pattern 2: Circuit Breaker

```python
import time

class CircuitBreakerModule(BaseModule):
    """Module with circuit breaker for expensive operations"""

    def __init__(self):
        super().__init__()
        self.failure_count = 0
        self.last_failure_time = 0
        self.circuit_open = False
        self.failure_threshold = 5
        self.recovery_timeout = 60  # seconds

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        findings = []

        for file_path in workspace.rglob('*'):
            if file_path.is_file():
                if self._is_circuit_open():
                    # Circuit is open, skip expensive operations
                    findings.append(self.create_finding(
                        title="Analysis skipped",
                        description="Circuit breaker is open due to previous failures",
                        severity="info",
                        category="system",
                        file_path=str(file_path.relative_to(workspace))
                    ))
                    continue

                try:
                    result = await self._expensive_analysis(file_path, workspace)
                    findings.extend(result)
                    self._on_success()
                except Exception as e:
                    self._on_failure()
                    logger.warning(f"Analysis failed for {file_path}: {e}")

        return self.create_result(findings=findings)

    def _is_circuit_open(self) -> bool:
        if not self.circuit_open:
            return False

        # Check if recovery timeout has passed
        if time.time() - self.last_failure_time > self.recovery_timeout:
            self.circuit_open = False
            self.failure_count = 0
            return False

        return True

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.circuit_open = True

    def _on_success(self):
        if self.circuit_open:
            self.circuit_open = False
            self.failure_count = 0
```

### Performance Patterns

#### Pattern 1: Batch Processing

```python
import asyncio
from typing import List, AsyncGenerator

class BatchProcessor(BaseModule):
    """Process files in batches to control memory usage"""

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        batch_size = config.get('batch_size', 10)
        findings = []

        async for batch_findings in self._process_in_batches(workspace, batch_size, config):
            findings.extend(batch_findings)

        return self.create_result(findings=findings)

    async def _process_in_batches(
        self,
        workspace: Path,
        batch_size: int,
        config: Dict[str, Any]
    ) -> AsyncGenerator[List[ModuleFinding], None]:
        """Process files in batches"""
        files = [f for f in workspace.rglob('*') if f.is_file()]

        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_findings = []

            for file_path in batch:
                try:
                    result = await self._analyze_file(file_path, workspace, config)
                    batch_findings.extend(result)
                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")

            yield batch_findings
```

#### Pattern 2: Concurrent Processing with Limits

```python
class ConcurrentProcessor(BaseModule):
    """Process files concurrently with semaphore limits"""

    async def execute(self, config: Dict[str, Any], workspace: Path) -> ModuleResult:
        max_concurrent = config.get('max_concurrent', 5)
        semaphore = asyncio.Semaphore(max_concurrent)

        files = [f for f in workspace.rglob('*') if f.is_file()]

        # Process files concurrently
        tasks = [
            self._process_file_with_semaphore(file_path, workspace, config, semaphore)
            for file_path in files
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect findings and handle exceptions
        findings = []
        for result in results:
            if isinstance(result, list):
                findings.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Processing failed: {result}")

        return self.create_result(findings=findings)

    async def _process_file_with_semaphore(
        self,
        file_path: Path,
        workspace: Path,
        config: Dict[str, Any],
        semaphore: asyncio.Semaphore
    ) -> List[ModuleFinding]:
        """Process a single file with semaphore protection"""
        async with semaphore:
            return await self._analyze_file(file_path, workspace, config)
```

## ⚡ Workflow Patterns

### Sequential Processing

```python
@flow(name="sequential_analysis")
async def sequential_workflow(target_path: str, **kwargs) -> Dict[str, Any]:
    """Execute analysis steps in sequence"""
    workspace = Path(target_path)

    # Step 1: File discovery
    scanner_config = kwargs.get('scanner_config', {})
    scan_results = await file_scan_task(workspace, scanner_config)

    # Step 2: Analysis (depends on scan results)
    analyzer_config = {
        **kwargs.get('analyzer_config', {}),
        'discovered_files': scan_results.get('summary', {}).get('total_files', 0)
    }
    analysis_results = await analysis_task(scan_results, workspace, analyzer_config)

    # Step 3: Report generation (depends on analysis)
    reporter_config = kwargs.get('reporter_config', {})
    final_report = await report_task(analysis_results, workspace, reporter_config)

    return final_report
```

### Parallel Execution

```python
@flow(name="parallel_analysis")
async def parallel_workflow(target_path: str, **kwargs) -> Dict[str, Any]:
    """Execute independent analyses in parallel"""
    workspace = Path(target_path)

    # Submit parallel tasks
    static_future = static_analysis_task.submit(workspace, kwargs.get('static_config', {}))
    secret_future = secret_detection_task.submit(workspace, kwargs.get('secret_config', {}))
    license_future = license_check_task.submit(workspace, kwargs.get('license_config', {}))

    # Wait for all to complete
    static_results = await static_future.result()
    secret_results = await secret_future.result()
    license_results = await license_future.result()

    # Combine results
    combined_report = await combine_results_task(
        [static_results, secret_results, license_results],
        workspace,
        kwargs.get('reporter_config', {})
    )

    return combined_report
```

### Conditional Logic

```python
@flow(name="conditional_analysis")
async def conditional_workflow(target_path: str, **kwargs) -> Dict[str, Any]:
    """Execute workflow with conditional branches"""
    workspace = Path(target_path)

    # Initial assessment
    assessment = await quick_assessment_task(workspace)

    # Branch based on project type
    if assessment.get('project_type') == 'web_application':
        # Web app specific analysis
        web_results = await web_security_task(workspace, kwargs.get('web_config', {}))
        final_results = web_results

    elif assessment.get('project_type') == 'library':
        # Library specific analysis
        lib_results = await library_analysis_task(workspace, kwargs.get('lib_config', {}))
        final_results = lib_results

    else:
        # Generic analysis
        generic_results = await generic_analysis_task(workspace, kwargs.get('generic_config', {}))
        final_results = generic_results

    # Optional deep analysis for high-risk projects
    if assessment.get('risk_level', 'low') in ['high', 'critical']:
        deep_results = await deep_analysis_task(workspace, kwargs.get('deep_config', {}))
        final_results = await merge_results_task(final_results, deep_results)

    return final_results
```

### Data Transformation

```python
@task(name="filter_and_transform")
async def filter_transform_task(
    raw_results: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Filter and transform findings based on criteria"""

    findings = raw_results.get('findings', [])

    # Filter by severity
    min_severity = config.get('min_severity', 'low')
    severity_order = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
    min_level = severity_order.get(min_severity, 0)

    filtered_findings = [
        f for f in findings
        if severity_order.get(f.get('severity', 'info'), 0) >= min_level
    ]

    # Group by category
    categorized = {}
    for finding in filtered_findings:
        category = finding.get('category', 'other')
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(finding)

    # Transform findings (add risk scores, priorities, etc.)
    enriched_findings = []
    for finding in filtered_findings:
        enriched_finding = {
            **finding,
            'risk_score': calculate_risk_score(finding),
            'priority': determine_priority(finding),
            'remediation_effort': estimate_effort(finding)
        }
        enriched_findings.append(enriched_finding)

    return {
        'findings': enriched_findings,
        'summary': {
            'total_findings': len(enriched_findings),
            'by_category': {k: len(v) for k, v in categorized.items()},
            'by_severity': {
                severity: len([f for f in enriched_findings if f.get('severity') == severity])
                for severity in ['info', 'low', 'medium', 'high', 'critical']
            }
        }
    }
```

## 🧪 Testing Patterns

### Pattern 1: Comprehensive Module Testing

```python
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

class TestMyModule:

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            # Create test files
            (workspace / 'test.py').write_text('print("hello")')
            (workspace / 'config.json').write_text('{"key": "value"}')
            yield workspace

    @pytest.fixture
    def module(self):
        return MyModule()

    @pytest.fixture
    def base_config(self):
        return {
            'max_file_size_mb': 10,
            'severity_threshold': 'medium',
            'timeout_seconds': 60
        }

    @pytest.mark.asyncio
    async def test_execute_success(self, module, temp_workspace, base_config):
        result = await module.execute(base_config, temp_workspace)

        assert result.status == "success"
        assert isinstance(result.findings, list)
        assert isinstance(result.summary, dict)
        assert 'total_files' in result.summary

    @pytest.mark.asyncio
    async def test_execute_empty_workspace(self, module, base_config):
        with tempfile.TemporaryDirectory() as empty_dir:
            result = await module.execute(base_config, Path(empty_dir))

            assert result.summary['total_files'] == 0
            assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_config_validation(self, module):
        assert module.validate_config({'max_file_size_mb': 10})
        assert not module.validate_config({'max_file_size_mb': -1})
        assert not module.validate_config({'max_file_size_mb': 'invalid'})

    @pytest.mark.asyncio
    async def test_error_handling(self, module, base_config):
        with patch.object(module, '_analyze_file', side_effect=Exception("Test error")):
            result = await module.execute(base_config, Path('/tmp'))

            # Should handle errors gracefully
            assert 'errors' in result.metadata
            assert len(result.metadata['errors']) > 0

    @pytest.mark.parametrize("severity,expected", [
        ('low', ['low', 'medium', 'high', 'critical']),
        ('medium', ['medium', 'high', 'critical']),
        ('high', ['high', 'critical']),
        ('critical', ['critical'])
    ])
    async def test_severity_filtering(self, module, temp_workspace, severity, expected):
        config = {'severity_threshold': severity}
        result = await module.execute(config, temp_workspace)

        found_severities = {f.severity for f in result.findings}
        assert found_severities.issubset(set(expected))
```

## 🔧 Utility Functions

### File Type Detection

```python
def detect_file_type(file_path: Path) -> str:
    """Detect file type from extension and content"""

    # Extension-based detection
    extension_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.go': 'go',
        '.rs': 'rust',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.xml': 'xml',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
        '.txt': 'text'
    }

    file_type = extension_map.get(file_path.suffix.lower())
    if file_type:
        return file_type

    # Content-based detection for files without extensions
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline().strip()

            if first_line.startswith('#!'):
                if 'python' in first_line:
                    return 'python'
                elif 'bash' in first_line or 'sh' in first_line:
                    return 'shell'
                elif 'node' in first_line:
                    return 'javascript'

            if first_line.startswith('<?xml'):
                return 'xml'

            if first_line.startswith('<!DOCTYPE html') or first_line.startswith('<html'):
                return 'html'

    except Exception:
        pass

    return 'unknown'
```

### Risk Scoring

```python
def calculate_risk_score(finding: Dict[str, Any]) -> int:
    """Calculate numeric risk score for a finding"""

    base_scores = {
        'critical': 100,
        'high': 75,
        'medium': 50,
        'low': 25,
        'info': 10
    }

    severity = finding.get('severity', 'info')
    base_score = base_scores.get(severity, 10)

    # Adjust based on category
    category_multipliers = {
        'security': 1.0,
        'vulnerability': 1.0,
        'credential': 1.2,
        'injection': 1.1,
        'authentication': 1.1,
        'authorization': 1.1,
        'code_quality': 0.8,
        'performance': 0.7,
        'documentation': 0.5
    }

    category = finding.get('category', 'other')
    multiplier = category_multipliers.get(category, 0.9)

    # Adjust based on file location
    file_path = finding.get('file_path', '')
    if any(sensitive in file_path.lower() for sensitive in ['config', 'secret', 'password', 'key']):
        multiplier *= 1.2

    return int(base_score * multiplier)
```

### Finding Deduplication

```python
def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate findings based on title, file, and line"""

    seen = set()
    deduplicated = []

    for finding in findings:
        # Create unique key
        key = (
            finding.get('title', ''),
            finding.get('file_path', ''),
            finding.get('line_start', 0),
            finding.get('category', '')
        )

        if key not in seen:
            seen.add(key)
            deduplicated.append(finding)
        else:
            # Update metadata to indicate duplication
            for existing in deduplicated:
                if (existing.get('title') == finding.get('title') and
                    existing.get('file_path') == finding.get('file_path')):

                    metadata = existing.setdefault('metadata', {})
                    metadata['duplicate_count'] = metadata.get('duplicate_count', 1) + 1
                    break

    return deduplicated
```

---

**🎯 Next Steps**: Use these patterns as building blocks for your own modules and workflows. Mix and match patterns to create powerful security analysis tools!
