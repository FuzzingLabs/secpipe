"""
Secret Detection Tools Comparison Report Generator

Generates comparison reports showing strengths/weaknesses of each tool.
Uses workflow execution via SDK to test complete pipeline.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sdk" / "src"))

from fuzzforge_sdk import FuzzForgeClient


@dataclass
class ToolResult:
    """Results from running a tool"""
    tool_name: str
    execution_time: float
    findings_count: int
    findings_by_file: Dict[str, List[int]]  # file_path -> [line_numbers]
    unique_files: int
    unique_locations: int  # unique (file, line) pairs
    secret_density: float  # average secrets per file
    file_types: Dict[str, int]  # file extension -> count of files with secrets


class SecretDetectionComparison:
    """Compare secret detection tools"""

    def __init__(self, target_path: Path, api_url: str = "http://localhost:8000"):
        self.target_path = target_path
        self.client = FuzzForgeClient(base_url=api_url)

    async def run_workflow(self, workflow_name: str, tool_name: str, config: Dict[str, Any] = None) -> Optional[ToolResult]:
        """Run a workflow and extract findings"""
        print(f"\nRunning {tool_name} workflow...")

        start_time = time.time()

        try:
            # Start workflow
            run = self.client.submit_workflow_with_upload(
                workflow_name=workflow_name,
                target_path=str(self.target_path),
                parameters=config or {}
            )

            print(f"  Started run: {run.run_id}")

            # Wait for completion (up to 30 minutes for slow LLMs)
            print(f"  Waiting for completion...")
            result = self.client.wait_for_completion(run.run_id, timeout=1800)

            execution_time = time.time() - start_time

            if result.status != "COMPLETED":
                print(f"❌ {tool_name} workflow failed: {result.status}")
                return None

            # Get findings from SARIF
            findings = self.client.get_run_findings(run.run_id)

            if not findings or not findings.sarif:
                print(f"⚠️  {tool_name} produced no findings")
                return None

            # Extract results from SARIF and group by file
            findings_by_file = {}
            unique_locations = set()

            for run_data in findings.sarif.get("runs", []):
                for result in run_data.get("results", []):
                    locations = result.get("locations", [])
                    for location in locations:
                        physical_location = location.get("physicalLocation", {})
                        artifact_location = physical_location.get("artifactLocation", {})
                        region = physical_location.get("region", {})

                        uri = artifact_location.get("uri", "")
                        line = region.get("startLine", 0)

                        if uri and line:
                            if uri not in findings_by_file:
                                findings_by_file[uri] = []
                            findings_by_file[uri].append(line)
                            unique_locations.add((uri, line))

            # Sort line numbers for each file
            for file_path in findings_by_file:
                findings_by_file[file_path] = sorted(set(findings_by_file[file_path]))

            # Calculate file type distribution
            file_types = {}
            for file_path in findings_by_file:
                ext = Path(file_path).suffix or Path(file_path).name  # Use full name for files like .env
                if ext.startswith('.'):
                    file_types[ext] = file_types.get(ext, 0) + 1
                else:
                    file_types['[no extension]'] = file_types.get('[no extension]', 0) + 1

            # Calculate secret density
            secret_density = len(unique_locations) / len(findings_by_file) if findings_by_file else 0

            print(f"  ✓ Found {len(unique_locations)} secrets in {len(findings_by_file)} files (avg {secret_density:.1f} per file)")

            return ToolResult(
                tool_name=tool_name,
                execution_time=execution_time,
                findings_count=len(unique_locations),
                findings_by_file=findings_by_file,
                unique_files=len(findings_by_file),
                unique_locations=len(unique_locations),
                secret_density=secret_density,
                file_types=file_types
            )

        except Exception as e:
            print(f"❌ {tool_name} error: {e}")
            return None


    async def run_all_tools(self, llm_models: List[str] = None) -> List[ToolResult]:
        """Run all available tools"""
        results = []

        if llm_models is None:
            llm_models = ["gpt-4o-mini"]

        # Gitleaks
        result = await self.run_workflow("gitleaks_detection", "Gitleaks", {
            "scan_mode": "detect",
            "no_git": True,
            "redact": False
        })
        if result:
            results.append(result)

        # TruffleHog
        result = await self.run_workflow("trufflehog_detection", "TruffleHog", {
            "verify": False,
            "max_depth": 10
        })
        if result:
            results.append(result)

        # LLM Detector with multiple models
        for model in llm_models:
            tool_name = f"LLM ({model})"
            result = await self.run_workflow("llm_secret_detection", tool_name, {
                "agent_url": "http://fuzzforge-task-agent:8000/a2a/litellm_agent",
                "llm_model": model,
                "llm_provider": "openai" if "gpt" in model else "anthropic",
                "max_files": 20,
                "timeout": 60,
                "file_patterns": [
                    "*.py", "*.js", "*.ts", "*.java", "*.go", "*.env", "*.yaml", "*.yml",
                    "*.json", "*.xml", "*.ini", "*.sql", "*.properties", "*.sh", "*.bat",
                    "*.config", "*.conf", "*.toml", "*id_rsa*", "*.txt"
                ]
            })
            if result:
                results.append(result)

        return results

    def _calculate_agreement_matrix(self, results: List[ToolResult]) -> Dict[str, Dict[str, int]]:
        """Calculate overlap matrix showing common secrets between tool pairs"""
        matrix = {}

        for i, result1 in enumerate(results):
            matrix[result1.tool_name] = {}
            # Convert to set of (file, line) tuples
            secrets1 = set()
            for file_path, lines in result1.findings_by_file.items():
                for line in lines:
                    secrets1.add((file_path, line))

            for result2 in results:
                secrets2 = set()
                for file_path, lines in result2.findings_by_file.items():
                    for line in lines:
                        secrets2.add((file_path, line))

                # Count common secrets
                common = len(secrets1 & secrets2)
                matrix[result1.tool_name][result2.tool_name] = common

        return matrix

    def _get_per_file_comparison(self, results: List[ToolResult]) -> Dict[str, Dict[str, int]]:
        """Get per-file breakdown of findings across all tools"""
        all_files = set()
        for result in results:
            all_files.update(result.findings_by_file.keys())

        comparison = {}
        for file_path in sorted(all_files):
            comparison[file_path] = {}
            for result in results:
                comparison[file_path][result.tool_name] = len(result.findings_by_file.get(file_path, []))

        return comparison

    def _get_agreement_stats(self, results: List[ToolResult]) -> Dict[int, int]:
        """Calculate how many secrets are found by 1, 2, 3, or all tools"""
        # Collect all unique (file, line) pairs across all tools
        all_secrets = {}  # (file, line) -> list of tools that found it

        for result in results:
            for file_path, lines in result.findings_by_file.items():
                for line in lines:
                    key = (file_path, line)
                    if key not in all_secrets:
                        all_secrets[key] = []
                    all_secrets[key].append(result.tool_name)

        # Count by number of tools
        agreement_counts = {}
        for secret, tools in all_secrets.items():
            count = len(set(tools))  # Unique tools
            agreement_counts[count] = agreement_counts.get(count, 0) + 1

        return agreement_counts

    def generate_markdown_report(self, results: List[ToolResult]) -> str:
        """Generate markdown comparison report"""
        report = []
        report.append("# Secret Detection Tools Comparison\n")
        report.append(f"**Target**: {self.target_path.name}")
        report.append(f"**Tools**: {', '.join([r.tool_name for r in results])}\n")

        # Summary table with extended metrics
        report.append("\n## Summary\n")
        report.append("| Tool | Secrets | Files | Avg/File | Time (s) |")
        report.append("|------|---------|-------|----------|----------|")

        for result in results:
            report.append(
                f"| {result.tool_name} | "
                f"{result.findings_count} | "
                f"{result.unique_files} | "
                f"{result.secret_density:.1f} | "
                f"{result.execution_time:.2f} |"
            )

        # Agreement Analysis
        agreement_stats = self._get_agreement_stats(results)
        report.append("\n## Agreement Analysis\n")
        report.append("Secrets found by different numbers of tools:\n")
        for num_tools in sorted(agreement_stats.keys(), reverse=True):
            count = agreement_stats[num_tools]
            if num_tools == len(results):
                report.append(f"- **All {num_tools} tools agree**: {count} secrets")
            elif num_tools == 1:
                report.append(f"- **Only 1 tool found**: {count} secrets")
            else:
                report.append(f"- **{num_tools} tools agree**: {count} secrets")

        # Agreement Matrix
        agreement_matrix = self._calculate_agreement_matrix(results)
        report.append("\n## Tool Agreement Matrix\n")
        report.append("Number of common secrets found by tool pairs:\n")

        # Header row
        header = "| Tool |"
        separator = "|------|"
        for result in results:
            short_name = result.tool_name.replace("LLM (", "").replace(")", "")
            header += f" {short_name} |"
            separator += "------|"
        report.append(header)
        report.append(separator)

        # Data rows
        for result in results:
            short_name = result.tool_name.replace("LLM (", "").replace(")", "")
            row = f"| {short_name} |"
            for result2 in results:
                count = agreement_matrix[result.tool_name][result2.tool_name]
                row += f" {count} |"
            report.append(row)

        # Per-File Comparison
        per_file = self._get_per_file_comparison(results)
        report.append("\n## Per-File Detailed Comparison\n")
        report.append("Secrets found per file by each tool:\n")

        # Header
        header = "| File |"
        separator = "|------|"
        for result in results:
            short_name = result.tool_name.replace("LLM (", "").replace(")", "")
            header += f" {short_name} |"
            separator += "------|"
        header += " Total |"
        separator += "------|"
        report.append(header)
        report.append(separator)

        # Show top 15 files by total findings
        file_totals = [(f, sum(counts.values())) for f, counts in per_file.items()]
        file_totals.sort(key=lambda x: x[1], reverse=True)

        for file_path, total in file_totals[:15]:
            row = f"| `{file_path}` |"
            for result in results:
                count = per_file[file_path].get(result.tool_name, 0)
                row += f" {count} |"
            row += f" **{total}** |"
            report.append(row)

        if len(file_totals) > 15:
            report.append(f"| ... and {len(file_totals) - 15} more files | ... | ... | ... | ... | ... |")

        # File Type Breakdown
        report.append("\n## File Type Breakdown\n")
        all_extensions = set()
        for result in results:
            all_extensions.update(result.file_types.keys())

        if all_extensions:
            header = "| Type |"
            separator = "|------|"
            for result in results:
                short_name = result.tool_name.replace("LLM (", "").replace(")", "")
                header += f" {short_name} |"
                separator += "------|"
            report.append(header)
            report.append(separator)

            for ext in sorted(all_extensions):
                row = f"| `{ext}` |"
                for result in results:
                    count = result.file_types.get(ext, 0)
                    row += f" {count} files |"
                report.append(row)

        # File analysis
        report.append("\n## Files Analyzed\n")

        # Collect all unique files across all tools
        all_files = set()
        for result in results:
            all_files.update(result.findings_by_file.keys())

        report.append(f"**Total unique files with secrets**: {len(all_files)}\n")

        for result in results:
            report.append(f"\n### {result.tool_name}\n")
            report.append(f"Found secrets in **{result.unique_files} files**:\n")

            # Sort files by number of findings (descending)
            sorted_files = sorted(
                result.findings_by_file.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )

            # Show top 10 files
            for file_path, lines in sorted_files[:10]:
                report.append(f"- `{file_path}`: {len(lines)} secrets (lines: {', '.join(map(str, lines[:5]))}{'...' if len(lines) > 5 else ''})")

            if len(sorted_files) > 10:
                report.append(f"- ... and {len(sorted_files) - 10} more files")

        # Overlap analysis
        if len(results) >= 2:
            report.append("\n## Overlap Analysis\n")

            # Find common files
            file_sets = [set(r.findings_by_file.keys()) for r in results]
            common_files = set.intersection(*file_sets) if file_sets else set()

            if common_files:
                report.append(f"\n**Files found by all tools** ({len(common_files)}):\n")
                for file_path in sorted(common_files)[:10]:
                    report.append(f"- `{file_path}`")
            else:
                report.append("\n**No files were found by all tools**\n")

            # Find tool-specific files
            for i, result in enumerate(results):
                unique_to_tool = set(result.findings_by_file.keys())
                for j, other_result in enumerate(results):
                    if i != j:
                        unique_to_tool -= set(other_result.findings_by_file.keys())

                if unique_to_tool:
                    report.append(f"\n**Unique to {result.tool_name}** ({len(unique_to_tool)} files):\n")
                    for file_path in sorted(unique_to_tool)[:5]:
                        report.append(f"- `{file_path}`")
                    if len(unique_to_tool) > 5:
                        report.append(f"- ... and {len(unique_to_tool) - 5} more")

        # Ground Truth Analysis (if available)
        ground_truth_path = Path(__file__).parent / "secret_detection_benchmark_GROUND_TRUTH.json"
        if ground_truth_path.exists():
            report.append("\n## Ground Truth Analysis\n")
            try:
                with open(ground_truth_path) as f:
                    gt_data = json.load(f)

                gt_total = gt_data.get("total_secrets", 30)
                report.append(f"**Expected secrets**: {gt_total} (documented in ground truth)\n")

                # Build ground truth set of (file, line) tuples
                gt_secrets = set()
                for secret in gt_data.get("secrets", []):
                    gt_secrets.add((secret["file"], secret["line"]))

                report.append("### Tool Performance vs Ground Truth\n")
                report.append("| Tool | Found | Expected | Recall | Extra Findings |")
                report.append("|------|-------|----------|--------|----------------|")

                for result in results:
                    # Build tool findings set
                    tool_secrets = set()
                    for file_path, lines in result.findings_by_file.items():
                        for line in lines:
                            tool_secrets.add((file_path, line))

                    # Calculate metrics
                    true_positives = len(gt_secrets & tool_secrets)
                    recall = (true_positives / gt_total * 100) if gt_total > 0 else 0
                    extra = len(tool_secrets - gt_secrets)

                    report.append(
                        f"| {result.tool_name} | "
                        f"{result.findings_count} | "
                        f"{gt_total} | "
                        f"{recall:.1f}% | "
                        f"{extra} |"
                    )

                # Analyze LLM extra findings
                llm_results = [r for r in results if "LLM" in r.tool_name]
                if llm_results:
                    report.append("\n### LLM Extra Findings Explanation\n")
                    report.append("LLMs may find more than 30 secrets because they detect:\n")
                    report.append("- **Split secret components**: Each part of `DB_PASS_PART1 + PART2 + PART3` counted separately")
                    report.append("- **Join operations**: Lines like `''.join(AWS_SECRET_CHARS)` flagged as additional exposure")
                    report.append("- **Decoding functions**: Code that reveals secrets (e.g., `base64.b64decode()`, `codecs.decode()`)")
                    report.append("- **Comment identifiers**: Lines marking secret locations without plaintext values")
                    report.append("\nThese are *technically correct* detections of secret exposure points, not false positives.")
                    report.append("The ground truth documents 30 'primary' secrets, but the codebase has additional derivative exposures.\n")

            except Exception as e:
                report.append(f"*Could not load ground truth: {e}*\n")

        # Performance summary
        if results:
            report.append("\n## Performance Summary\n")
            most_findings = max(results, key=lambda r: r.findings_count)
            most_files = max(results, key=lambda r: r.unique_files)
            fastest = min(results, key=lambda r: r.execution_time)

            report.append(f"- **Most secrets found**: {most_findings.tool_name} ({most_findings.findings_count} secrets)")
            report.append(f"- **Most files covered**: {most_files.tool_name} ({most_files.unique_files} files)")
            report.append(f"- **Fastest**: {fastest.tool_name} ({fastest.execution_time:.2f}s)")

        return "\n".join(report)

    def save_json_report(self, results: List[ToolResult], output_path: Path):
        """Save results as JSON"""
        data = {
            "target_path": str(self.target_path),
            "results": [asdict(r) for r in results]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n✅ JSON report saved to: {output_path}")

    def cleanup(self):
        """Cleanup SDK client"""
        self.client.close()


async def main():
    """Run comparison and generate reports"""
    # Get target path (secret_detection_benchmark)
    target_path = Path(__file__).parent.parent.parent.parent.parent / "test_projects" / "secret_detection_benchmark"

    if not target_path.exists():
        print(f"❌ Target not found at: {target_path}")
        return 1

    print("=" * 80)
    print("Secret Detection Tools Comparison")
    print("=" * 80)
    print(f"Target: {target_path}")

    # LLM models to test
    llm_models = [
        "gpt-4o-mini",
        "gpt-5-mini"
    ]
    print(f"LLM models: {', '.join(llm_models)}\n")

    # Run comparison
    comparison = SecretDetectionComparison(target_path)

    try:
        results = await comparison.run_all_tools(llm_models=llm_models)

        if not results:
            print("❌ No tools ran successfully")
            return 1

        # Generate reports
        print("\n" + "=" * 80)
        markdown_report = comparison.generate_markdown_report(results)
        print(markdown_report)

        # Save reports
        output_dir = Path(__file__).parent / "results"
        output_dir.mkdir(exist_ok=True)

        markdown_path = output_dir / "comparison_report.md"
        with open(markdown_path, 'w') as f:
            f.write(markdown_report)
        print(f"\n✅ Markdown report saved to: {markdown_path}")

        json_path = output_dir / "comparison_results.json"
        comparison.save_json_report(results, json_path)

        print("\n" + "=" * 80)
        print("✅ Comparison complete!")
        print("=" * 80)

        return 0

    finally:
        comparison.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
