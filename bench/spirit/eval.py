"""Do the chosen passages speak to the whys any better than chance? A blind check with the same local Gemma.

    python bench/spirit/eval.py spirit.yaml [--seed 1]

For each why and text, the chosen passage and a random passage from the same text go to Gemma with no sign of which is
which, each scored on its own: does it speak to this concern, 0 to 3. Self-marking by the same model that chose is
generous, so read this as a floor check against chance, not as proof the passages are good."""
import json
import random
import sys
from pathlib import Path

import yaml

from specdeck.spirit import texts
from specdeck.spirit.model import Ollama

JUDGE = """Someone wrote this reason for a rule in their software project:

"{why}"

The human concern under it: {concern}

Here is a passage from {title}:

"{quote}"

Does this passage, read in its own setting and without stretching it, speak to that concern?
0 means not at all, 1 only by a shared word or image, 2 yes in a general way, 3 clearly and directly.
Answer with JSON only: {{"score": 0}}"""


def main():
    ledger = yaml.safe_load(Path(sys.argv[1]).read_text())
    rng = random.Random(int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1)
    model = Ollama()
    rows = []
    for tid, book in ledger["texts"].items():
        passages = texts.load(tid)
        for rid, e in book["entries"].items():
            if not e.get("ref"):
                rows.append({"text": tid, "rule": rid, "chosen": None, "random": None})
                continue
            other = rng.choice(passages)
            pair = [("chosen", e["quote"]), ("random", other["text"])]
            rng.shuffle(pair)
            row = {"text": tid, "rule": rid, "ref": e["ref"], "random_ref": other["ref"]}
            for kind, quote in pair:
                got = model.ask_json(JUDGE.format(why=e["why"], concern=e["concern"], title=book["title"], quote=quote), 60)
                row[kind] = got.get("score")
            rows.append(row)
            print(json.dumps(row), flush=True)
    scored = [r for r in rows if isinstance(r.get("chosen"), int) and isinstance(r.get("random"), int)]
    print(f"{len(scored)} passages, chosen mean {sum(r['chosen'] for r in scored) / len(scored):.2f}, "
          f"random mean {sum(r['random'] for r in scored) / len(scored):.2f}, "
          f"chosen higher in {sum(r['chosen'] > r['random'] for r in scored)}, "
          f"tied in {sum(r['chosen'] == r['random'] for r in scored)}, "
          f"no passage for {sum(r.get('chosen') is None and not r.get('ref') for r in rows)}")


if __name__ == "__main__":
    main()
