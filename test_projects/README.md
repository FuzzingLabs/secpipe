# FuzzForge Vulnerable Test Project

This directory contains a comprehensive vulnerable test application designed to validate FuzzForge's security workflows. The project contains multiple categories of security vulnerabilities to test `security_assessment`, `gitleaks_detection`, `trufflehog_detection`, and `llm_secret_detection` workflows.

## Test Project Overview

### Vulnerable Application (`vulnerable_app/`)
**Purpose**: Comprehensive vulnerable application for testing security workflows

**Supported Workflows**:
- `security_assessment` - General security scanning and analysis
- `gitleaks_detection` - Pattern-based secret detection
- `trufflehog_detection` - Entropy-based secret detection with verification
- `llm_secret_detection` - AI-powered semantic secret detection

**Vulnerabilities Included**:
- SQL injection vulnerabilities
- Command injection
- Hardcoded secrets and credentials
- Path traversal vulnerabilities
- Weak cryptographic functions
- Server-side template injection (SSTI)
- Pickle deserialization attacks
- CSRF missing protection
- Information disclosure
- API keys and tokens
- Database connection strings
- Private keys and certificates

**Files**:
- Multiple source code files with various vulnerability types
- Configuration files with embedded secrets
- Dependencies with known vulnerabilities

**Expected Detections**: 30+ findings across both security assessment and secret detection workflows

---

## Usage Instructions

### Testing with FuzzForge Workflows

The vulnerable application can be tested with multiple security workflows:

```bash
# Test security assessment workflow
curl -X POST http://localhost:8000/workflows/security_assessment/submit \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/path/to/test_projects/vulnerable_app"
  }'

# Test Gitleaks secret detection workflow
curl -X POST http://localhost:8000/workflows/gitleaks_detection/submit \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/path/to/test_projects/vulnerable_app"
  }'

# Test TruffleHog secret detection workflow
curl -X POST http://localhost:8000/workflows/trufflehog_detection/submit \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/path/to/test_projects/vulnerable_app"
  }'
```

### Expected Results

Each workflow should produce SARIF-formatted results with:
- High-severity findings for critical vulnerabilities
- Medium-severity findings for moderate risks
- Detailed descriptions and remediation guidance
- Code flow information where applicable

### Validation Criteria

A successful test should detect:
- **Security Assessment**: At least 20 various security vulnerabilities
- **Gitleaks Detection**: At least 10 different types of secrets
- **TruffleHog Detection**: At least 5 high-entropy secrets
- **LLM Secret Detection**: At least 15 secrets with semantic understanding

---

## Security Notice

⚠️ **WARNING**: This project contains intentional security vulnerabilities and should NEVER be deployed in production environments or exposed to public networks. It is designed solely for security testing and validation purposes.

## File Structure
```
test_projects/
├── README.md
└── vulnerable_app/
    ├── [Multiple vulnerable source files]
    ├── [Configuration files with secrets]
    └── [Dependencies with known issues]
```