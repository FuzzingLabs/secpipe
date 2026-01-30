"""
Unit tests for SecurityAnalyzer module
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "toolbox"))

from modules.analyzer.security_analyzer import SecurityAnalyzer


@pytest.fixture
def security_analyzer():
    """Create SecurityAnalyzer instance"""
    return SecurityAnalyzer()


@pytest.mark.asyncio
class TestSecurityAnalyzerMetadata:
    """Test SecurityAnalyzer metadata"""

    async def test_metadata_structure(self, security_analyzer):
        """Test that metadata has correct structure"""
        metadata = security_analyzer.get_metadata()

        assert metadata.name == "security_analyzer"
        assert metadata.version == "1.0.0"
        assert metadata.category == "analyzer"
        assert "security" in metadata.tags
        assert "vulnerabilities" in metadata.tags
        assert metadata.requires_workspace is True


@pytest.mark.asyncio
class TestSecurityAnalyzerConfigValidation:
    """Test configuration validation"""

    async def test_valid_config(self, security_analyzer):
        """Test that valid config passes validation"""
        config = {
            "file_extensions": [".py", ".js"],
            "check_secrets": True,
            "check_sql": True,
            "check_dangerous_functions": True
        }
        assert security_analyzer.validate_config(config) is True

    async def test_default_config(self, security_analyzer):
        """Test that empty config uses defaults"""
        config = {}
        assert security_analyzer.validate_config(config) is True

    async def test_invalid_extensions_type(self, security_analyzer):
        """Test that non-list extensions raises error"""
        config = {"file_extensions": ".py"}
        with pytest.raises(ValueError, match="file_extensions must be a list"):
            security_analyzer.validate_config(config)


@pytest.mark.asyncio
class TestSecurityAnalyzerSecretDetection:
    """Test hardcoded secret detection"""

    async def test_detect_api_key(self, security_analyzer, temp_workspace):
        """Test detection of hardcoded API key"""
        code_file = temp_workspace / "config.py"
        code_file.write_text("""
