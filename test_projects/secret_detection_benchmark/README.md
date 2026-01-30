# Secret Detection Benchmark Dataset

Ground truth dataset with **exactly 32 known secrets** for testing secret detection tools.

## Contents

- **12 Easy Secrets**: Standard patterns (AWS keys, GitHub PATs, Stripe keys, etc.)
- **10 Medium Secrets**: Slightly obfuscated (Base64, hex, concatenated, in comments)
- **10 Hard Secrets**: Well hidden (ROT13, binary, XOR, reversed, template strings)

## Files

```
├── .env                        # 2 secrets
├── config/
│   ├── settings.py            # 3 secrets
│   ├── database.yaml          # 1 secret
│   ├── app.properties         # 1 secret
│   ├── oauth.json             # 1 secret
│   ├── keys.yaml              # 2 secrets
│   └── legacy.ini             # 2 secrets
├── src/
│   ├── app.py                 # 1 secret
│   ├── Main.java              # 1 secret
│   ├── config.py              # 3 secrets (medium difficulty)
│   ├── obfuscated.py          # 4 secrets (hard difficulty)
│   ├── advanced.js            # 4 secrets (hard difficulty)
│   ├── Crypto.go              # 2 secrets (hard difficulty)
│   └── database.sql           # 1 secret
├── scripts/
│   ├── webhook.js             # 1 secret
│   └── deploy.sh              # 2 secrets
└── id_rsa                     # 1 secret

Total: 17 files with 32 secrets
```

## Secret Difficulty Breakdown

### Easy (12 secrets)
Should be detected by any decent secret scanner:
- Plain AWS access keys
- GitHub Personal Access Tokens
- Stripe API keys
- Database passwords in plain text
- JWT secrets
- SSH private keys
- OAuth secrets
- Slack webhooks

### Medium (10 secrets)
Requires some parsing or contextual understanding:
- Base64 encoded AWS key
- Hex-encoded tokens
- Split strings concatenated at runtime
- URL-encoded passwords
- Multi-line private keys in YAML
- Secrets with Unicode characters
- Secrets in SQL/shell comments
- Deprecated config formats

### Hard (10 secrets)
Well hidden, may challenge even advanced tools:
- ROT13 encoded secrets
- Binary string representations
- Character array joins
- Reversed strings
- Template string constructs
- Secrets in regex patterns
- XOR encrypted values
- Escaped JSON within strings
- Heredoc patterns
- Intentional typos corrected programmatically

## Usage

Run secret detection tools against this directory and compare results to the ground truth file (located in `backend/benchmarks/by_category/secret_detection/secret_detection_benchmark_GROUND_TRUTH.json`) to calculate:

- **Precision**: TP / (TP + FP) - How many detected secrets are real?
- **Recall**: TP / (TP + FN) - How many real secrets were found?
- **F1 Score**: 2 × (Precision × Recall) / (Precision + Recall)

### Expected Performance

| Tool Type | Expected Easy | Expected Medium | Expected Hard | Total Expected |
|-----------|---------------|-----------------|---------------|----------------|
| Pattern-based (Gitleaks) | 12/12 (100%) | 6-8/10 (60-80%) | 2-4/10 (20-40%) | 20-24/32 |
| Entropy-based (TruffleHog) | 12/12 (100%) | 5-7/10 (50-70%) | 1-3/10 (10-30%) | 18-22/32 |
| LLM-based | 12/12 (100%) | 8-10/10 (80-100%) | 4-8/10 (40-80%) | 24-30/32 |

## Validation

Use the validation script to check tool performance:

```bash
python validate_ground_truth.py --tool-output results.json
```

This will calculate precision, recall, and F1 score against the ground truth.
