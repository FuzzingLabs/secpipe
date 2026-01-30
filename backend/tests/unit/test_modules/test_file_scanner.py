"""
Unit tests for FileScanner module
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "toolbox"))



@pytest.mark.asyncio
class TestFileScannerMetadata:
    """Test FileScanner metadata"""

    async def test_metadata_structure(self, file_scanner):
        """Test that metadata has correct structure"""
        metadata = file_scanner.get_metadata()

        assert metadata.name == "file_scanner"
        assert metadata.version == "1.0.0"
        assert metadata.category == "scanner"
        assert "files" in metadata.tags
        assert "enumeration" in metadata.tags
        assert metadata.requires_workspace is True


@pytest.mark.asyncio
class TestFileScannerConfigValidation:
    """Test configuration validation"""

    async def test_valid_config(self, file_scanner):
        """Test that valid config passes validation"""
        config = {
            "patterns": ["*.py", "*.js"],
            "max_file_size": 1048576,
            "check_sensitive": True,
            "calculate_hashes": False
        }
        assert file_scanner.validate_config(config) is True

    async def test_default_config(self, file_scanner):
        """Test that empty config uses defaults"""
        config = {}
        assert file_scanner.validate_config(config) is True

    async def test_invalid_patterns_type(self, file_scanner):
        """Test that non-list patterns raises error"""
        config = {"patterns": "*.py"}
        with pytest.raises(ValueError, match="patterns must be a list"):
            file_scanner.validate_config(config)

    async def test_invalid_max_file_size(self, file_scanner):
        """Test that invalid max_file_size raises error"""
        config = {"max_file_size": -1}
        with pytest.raises(ValueError, match="max_file_size must be a positive integer"):
            file_scanner.validate_config(config)

    async def test_invalid_max_file_size_type(self, file_scanner):
        """Test that non-integer max_file_size raises error"""
        config = {"max_file_size": "large"}
        with pytest.raises(ValueError, match="max_file_size must be a positive integer"):
            file_scanner.validate_config(config)


@pytest.mark.asyncio
class TestFileScannerExecution:
    """Test scanner execution"""

    async def test_scan_python_files(self, file_scanner, python_test_workspace):
        """Test scanning Python files"""
        config = {
            "patterns": ["*.py"],
            "check_sensitive": False,
            "calculate_hashes": False
        }

        result = await file_scanner.execute(config, python_test_workspace)

        assert result.module == "file_scanner"
        assert result.status == "success"
        assert len(result.findings) > 0

        # Check that Python files were found
        python_files = [f for f in result.findings if f.file_path.endswith('.py')]
        assert len(python_files) > 0

    async def test_scan_all_files(self, file_scanner, python_test_workspace):
        """Test scanning all files with wildcard"""
        config = {
            "patterns": ["*"],
            "check_sensitive": False,
            "calculate_hashes": False
        }

        result = await file_scanner.execute(config, python_test_workspace)

        assert result.status == "success"
        assert len(result.findings) > 0
        assert result.summary["total_files"] > 0

    async def test_scan_with_multiple_patterns(self, file_scanner, python_test_workspace):
        """Test scanning with multiple patterns"""
        config = {
            "patterns": ["*.py", "*.txt"],
            "check_sensitive": False,
            "calculate_hashes": False
        }

        result = await file_scanner.execute(config, python_test_workspace)

        assert result.status == "success"
        assert len(result.findings) > 0

    async def test_empty_workspace(self, file_scanner, temp_workspace):
        """Test scanning empty workspace"""
        config = {
            "patterns": ["*.py"],
            "check_sensitive": False
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        assert len(result.findings) == 0
        assert result.summary["total_files"] == 0


@pytest.mark.asyncio
class TestFileScannerSensitiveDetection:
    """Test sensitive file detection"""

    async def test_detect_env_file(self, file_scanner, temp_workspace):
        """Test detection of .env file"""
        # Create .env file
        (temp_workspace / ".env").write_text("API_KEY=secret123")

        config = {
            "patterns": ["*"],
            "check_sensitive": True,
            "calculate_hashes": False
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"

        # Check for sensitive file finding
        sensitive_findings = [f for f in result.findings if f.category == "sensitive_file"]
        assert len(sensitive_findings) > 0
        assert any(".env" in f.title for f in sensitive_findings)

    async def test_detect_private_key(self, file_scanner, temp_workspace):
        """Test detection of private key file"""
        # Create private key file
        (temp_workspace / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----")

        config = {
            "patterns": ["*"],
            "check_sensitive": True
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        sensitive_findings = [f for f in result.findings if f.category == "sensitive_file"]
        assert len(sensitive_findings) > 0

    async def test_no_sensitive_detection_when_disabled(self, file_scanner, temp_workspace):
        """Test that sensitive detection can be disabled"""
        (temp_workspace / ".env").write_text("API_KEY=secret123")

        config = {
            "patterns": ["*"],
            "check_sensitive": False
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        sensitive_findings = [f for f in result.findings if f.category == "sensitive_file"]
        assert len(sensitive_findings) == 0


@pytest.mark.asyncio
class TestFileScannerHashing:
    """Test file hashing functionality"""

    async def test_hash_calculation(self, file_scanner, temp_workspace):
        """Test SHA256 hash calculation"""
        # Create test file
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello World")

        config = {
            "patterns": ["*.txt"],
            "calculate_hashes": True
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"

        # Find the test.txt finding
        txt_findings = [f for f in result.findings if "test.txt" in f.file_path]
        assert len(txt_findings) > 0

        # Check that hash was calculated
        finding = txt_findings[0]
        assert finding.metadata.get("file_hash") is not None
        assert len(finding.metadata["file_hash"]) == 64  # SHA256 hex length

    async def test_no_hash_when_disabled(self, file_scanner, temp_workspace):
        """Test that hashing can be disabled"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello World")

        config = {
            "patterns": ["*.txt"],
            "calculate_hashes": False
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        txt_findings = [f for f in result.findings if "test.txt" in f.file_path]

        if len(txt_findings) > 0:
            finding = txt_findings[0]
            assert finding.metadata.get("file_hash") is None


@pytest.mark.asyncio
class TestFileScannerFileTypes:
    """Test file type detection"""

    async def test_detect_python_type(self, file_scanner, temp_workspace):
        """Test detection of Python file type"""
        (temp_workspace / "script.py").write_text("print('hello')")

        config = {"patterns": ["*.py"]}
        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        py_findings = [f for f in result.findings if "script.py" in f.file_path]
        assert len(py_findings) > 0
        assert "python" in py_findings[0].metadata["file_type"]

    async def test_detect_javascript_type(self, file_scanner, temp_workspace):
        """Test detection of JavaScript file type"""
        (temp_workspace / "app.js").write_text("console.log('hello')")

        config = {"patterns": ["*.js"]}
        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        js_findings = [f for f in result.findings if "app.js" in f.file_path]
        assert len(js_findings) > 0
        assert "javascript" in js_findings[0].metadata["file_type"]

    async def test_file_type_summary(self, file_scanner, temp_workspace):
        """Test that file type summary is generated"""
        (temp_workspace / "script.py").write_text("print('hello')")
        (temp_workspace / "app.js").write_text("console.log('hello')")
        (temp_workspace / "readme.txt").write_text("Documentation")

        config = {"patterns": ["*"]}
        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        assert "file_types" in result.summary
        assert len(result.summary["file_types"]) > 0


@pytest.mark.asyncio
class TestFileScannerSizeLimits:
    """Test file size handling"""

    async def test_skip_large_files(self, file_scanner, temp_workspace):
        """Test that large files are skipped"""
        # Create a "large" file
        large_file = temp_workspace / "large.txt"
        large_file.write_text("x" * 1000)

        config = {
            "patterns": ["*.txt"],
            "max_file_size": 500  # Set limit smaller than file
        }

        result = await file_scanner.execute(config, temp_workspace)

        # Should succeed but skip the large file
        assert result.status == "success"

        # The file should still be counted but not have a detailed finding
        assert result.summary["total_files"] > 0

    async def test_process_small_files(self, file_scanner, temp_workspace):
        """Test that small files are processed"""
        small_file = temp_workspace / "small.txt"
        small_file.write_text("small content")

        config = {
            "patterns": ["*.txt"],
            "max_file_size": 1048576  # 1MB
        }

        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        txt_findings = [f for f in result.findings if "small.txt" in f.file_path]
        assert len(txt_findings) > 0


@pytest.mark.asyncio
class TestFileScannerSummary:
    """Test result summary generation"""

    async def test_summary_structure(self, file_scanner, python_test_workspace):
        """Test that summary has correct structure"""
        config = {"patterns": ["*"]}
        result = await file_scanner.execute(config, python_test_workspace)

        assert result.status == "success"
        assert "total_files" in result.summary
        assert "total_size_bytes" in result.summary
        assert "file_types" in result.summary
        assert "patterns_scanned" in result.summary

        assert isinstance(result.summary["total_files"], int)
        assert isinstance(result.summary["total_size_bytes"], int)
        assert isinstance(result.summary["file_types"], dict)
        assert isinstance(result.summary["patterns_scanned"], list)

    async def test_summary_counts(self, file_scanner, temp_workspace):
        """Test that summary counts are accurate"""
        # Create known files
        (temp_workspace / "file1.py").write_text("content1")
        (temp_workspace / "file2.py").write_text("content2")
        (temp_workspace / "file3.txt").write_text("content3")

        config = {"patterns": ["*"]}
        result = await file_scanner.execute(config, temp_workspace)

        assert result.status == "success"
        assert result.summary["total_files"] == 3
        assert result.summary["total_size_bytes"] > 0
