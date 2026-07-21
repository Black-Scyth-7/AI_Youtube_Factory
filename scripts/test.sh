#!/usr/bin/env bash
# Run all test suites (Node workspace + Python services).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Node tests"
pnpm test

echo "==> Backend tests"
( cd apps/backend && pytest )

echo "==> Worker tests"
( cd apps/worker && pytest )

echo "==> All tests passed."
