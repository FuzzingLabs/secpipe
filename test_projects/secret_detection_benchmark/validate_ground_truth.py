#!/usr/bin/env python3
"""
Validate secret detection tool results against ground truth
"""
import json
import argparse
from pathlib import Path
from typing import Set, Tuple

def load_ground_truth(ground_truth_file: Path) -> Set[Tuple[str, int]]:
    """Load ground truth secrets as set of (file, line) tuples"""
    with open(ground_truth_file) as f:
        data = json.load(f)

    secrets = set()
    for secret in data["secrets"]:
        secrets.add((secret["file"], secret["line"]))

    return secrets

def load_tool_results(results_file: Path) -> Set[Tuple[str, int]]:
    """Load tool results as set of (file, line) tuples"""
    with open(results_file) as f:
        data = json.load(f)

    findings = set()
    # Assume SARIF format or custom format with findings_by_file
    if "findings_by_file" in data:
        for file_path, lines in data["findings_by_file"].items():
            for line in lines:
                findings.add((file_path, line))

    return findings

def calculate_metrics(ground_truth: Set, detected: Set):
    """Calculate precision, recall, and F1 score"""
    tp = len(ground_truth & detected)  # True positives
    fp = len(detected - ground_truth)  # False positives
    fn = len(ground_truth - detected)  # False negatives

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision * 100,
        "recall": recall * 100,
        "f1_score": f1 * 100
    }

def main():
    parser = argparse.ArgumentParser(description="Validate tool results against ground truth")
    parser.add_argument("--tool-output", required=True, help="Path to tool output JSON")
    parser.add_argument("--ground-truth",
                        default="../../backend/benchmarks/by_category/secret_detection/secret_detection_benchmark_GROUND_TRUTH.json",
                        help="Path to ground truth file")
    args = parser.parse_args()

    ground_truth = load_ground_truth(Path(args.ground_truth))
    detected = load_tool_results(Path(args.tool_output))
    metrics = calculate_metrics(ground_truth, detected)

    print("\n" + "="*60)
    print("Secret Detection Validation Results")
    print("="*60)
    print(f"Ground Truth Secrets: {len(ground_truth)}")
    print(f"Detected Secrets: {len(detected)}")
    print(f"\nTrue Positives: {metrics['true_positives']}")
    print(f"False Positives: {metrics['false_positives']}")
    print(f"False Negatives: {metrics['false_negatives']}")
    print(f"\n{'Precision:':<15} {metrics['precision']:.2f}%")
    print(f"{'Recall:':<15} {metrics['recall']:.2f}%")
    print(f"{'F1 Score:':<15} {metrics['f1_score']:.2f}%")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
