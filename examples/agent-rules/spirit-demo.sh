#!/usr/bin/env bash
# The spirit layer on the shop example, using the alignments saved in spirit.yaml, so no model is needed to watch it.
# Runs in a scratch copy, so this directory stays as it is.  PAUSE=0 ./spirit-demo.sh to run straight through.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)/shop"
cp -r "$here" "$work" && cd "$work" && rm -rf .specdeck
pause() { [ "${PAUSE:-1}" = 0 ] || read -r -p $'\n[enter] ' _; }
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
quiet_pytest() { python3 -m pytest -q -p no:cacheprovider -p no:asyncio "$@" 2>&1 | grep -v -e '^$' -e Warning -e warnings.warn || true; }

step "1. A rule, with its why"
sed -n '/rules.decimal-money/,/type:/p' requirements.yaml
pause

step "2. The same why, read next to each text"
python3 - <<'PY'
import yaml
d = yaml.safe_load(open("spirit.yaml"))
for book in d["texts"].values():
    e = book["entries"].get("rules.decimal-money") or {}
    print(f"\n{book['title']} ({book['tradition']})")
    print(f"  \"{e['quote']}\" ({e['ref']})" if e.get("ref") else "  no passage fits, and that's allowed")
PY
pause

step "3. The tests pass, and the rules go into AGENTS.md with the passage this project keeps"
quiet_pytest | tail -1
python3 -m specdeck agents
grep -A2 'no float anywhere' AGENTS.md
pause

step "4. An agent adds a refund function, the quick way"
tail -3 agent_change/refund.py
cat agent_change/refund.py >> src/shop/orders.py
pause

step "5. The rule breaks, and the report says why it matters"
quiet_pytest | grep -A1 -e "rule rules.decimal-money broken" || true
pause

step "6. Checking the ledger: every why aligned, every quote the text's own"
python3 -m specdeck spirit check | tail -1
