#!/bin/bash
# Helper script to push changes after each spec-driven development phase

set -e

PHASE="${1:-unknown}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📦 Pushing phase: $PHASE${NC}"

# Check if there are changes to commit
if [[ -z $(git status -s) ]]; then
    echo -e "${BLUE}✓ No changes to commit${NC}"
    exit 0
fi

# Stage all changes
git add -A

# Commit with phase information
git commit -m "Complete $PHASE phase - $(date '+%Y-%m-%d %H:%M:%S')

Updates from spec-driven development workflow.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>" || echo "Nothing to commit"

# Push to remote
if git push; then
    echo -e "${GREEN}✓ Successfully pushed $PHASE phase${NC}"
else
    echo -e "${BLUE}⚠ Push failed - check network connection${NC}"
    exit 1
fi
