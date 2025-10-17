# SARIF Format

FuzzForge uses the Static Analysis Results Interchange Format (SARIF) as the standardized output format for all security analysis results. SARIF provides a consistent, machine-readable format that enables tool interoperability and comprehensive result analysis.

## What is SARIF?

### Overview

SARIF (Static Analysis Results Interchange Format) is an OASIS-approved standard (SARIF 2.1.0) designed to standardize the output of static analysis tools. FuzzForge extends this standard to cover dynamic analysis, secret detection, infrastructure analysis, and fuzzing results.

### Key Benefits

- **Standardization**: Consistent format across all security tools and workflows
- **Interoperability**: Integration with existing security tools and platforms
- **Rich Metadata**: Comprehensive information about findings, tools, and analysis runs
- **Tool Agnostic**: Works with any security tool that produces structured results
- **IDE Integration**: Native support in modern development environments

### SARIF Structure

```json
{
  "version": "2.1.0",
  "schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "tool": { /* Tool information */ },
      "invocations": [ /* How the tool was run */ ],
      "artifacts": [ /* Files analyzed */ ],
      "results": [ /* Security findings */ ]
    }
  ]
}
```

## FuzzForge SARIF Implementation

### Run Structure

Each FuzzForge workflow produces a SARIF "run" containing:

```json
{
  "tool": {
    "driver": {
      "name": "FuzzForge",
      "version": "1.0.0",
      "informationUri": "https://github.com/FuzzingLabs/fuzzforge_ai",
      "organization": "FuzzingLabs",
      "rules": [ /* Security rules applied */ ]
    },
    "extensions": [
      {
        "name": "semgrep",
        "version": "1.45.0",
        "rules": [ /* Semgrep-specific rules */ ]
      }
    ]
  },
  "invocations": [
    {
      "executionSuccessful": true,
      "startTimeUtc": "2025-09-25T12:00:00.000Z",
      "endTimeUtc": "2025-09-25T12:05:30.000Z",
      "workingDirectory": {
        "uri": "file:///app/target/"
      },
      "commandLine": "python -m toolbox.workflows.static_analysis",
      "environmentVariables": {
        "WORKFLOW_TYPE": "static_analysis_scan"
      }
    }
  ]
}
```

### Result Structure

Each security finding is represented as a SARIF result:

```json
{
  "ruleId": "semgrep.security.audit.sqli.pg-sqli",
  "ruleIndex": 42,
  "level": "error",
  "message": {
    "text": "Potential SQL injection vulnerability detected"
  },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": {
          "uri": "src/database/queries.py",
          "uriBaseId": "SRCROOT"
        },
        "region": {
          "startLine": 156,
          "startColumn": 20,
          "endLine": 156,
          "endColumn": 45,
          "snippet": {
            "text": "cursor.execute(query)"
          }
        }
      }
    }
  ],
  "properties": {
    "tool": "semgrep",
    "confidence": "high",
    "severity": "high",
    "cwe": ["CWE-89"],
    "owasp": ["A03:2021"],
    "references": [
      "https://owasp.org/Top10/A03_2021-Injection/"
    ]
  }
}
```

## Finding Categories and Severity

### Severity Levels

FuzzForge maps tool-specific severity levels to SARIF standard levels:

#### SARIF Level Mapping
- **error**: Critical and High severity findings
- **warning**: Medium severity findings
- **note**: Low severity findings
- **info**: Informational findings

#### Extended Severity Properties
```json
{
  "properties": {
    "severity": "high",           // FuzzForge severity
    "confidence": "medium",       // Tool confidence
    "exploitability": "high",     // Likelihood of exploitation
    "impact": "data_breach"       // Potential impact
  }
}
```

### Vulnerability Classification

#### CWE (Common Weakness Enumeration)
```json
{
  "properties": {
    "cwe": ["CWE-89", "CWE-79"],
    "cwe_category": "Injection"
  }
}
```

#### OWASP Top 10 Mapping
```json
{
  "properties": {
    "owasp": ["A03:2021", "A06:2021"],
    "owasp_category": "Injection"
  }
}
```

#### Tool-Specific Classifications
```json
{
  "properties": {
    "tool_category": "security",
    "rule_type": "semantic_grep",
    "finding_type": "sql_injection"
  }
}
```

## Multi-Tool Result Aggregation

### Tool Extension Model

FuzzForge aggregates results from multiple tools using SARIF's extension model:

```json
{
  "tool": {
    "driver": {
      "name": "FuzzForge",
      "version": "1.0.0"
    },
    "extensions": [
      {
        "name": "semgrep",
        "version": "1.45.0",
        "guid": "semgrep-extension-guid"
      },
      {
        "name": "bandit",
        "version": "1.7.5",
        "guid": "bandit-extension-guid"
      }
    ]
  }
}
```

### Result Correlation

#### Cross-Tool Finding Correlation
```json
{
  "ruleId": "fuzzforge.correlation.sql-injection",
  "level": "error",
  "message": {
    "text": "SQL injection vulnerability confirmed by multiple tools"
  },
  "locations": [ /* Primary location */ ],
  "relatedLocations": [ /* Additional contexts */ ],
  "properties": {
    "correlation_id": "corr-001",
    "confirming_tools": ["semgrep", "bandit"],
    "confidence_score": 0.95,
    "aggregated_severity": "critical"
  }
}
```

