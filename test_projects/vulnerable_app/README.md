# Vulnerable Test Application

This is a **TEST PROJECT** designed to trigger security findings in the FuzzForge security assessment workflow.

⚠️ **WARNING**: This application contains intentional security vulnerabilities for testing purposes only. DO NOT use any of this code in production!

## Vulnerabilities Included

### Hardcoded Secrets
- Database passwords
- API keys (AWS, Stripe, GitHub, etc.)
- JWT secrets
- Private keys (RSA, Bitcoin, Ethereum)
- OAuth tokens

### Code Injection
- `eval()` usage in multiple languages
- `exec()` and `system()` calls
- Dynamic function creation
- Template injection

### SQL Injection
- String concatenation in queries
- String formatting in SQL
- Dynamic query building
- Parameterless queries

### Command Injection
- Unsanitized user input in system commands
- Shell execution with user data
- Subprocess calls with shell=True

### Path Traversal
- Unvalidated file paths
- Directory traversal patterns
- Insecure file operations

### Other Vulnerabilities
- XSS vulnerabilities
- Insecure deserialization
- Weak cryptography (MD5, weak random)
- CORS misconfigurations
- Debug mode enabled

## Files Overview

- `src/` - Source code with various vulnerabilities
  - `database.py` - Python with SQL injection and hardcoded secrets
  - `api_handler.py` - Python with eval and command injection
  - `utils.rb` - Ruby vulnerabilities
  - `Main.java` - Java security issues
  - `app.go` - Go vulnerabilities

- `scripts/` - Script files
  - `deploy.php` - PHP vulnerabilities
  - `backup.js` - JavaScript security issues

- `config/` - Configuration files
  - `settings.py` - Hardcoded credentials
  - `database.yaml` - Database passwords

- `.env` - Environment file with secrets
- `private_key.pem` - Private key file
- `wallet.json` - Cryptocurrency wallets
- `.github/workflows/` - CI/CD with hardcoded secrets

## Expected Findings

When running the security assessment workflow, you should see:
- Multiple hardcoded secrets detected
- SQL injection vulnerabilities
- Command injection risks
- Dangerous function usage
- Sensitive file discoveries

## Testing

To test with FuzzForge:

```bash
curl -X POST "http://localhost:8000/workflows/security_assessment/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "/path/to/test_projects/vulnerable_app",
    "parameters": {
      "scanner_config": {"check_sensitive": true},
      "analyzer_config": {"check_secrets": true, "check_sql": true}
    }
  }'
```

## Note

This is purely for testing security scanning capabilities. All credentials and keys are fake/example values.