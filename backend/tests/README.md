# FuzzForge Test Suite

Comprehensive test infrastructure for FuzzForge modules and workflows.

## Directory Structure

```
tests/
├── conftest.py           # Shared pytest fixtures
├── unit/                 # Fast, isolated unit tests
│   ├── test_modules/     # Module-specific tests
│   │   ├── test_cargo_fuzzer.py
│   │   └── test_atheris_fuzzer.py
│   ├── test_workflows/   # Workflow tests
│   └── test_api/         # API endpoint tests
├── integration/          # Integration tests (requires Docker)
└── fixtures/             # Test data and projects
    ├── test_projects/    # Vulnerable projects for testing
    └── expected_results/ # Expected output for validation
```

## Running Tests

### All Tests
```bash
cd backend
pytest tests/ -v
```

### Unit Tests Only (Fast)
```bash
pytest tests/unit/ -v
```

### Integration Tests (Requires Docker)
```bash
# Start services
docker-compose up -d

# Run integration tests
pytest tests/integration/ -v

# Cleanup
docker-compose down
```

### With Coverage
```bash
pytest tests/ --cov=toolbox/modules --cov=src --cov-report=html
```

### Parallel Execution
```bash
pytest tests/unit/ -n auto
```

## Available Fixtures

### Workspace Fixtures
- `temp_workspace`: Empty temporary workspace
- `python_test_workspace`: Python project with vulnerabilities
- `rust_test_workspace`: Rust project with fuzz targets

### Module Fixtures
- `atheris_fuzzer`: AtherisFuzzer instance
- `cargo_fuzzer`: CargoFuzzer instance
- `file_scanner`: FileScanner instance

### Configuration Fixtures
- `atheris_config`: Default Atheris configuration
- `cargo_fuzz_config`: Default cargo-fuzz configuration
- `gitleaks_config`: Default Gitleaks configuration

### Mock Fixtures
- `mock_stats_callback`: Mock stats callback for fuzzing
- `mock_temporal_context`: Mock Temporal activity context

## Writing Tests

### Unit Test Example
```python
import pytest

@pytest.mark.asyncio
async def test_module_execution(cargo_fuzzer, rust_test_workspace, cargo_fuzz_config):
    """Test module execution"""
    result = await cargo_fuzzer.execute(cargo_fuzz_config, rust_test_workspace)

    assert result.status == "success"
    assert result.execution_time > 0
```

### Integration Test Example
```python
@pytest.mark.integration
async def test_end_to_end_workflow():
    """Test complete workflow execution"""
    # Test full workflow with real services
    pass
```

## CI/CD Integration

Tests run automatically on:
- **Push to main/develop**: Full test suite
- **Pull requests**: Full test suite + coverage
- **Nightly**: Extended integration tests

See `.github/workflows/test.yml` for configuration.

## Code Coverage

Target coverage: **80%+** for core modules

View coverage report:
```bash
pytest tests/ --cov --cov-report=html
open htmlcov/index.html
```