#### Finding Relationships
```json
{
  "ruleId": "semgrep.security.audit.xss.direct-use-of-jinja2",
  "properties": {
    "related_findings": [
      {
        "correlation_type": "same_vulnerability_class",
        "related_rule": "bandit.B703",
        "relationship": "confirms"
      },
      {
        "correlation_type": "attack_chain",
        "related_rule": "nuclei.xss.reflected",
        "relationship": "exploits"
      }
    ]
  }
}
```

## Workflow-Specific Extensions

### Static Analysis Results
```json
{
  "properties": {
    "analysis_type": "static",
    "language": "python",
    "complexity_score": 3.2,
    "coverage": {
      "lines_analyzed": 15420,
      "functions_analyzed": 892,
      "classes_analyzed": 156
    }
  }
}
```

### Dynamic Analysis Results
```json
{
  "properties": {
    "analysis_type": "dynamic",
    "test_method": "web_application_scan",
    "target_url": "https://example.com",
    "http_method": "POST",
    "request_payload": "user_input=<script>alert(1)</script>",
    "response_code": 200,
    "exploitation_proof": "alert_box_displayed"
  }
}
```

### Secret Detection Results
```json
{
  "properties": {
    "analysis_type": "secret_detection",
    "secret_type": "api_key",
    "entropy_score": 4.2,
    "commit_hash": "abc123def456",
    "commit_date": "2025-09-20T10:30:00Z",
    "author": "developer@example.com",
    "exposure_duration": "30_days"
  }
}
```

### Infrastructure Analysis Results
```json
{
  "properties": {
    "analysis_type": "infrastructure",
    "resource_type": "docker_container",
    "policy_violation": "privileged_container",
    "compliance_framework": ["CIS", "NIST"],
    "remediation_effort": "low",
    "deployment_risk": "high"
  }
}
```

### Fuzzing Results
```json
{
  "properties": {
    "analysis_type": "fuzzing",
    "fuzzer": "afl++",
    "crash_type": "segmentation_fault",
    "crash_address": "0x7fff8b2a1000",
    "exploitability": "likely_exploitable",
    "test_case": "base64:SGVsbG8gV29ybGQ=",
    "coverage_achieved": "85%"
  }
}
```

## SARIF Processing and Analysis

### Result Filtering

#### Severity-Based Filtering
```python
def filter_by_severity(sarif_results, min_severity="medium"):
    """Filter SARIF results by minimum severity level"""
    severity_order = {"info": 0, "note": 1, "warning": 2, "error": 3}
    min_level = severity_order.get(min_severity, 1)

    filtered_results = []
    for result in sarif_results["runs"][0]["results"]:
        result_level = severity_order.get(result.get("level", "note"), 1)
        if result_level >= min_level:
            filtered_results.append(result)

    return filtered_results
```

#### Rule-Based Filtering
```python
def filter_by_rules(sarif_results, rule_patterns):
    """Filter results by rule ID patterns"""
    import re

    filtered_results = []
    for result in sarif_results["runs"][0]["results"]:
        rule_id = result.get("ruleId", "")
        for pattern in rule_patterns:
            if re.match(pattern, rule_id):
                filtered_results.append(result)
                break

    return filtered_results
```

### Statistical Analysis

#### Severity Distribution
```python
def analyze_severity_distribution(sarif_results):
    """Analyze distribution of findings by severity"""
    distribution = {"error": 0, "warning": 0, "note": 0, "info": 0}

    for result in sarif_results["runs"][0]["results"]:
        level = result.get("level", "note")
        distribution[level] += 1

    return distribution
```

#### Tool Coverage Analysis
```python
def analyze_tool_coverage(sarif_results):
    """Analyze which tools contributed findings"""
    tool_stats = {}

    for result in sarif_results["runs"][0]["results"]:
        tool = result.get("properties", {}).get("tool", "unknown")
        if tool not in tool_stats:
            tool_stats[tool] = {"count": 0, "severities": {"error": 0, "warning": 0, "note": 0, "info": 0}}

        tool_stats[tool]["count"] += 1
        level = result.get("level", "note")
        tool_stats[tool]["severities"][level] += 1

    return tool_stats
```

## SARIF Export and Integration

### Export Formats

#### JSON Export
```python
def export_sarif_json(sarif_results, output_path):
    """Export SARIF results as JSON"""
    import json

    with open(output_path, 'w') as f:
        json.dump(sarif_results, f, indent=2, ensure_ascii=False)
```

#### CSV Export for Spreadsheets
```python
def export_sarif_csv(sarif_results, output_path):
    """Export SARIF results as CSV for spreadsheet analysis"""
    import csv

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Rule ID', 'Severity', 'Message', 'File', 'Line', 'Tool'])

        for result in sarif_results["runs"][0]["results"]:
            rule_id = result.get("ruleId", "unknown")
            level = result.get("level", "note")
            message = result.get("message", {}).get("text", "")
            tool = result.get("properties", {}).get("tool", "unknown")

            for location in result.get("locations", []):
                physical_location = location.get("physicalLocation", {})
                file_path = physical_location.get("artifactLocation", {}).get("uri", "")
                line = physical_location.get("region", {}).get("startLine", "")

                writer.writerow([rule_id, level, message, file_path, line, tool])
```

