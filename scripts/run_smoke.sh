#!/usr/bin/env bash
set -euo pipefail

python scripts/kb_search_smoke.py --mode payload-check
python scripts/kb_search_smoke.py --mode corpus-eval
