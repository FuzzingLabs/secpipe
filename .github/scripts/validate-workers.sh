#!/bin/bash
# Worker Validation Script
# Ensures all workers defined in docker-compose.yml exist in the repository
# and are properly tracked by git.

set -e

echo "🔍 Validating worker completeness..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Extract worker service names from docker-compose.yml
echo ""
echo "📋 Checking workers defined in docker-compose.yml..."
WORKERS=$(grep -E "^\s+worker-" docker-compose.yml | grep -v "#" | cut -d: -f1 | tr -d ' ' | sort -u)

if [ -z "$WORKERS" ]; then
    echo -e "${RED}❌ No workers found in docker-compose.yml${NC}"
    exit 1
fi

echo "Found workers:"
for worker in $WORKERS; do
    echo "  - $worker"
done

# Check each worker
echo ""
echo "🔎 Validating worker files..."
for worker in $WORKERS; do
    WORKER_DIR="workers/${worker#worker-}"

    echo ""
    echo "Checking $worker ($WORKER_DIR)..."

    # Check if directory exists
    if [ ! -d "$WORKER_DIR" ]; then
        echo -e "${RED}  ❌ Directory not found: $WORKER_DIR${NC}"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # Check required files
    REQUIRED_FILES=("Dockerfile" "requirements.txt" "worker.py")
    for file in "${REQUIRED_FILES[@]}"; do
        FILE_PATH="$WORKER_DIR/$file"

        if [ ! -f "$FILE_PATH" ]; then
            echo -e "${RED}  ❌ Missing file: $FILE_PATH${NC}"
            ERRORS=$((ERRORS + 1))
        else
            # Check if file is tracked by git
            if ! git ls-files --error-unmatch "$FILE_PATH" &> /dev/null; then
                echo -e "${RED}  ❌ File not tracked by git: $FILE_PATH${NC}"
                echo -e "${YELLOW}     Check .gitignore patterns!${NC}"
                ERRORS=$((ERRORS + 1))
            else
                echo -e "${GREEN}  ✓ $file (tracked)${NC}"
            fi
        fi
    done
done

# Check for any ignored worker files
echo ""
echo "🚫 Checking for gitignored worker files..."
IGNORED_FILES=$(git check-ignore workers/*/* 2>/dev/null || true)
if [ -n "$IGNORED_FILES" ]; then
    echo -e "${YELLOW}⚠️  Warning: Some worker files are being ignored:${NC}"
    echo "$IGNORED_FILES" | while read -r file; do
        echo -e "${YELLOW}  - $file${NC}"
    done
    WARNINGS=$((WARNINGS + 1))
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All workers validated successfully!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Validation passed with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}❌ Validation failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    exit 1
fi
