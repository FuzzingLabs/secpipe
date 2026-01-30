"""
Secret Detection Tool Comparison Benchmark

Compares Gitleaks, TruffleHog, and LLM-based detection
on the vulnerable_app ground truth dataset via workflow execution.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sdk" / "src"))

from fuzzforge_sdk import FuzzForgeClient
from benchmarks.category_configs import ModuleCategory, get_threshold


@pytest.fixture
def target_path():
    """Path to vulnerable_app"""
    path = Path(__file__).parent.parent.parent.parent.parent / "test_projects" / "vulnerable_app"
    assert path.exists(), f"Target not found: {path}"
    return path


@pytest.fixture
def ground_truth(target_path):
    """Load ground truth data"""
    metadata_file = target_path / "SECRETS_GROUND_TRUTH.json"
    assert metadata_file.exists(), f"Ground truth not found: {metadata_file}"

    with open(metadata_file) as f:
        return json.load(f)


@pytest.fixture
def sdk_client():
    """FuzzForge SDK client"""
    client = FuzzForgeClient(base_url="http://localhost:8000")
    yield client
    client.close()


def calculate_metrics(sarif_results: List[Dict], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    """Calculate precision, recall, and F1 score"""

    # Extract expected secrets from ground truth
    expected_secrets = set()
    for file_info in ground_truth["files"]:
        if "secrets" in file_info:
            for secret in file_info["secrets"]:
                expected_secrets.add((file_info["filename"], secret["line"]))

    # Extract detected secrets from SARIF
    detected_secrets = set()
    for result in sarif_results:
        locations = result.get("locations", [])
        for location in locations:
            physical_location = location.get("physicalLocation", {})
            artifact_location = physical_location.get("artifactLocation", {})
            region = physical_location.get("region", {})

            uri = artifact_location.get("uri", "")
            line = region.get("startLine", 0)

            if uri and line:
                file_path = Path(uri)
                filename = file_path.name
                detected_secrets.add((filename, line))
                # Also try with relative path
                if len(file_path.parts) > 1:
                    rel_path = str(Path(*file_path.parts[-2:]))
                    detected_secrets.add((rel_path, line))

    # Calculate metrics
    true_positives = len(expected_secrets & detected_secrets)
    false_positives = len(detected_secrets - expected_secrets)
    false_negatives = len(expected_secrets - detected_secrets)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }


class TestSecretDetectionComparison:
    """Compare all secret detection tools"""

    @pytest.mark.benchmark(group="secret_detection")
    def test_gitleaks_workflow(self, benchmark, sdk_client, target_path, ground_truth):
        """Benchmark Gitleaks workflow accuracy and performance"""

        def run_gitleaks():
            run = sdk_client.submit_workflow_with_upload(
                workflow_name="gitleaks_detection",
                target_path=str(target_path),
                parameters={
                    "scan_mode": "detect",
                    "no_git": True,
                    "redact": False
                }
            )

            result = sdk_client.wait_for_completion(run.run_id, timeout=300)
            assert result.status == "completed", f"Workflow failed: {result.status}"

            findings = sdk_client.get_run_findings(run.run_id)
            assert findings and findings.sarif, "No findings returned"

            return findings

        findings = benchmark(run_gitleaks)

        # Extract SARIF results
        sarif_results = []
        for run_data in findings.sarif.get("runs", []):
            sarif_results.extend(run_data.get("results", []))

        # Calculate metrics
        metrics = calculate_metrics(sarif_results, ground_truth)

        # Log results
        print(f"\n=== Gitleaks Workflow Results ===")
        print(f"Precision: {metrics['precision']:.2%}")
        print(f"Recall: {metrics['recall']:.2%}")
        print(f"F1 Score: {metrics['f1']:.2%}")
        print(f"True Positives: {metrics['true_positives']}")
        print(f"False Positives: {metrics['false_positives']}")
        print(f"False Negatives: {metrics['false_negatives']}")
        print(f"Findings Count: {len(sarif_results)}")

        # Assert meets thresholds
        min_precision = get_threshold(ModuleCategory.SECRET_DETECTION, "min_precision")
        min_recall = get_threshold(ModuleCategory.SECRET_DETECTION, "min_recall")

        assert metrics['precision'] >= min_precision, \
            f"Precision {metrics['precision']:.2%} below threshold {min_precision:.2%}"
        assert metrics['recall'] >= min_recall, \
            f"Recall {metrics['recall']:.2%} below threshold {min_recall:.2%}"

    @pytest.mark.benchmark(group="secret_detection")
    def test_trufflehog_workflow(self, benchmark, sdk_client, target_path, ground_truth):
        """Benchmark TruffleHog workflow accuracy and performance"""

        def run_trufflehog():
            run = sdk_client.submit_workflow_with_upload(
                workflow_name="trufflehog_detection",
                target_path=str(target_path),
                parameters={
                    "verify": False,
                    "max_depth": 10
                }
            )

            result = sdk_client.wait_for_completion(run.run_id, timeout=300)
            assert result.status == "completed", f"Workflow failed: {result.status}"

            findings = sdk_client.get_run_findings(run.run_id)
            assert findings and findings.sarif, "No findings returned"

            return findings

        findings = benchmark(run_trufflehog)

        sarif_results = []
        for run_data in findings.sarif.get("runs", []):
            sarif_results.extend(run_data.get("results", []))

        metrics = calculate_metrics(sarif_results, ground_truth)

        print(f"\n=== TruffleHog Workflow Results ===")
        print(f"Precision: {metrics['precision']:.2%}")
        print(f"Recall: {metrics['recall']:.2%}")
        print(f"F1 Score: {metrics['f1']:.2%}")
        print(f"True Positives: {metrics['true_positives']}")
        print(f"False Positives: {metrics['false_positives']}")
        print(f"False Negatives: {metrics['false_negatives']}")
        print(f"Findings Count: {len(sarif_results)}")

        min_precision = get_threshold(ModuleCategory.SECRET_DETECTION, "min_precision")
        min_recall = get_threshold(ModuleCategory.SECRET_DETECTION, "min_recall")

        assert metrics['precision'] >= min_precision
        assert metrics['recall'] >= min_recall

    @pytest.mark.benchmark(group="secret_detection")
    @pytest.mark.parametrize("model", [
        "gpt-4o-mini",
        "gpt-4o",
        "claude-3-5-sonnet-20241022"
    ])
    def test_llm_workflow(self, benchmark, sdk_client, target_path, ground_truth, model):
        """Benchmark LLM workflow with different models"""

        def run_llm():
            provider = "openai" if "gpt" in model else "anthropic"

            run = sdk_client.submit_workflow_with_upload(
                workflow_name="llm_secret_detection",
                target_path=str(target_path),
                parameters={
                    "agent_url": "http://fuzzforge-task-agent:8000/a2a/litellm_agent",
                    "llm_model": model,
                    "llm_provider": provider,
                    "max_files": 20,
                    "timeout": 60
                }
            )

            result = sdk_client.wait_for_completion(run.run_id, timeout=300)
            assert result.status == "completed", f"Workflow failed: {result.status}"

            findings = sdk_client.get_run_findings(run.run_id)
            assert findings and findings.sarif, "No findings returned"

            return findings

        findings = benchmark(run_llm)

        sarif_results = []
        for run_data in findings.sarif.get("runs", []):
            sarif_results.extend(run_data.get("results", []))

        metrics = calculate_metrics(sarif_results, ground_truth)

        print(f"\n=== LLM ({model}) Workflow Results ===")
        print(f"Precision: {metrics['precision']:.2%}")
        print(f"Recall: {metrics['recall']:.2%}")
        print(f"F1 Score: {metrics['f1']:.2%}")
        print(f"True Positives: {metrics['true_positives']}")
        print(f"False Positives: {metrics['false_positives']}")
        print(f"False Negatives: {metrics['false_negatives']}")
        print(f"Findings Count: {len(sarif_results)}")


class TestSecretDetectionPerformance:
    """Performance benchmarks for each tool"""

    @pytest.mark.benchmark(group="secret_detection")
    def test_gitleaks_performance(self, benchmark, sdk_client, target_path):
        """Benchmark Gitleaks workflow execution speed"""

        def run():
            run = sdk_client.submit_workflow_with_upload(
                workflow_name="gitleaks_detection",
                target_path=str(target_path),
                parameters={"scan_mode": "detect", "no_git": True}
            )
            result = sdk_client.wait_for_completion(run.run_id, timeout=300)
            return result

        result = benchmark(run)

        max_time = get_threshold(ModuleCategory.SECRET_DETECTION, "max_execution_time_small")
        # Note: Workflow execution time includes orchestration overhead
        # so we allow 2x the module threshold
        assert result.execution_time < max_time * 2

    @pytest.mark.benchmark(group="secret_detection")
    def test_trufflehog_performance(self, benchmark, sdk_client, target_path):
        """Benchmark TruffleHog workflow execution speed"""

        def run():
            run = sdk_client.submit_workflow_with_upload(
                workflow_name="trufflehog_detection",
                target_path=str(target_path),
                parameters={"verify": False}
            )
            result = sdk_client.wait_for_completion(run.run_id, timeout=300)
            return result

        result = benchmark(run)

        max_time = get_threshold(ModuleCategory.SECRET_DETECTION, "max_execution_time_small")
        assert result.execution_time < max_time * 2