### IDE Integration

#### Visual Studio Code
SARIF files can be opened directly in VS Code with the SARIF extension:

```json
{
  "recommendations": ["ms-sarif.sarif-viewer"],
  "sarif.viewer.connectToGitHub": true,
  "sarif.viewer.showResultsInExplorer": true
}
```

#### GitHub Integration
GitHub automatically processes SARIF files uploaded through Actions:

```yaml
- name: Upload SARIF results
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: fuzzforge-results.sarif
    category: security-analysis
```

### API Integration

#### SARIF Result Access
```python
# Example: Accessing SARIF results via FuzzForge API
async with FuzzForgeClient() as client:
    result = await client.get_workflow_result(run_id)

    # Access SARIF data
    sarif_data = result["sarif"]
    findings = sarif_data["runs"][0]["results"]

    # Filter critical findings
    critical_findings = [
        f for f in findings
        if f.get("level") == "error" and
           f.get("properties", {}).get("severity") == "critical"
    ]
```

## SARIF Validation and Quality

### Schema Validation
```python
import jsonschema
import requests

def validate_sarif(sarif_data):
    """Validate SARIF data against official schema"""
    schema_url = "https://json.schemastore.org/sarif-2.1.0.json"
    schema = requests.get(schema_url).json()

    try:
        jsonschema.validate(sarif_data, schema)
        return True, "Valid SARIF 2.1.0 format"
    except jsonschema.ValidationError as e:
        return False, f"SARIF validation error: {e.message}"
```

### Quality Metrics
```python
def calculate_sarif_quality_metrics(sarif_data):
    """Calculate quality metrics for SARIF results"""
    results = sarif_data["runs"][0]["results"]

    metrics = {
        "total_findings": len(results),
        "findings_with_location": len([r for r in results if r.get("locations")]),
        "findings_with_message": len([r for r in results if r.get("message", {}).get("text")]),
        "findings_with_remediation": len([r for r in results if r.get("fixes")]),
        "unique_rules": len(set(r.get("ruleId") for r in results)),
        "coverage_percentage": calculate_coverage(sarif_data)
    }

    metrics["quality_score"] = (
        metrics["findings_with_location"] / max(metrics["total_findings"], 1) * 0.3 +
        metrics["findings_with_message"] / max(metrics["total_findings"], 1) * 0.3 +
        metrics["findings_with_remediation"] / max(metrics["total_findings"], 1) * 0.2 +
        min(metrics["coverage_percentage"] / 100, 1.0) * 0.2
    )

    return metrics
```

## Advanced SARIF Features

### Fixes and Remediation
```json
{
  "ruleId": "semgrep.security.audit.sqli.pg-sqli",
  "fixes": [
    {
      "description": {
        "text": "Use parameterized queries to prevent SQL injection"
      },
      "artifactChanges": [
        {
          "artifactLocation": {
            "uri": "src/database/queries.py"
          },
          "replacements": [
            {
              "deletedRegion": {
                "startLine": 156,
                "startColumn": 20,
                "endLine": 156,
                "endColumn": 45
              },
              "insertedContent": {
                "text": "cursor.execute(query, params)"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Code Flows for Complex Vulnerabilities
```json
{
  "ruleId": "dataflow.taint.sql-injection",
  "codeFlows": [
    {
      "message": {
        "text": "Tainted data flows from user input to SQL query"
      },
      "threadFlows": [
        {
          "locations": [
            {
              "location": {
                "physicalLocation": {
                  "artifactLocation": {"uri": "src/api/handlers.py"},
                  "region": {"startLine": 45}
                }
              },
              "state": {"source": "user_input"},
              "nestingLevel": 0
            },
            {
              "location": {
                "physicalLocation": {
                  "artifactLocation": {"uri": "src/database/queries.py"},
                  "region": {"startLine": 156}
                }
              },
              "state": {"sink": "sql_query"},
              "nestingLevel": 0
            }
          ]
        }
      ]
    }
  ]
}
```

---

## SARIF Best Practices

### Result Quality
- **Precise Locations**: Always include accurate file paths and line numbers
- **Clear Messages**: Write descriptive, actionable finding messages
- **Remediation Guidance**: Include fix suggestions when possible
- **Severity Consistency**: Use consistent severity mappings across tools

### Performance
- **Efficient Processing**: Process SARIF results efficiently for large result sets
- **Streaming**: Use streaming for very large SARIF files
- **Caching**: Cache processed results for faster repeated access
- **Compression**: Compress SARIF files for storage and transmission

### Integration
- **Tool Interoperability**: Ensure SARIF compatibility with existing tools
- **Standard Compliance**: Follow SARIF 2.1.0 specification precisely
- **Extension Documentation**: Document any custom extensions clearly
- **Version Management**: Handle SARIF schema version differences