# Configuration file
api_key = "apikey_live_abcdefghijklmnopqrstuvwxyzabcdefghijk"
database_url = "postgresql://localhost/db"
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": True,
            "check_sql": False,
            "check_dangerous_functions": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        secret_findings = [f for f in result.findings if f.category == "hardcoded_secret"]
        assert len(secret_findings) > 0
        assert any("API Key" in f.title for f in secret_findings)

    async def test_detect_password(self, security_analyzer, temp_workspace):
        """Test detection of hardcoded password"""
        code_file = temp_workspace / "auth.py"
        code_file.write_text("""
def connect():
    password = "mySecretP@ssw0rd"
    return connect_db(password)
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": True,
            "check_sql": False,
            "check_dangerous_functions": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        secret_findings = [f for f in result.findings if f.category == "hardcoded_secret"]
        assert len(secret_findings) > 0

    async def test_detect_aws_credentials(self, security_analyzer, temp_workspace):
        """Test detection of AWS credentials"""
        code_file = temp_workspace / "aws_config.py"
        code_file.write_text("""
aws_access_key = "AKIAIOSFODNN7REALKEY"
aws_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYREALKEY"
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        aws_findings = [f for f in result.findings if "AWS" in f.title]
        assert len(aws_findings) >= 2  # Both access key and secret key

    async def test_no_secret_detection_when_disabled(self, security_analyzer, temp_workspace):
        """Test that secret detection can be disabled"""
        code_file = temp_workspace / "config.py"
        code_file.write_text('api_key = "sk_live_1234567890abcdef"')

        config = {
            "file_extensions": [".py"],
            "check_secrets": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        secret_findings = [f for f in result.findings if f.category == "hardcoded_secret"]
        assert len(secret_findings) == 0


@pytest.mark.asyncio
class TestSecurityAnalyzerSQLInjection:
    """Test SQL injection detection"""

    async def test_detect_string_concatenation(self, security_analyzer, temp_workspace):
        """Test detection of SQL string concatenation"""
        code_file = temp_workspace / "db.py"
        code_file.write_text("""
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return execute(query)
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": False,
            "check_sql": True,
            "check_dangerous_functions": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        sql_findings = [f for f in result.findings if f.category == "sql_injection"]
        assert len(sql_findings) > 0

    async def test_detect_f_string_sql(self, security_analyzer, temp_workspace):
        """Test detection of f-string in SQL"""
        code_file = temp_workspace / "db.py"
        code_file.write_text("""
def get_user(name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    return execute(query)
""")

        config = {
            "file_extensions": [".py"],
            "check_sql": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        sql_findings = [f for f in result.findings if f.category == "sql_injection"]
        assert len(sql_findings) > 0

    async def test_detect_dynamic_query_building(self, security_analyzer, temp_workspace):
        """Test detection of dynamic query building"""
        code_file = temp_workspace / "queries.py"
        code_file.write_text("""
def search(keyword):
    query = "SELECT * FROM products WHERE name LIKE " + keyword
    execute(query + " ORDER BY price")
""")

        config = {
            "file_extensions": [".py"],
            "check_sql": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        sql_findings = [f for f in result.findings if f.category == "sql_injection"]
        assert len(sql_findings) > 0

    async def test_no_sql_detection_when_disabled(self, security_analyzer, temp_workspace):
        """Test that SQL detection can be disabled"""
        code_file = temp_workspace / "db.py"
        code_file.write_text('query = "SELECT * FROM users WHERE id = " + user_id')

        config = {
            "file_extensions": [".py"],
            "check_sql": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        sql_findings = [f for f in result.findings if f.category == "sql_injection"]
        assert len(sql_findings) == 0


@pytest.mark.asyncio
class TestSecurityAnalyzerDangerousFunctions:
    """Test dangerous function detection"""

    async def test_detect_eval(self, security_analyzer, temp_workspace):
        """Test detection of eval() usage"""
        code_file = temp_workspace / "dangerous.py"
        code_file.write_text("""
def process_input(user_input):
    result = eval(user_input)
    return result
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": False,
            "check_sql": False,
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0
        assert any("eval" in f.title.lower() for f in dangerous_findings)

    async def test_detect_exec(self, security_analyzer, temp_workspace):
        """Test detection of exec() usage"""
        code_file = temp_workspace / "runner.py"
        code_file.write_text("""
def run_code(code):
    exec(code)
""")

        config = {
            "file_extensions": [".py"],
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0

    async def test_detect_os_system(self, security_analyzer, temp_workspace):
        """Test detection of os.system() usage"""
        code_file = temp_workspace / "commands.py"
        code_file.write_text("""
import os

def run_command(cmd):
    os.system(cmd)
""")

        config = {
            "file_extensions": [".py"],
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0
        assert any("os.system" in f.title for f in dangerous_findings)

    async def test_detect_pickle_loads(self, security_analyzer, temp_workspace):
        """Test detection of pickle.loads() usage"""
        code_file = temp_workspace / "serializer.py"
        code_file.write_text("""
import pickle

def deserialize(data):
    return pickle.loads(data)
""")

        config = {
            "file_extensions": [".py"],
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0

    async def test_detect_javascript_eval(self, security_analyzer, temp_workspace):
        """Test detection of eval() in JavaScript"""
        code_file = temp_workspace / "app.js"
        code_file.write_text("""
function processInput(userInput) {
    return eval(userInput);
}
""")

        config = {
            "file_extensions": [".js"],
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0

    async def test_detect_innerHTML(self, security_analyzer, temp_workspace):
        """Test detection of innerHTML (XSS risk)"""
        code_file = temp_workspace / "dom.js"
        code_file.write_text("""
function updateContent(html) {
    document.getElementById("content").innerHTML = html;
}
""")

        config = {
            "file_extensions": [".js"],
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) > 0

    async def test_no_dangerous_detection_when_disabled(self, security_analyzer, temp_workspace):
        """Test that dangerous function detection can be disabled"""
        code_file = temp_workspace / "code.py"
        code_file.write_text('result = eval(user_input)')

        config = {
            "file_extensions": [".py"],
            "check_dangerous_functions": False
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]
        assert len(dangerous_findings) == 0


@pytest.mark.asyncio
class TestSecurityAnalyzerMultipleIssues:
    """Test detection of multiple issues in same file"""

    async def test_detect_multiple_vulnerabilities(self, security_analyzer, temp_workspace):
        """Test detection of multiple vulnerability types"""
        code_file = temp_workspace / "vulnerable.py"
        code_file.write_text("""
import os

# Hardcoded credentials
api_key = "apikey_live_abcdefghijklmnopqrstuvwxyzabcdef"
password = "MySecureP@ssw0rd"

def process_query(user_input):
    # SQL injection
    query = "SELECT * FROM users WHERE name = " + user_input

    # Dangerous function
    result = eval(user_input)

    # Command injection
    os.system(user_input)

    return result
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": True,
            "check_sql": True,
            "check_dangerous_functions": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"

        # Should find multiple types of issues
        secret_findings = [f for f in result.findings if f.category == "hardcoded_secret"]
        sql_findings = [f for f in result.findings if f.category == "sql_injection"]
        dangerous_findings = [f for f in result.findings if f.category == "dangerous_function"]

        assert len(secret_findings) > 0
        assert len(sql_findings) > 0
        assert len(dangerous_findings) > 0


@pytest.mark.asyncio
class TestSecurityAnalyzerSummary:
    """Test result summary generation"""

    async def test_summary_structure(self, security_analyzer, temp_workspace):
        """Test that summary has correct structure"""
        (temp_workspace / "test.py").write_text("print('hello')")

        config = {"file_extensions": [".py"]}
        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        assert "files_analyzed" in result.summary
        assert "total_findings" in result.summary
        assert "extensions_scanned" in result.summary

        assert isinstance(result.summary["files_analyzed"], int)
        assert isinstance(result.summary["total_findings"], int)
        assert isinstance(result.summary["extensions_scanned"], list)

    async def test_empty_workspace(self, security_analyzer, temp_workspace):
        """Test analyzing empty workspace"""
        config = {"file_extensions": [".py"]}
        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "partial"  # No files found
        assert result.summary["files_analyzed"] == 0

    async def test_analyze_multiple_file_types(self, security_analyzer, temp_workspace):
        """Test analyzing multiple file types"""
        (temp_workspace / "app.py").write_text("print('hello')")
        (temp_workspace / "script.js").write_text("console.log('hello')")
        (temp_workspace / "index.php").write_text("<?php echo 'hello'; ?>")

        config = {"file_extensions": [".py", ".js", ".php"]}
        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        assert result.summary["files_analyzed"] == 3


@pytest.mark.asyncio
class TestSecurityAnalyzerFalsePositives:
    """Test false positive filtering"""

    async def test_skip_test_secrets(self, security_analyzer, temp_workspace):
        """Test that test/example secrets are filtered"""
        code_file = temp_workspace / "test_config.py"
        code_file.write_text("""
# Test configuration - should be filtered
api_key = "test_key_example"
password = "dummy_password_123"
token = "sample_token_placeholder"
""")

        config = {
            "file_extensions": [".py"],
            "check_secrets": True
        }

        result = await security_analyzer.execute(config, temp_workspace)

        assert result.status == "success"
        # These should be filtered as false positives
        secret_findings = [f for f in result.findings if f.category == "hardcoded_secret"]
        # Should have fewer or no findings due to false positive filtering
        assert len(secret_findings) == 0 or all(
            not any(fp in f.description.lower() for fp in ['test', 'example', 'dummy', 'sample'])
            for f in secret_findings
        )
