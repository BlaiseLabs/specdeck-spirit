"""`specdeck spirit ...`"""
from __future__ import annotations

import sys
from pathlib import Path

from . import align as A
from . import retrieve, texts


def add_parser(sub) -> None:
    p = sub.add_parser("spirit", help="read each why in the spec next to a spiritual text you choose, with open models running locally")
    p.add_argument("--requirements", default="requirements.yaml", help="requirements file (default requirements.yaml)")
    s = p.add_subparsers(dest="spirit_cmd", required=True)
    s.add_parser("texts", help="the texts that can be fetched, and which already are")
    f = s.add_parser("fetch", help="download texts and turn them into passages")
    f.add_argument("ids", nargs="*", help="text ids; none means all")
    d = s.add_parser("add-text", help="add a text of your own: .jsonl with ref and text, or plain text with blank lines between passages")
    d.add_argument("id")
    d.add_argument("file")
    d.add_argument("--title", required=True)
    d.add_argument("--tradition", required=True)
    d.add_argument("--translation", default="")
    d.add_argument("--licence", default="")
    i = s.add_parser("index", help="embed every passage so meaning can find passages keywords can't (optional and slow on big texts)")
    i.add_argument("ids", nargs="+")
    a = s.add_parser("align", help="propose a passage for each why that has none yet")
    a.add_argument("--text", action="append", default=None, help="text id; repeat for several. The first ever used becomes the project's own")
    a.add_argument("--only", action="append", default=None, metavar="RULE", help="just this requirement; repeat for several")
    a.add_argument("--again", action="store_true", help="propose again even where a passage exists")
    u = s.add_parser("use", help="choose which aligned text the rules and agent instructions quote")
    u.add_argument("id")
    w = s.add_parser("show", help="print the whys and their passages")
    w.add_argument("rule", nargs="?")
    w.add_argument("--text", default=None)
    for name, what in (("keep", "keep a proposed passage, making it yours"), ("reject", "reject a passage; `align` then offers another")):
        k = s.add_parser(name, help=what)
        k.add_argument("rule")
        k.add_argument("--text", default=None)
    r = s.add_parser("read", help="what to read further, from where the project's whys landed")
    r.add_argument("--text", default=None)
    o = s.add_parser("report", help="write SPIRIT.md")
    o.add_argument("--out", default="SPIRIT.md", help="file to write, - for stdout")
    c = s.add_parser("check", help="every why aligned and current, every quote word for word in the text")
    c.add_argument("--fail", action="store_true", help="exit 1 on a problem")


def _reqs(args):
    from ..requirements import load

    if not Path(args.requirements).exists():
        print(f"specdeck: no requirements file at {args.requirements}", file=sys.stderr)
        raise SystemExit(2)
    return load(args.requirements)


def _texts() -> int:
    for t in texts.CATALOGUE.values():
        state = "fetched" if texts.is_fetched(t.id) else "not fetched"
        print(f"{t.id:<18} {t.tradition:<17} {t.title}, {t.translation} ({t.licence}), {state}")
    if texts.home().exists():
        for p in sorted(texts.home().glob("*.jsonl")):
            if p.stem not in texts.CATALOGUE and ".vec" not in p.name:
                m = texts.meta_of(p.stem)
                print(f"{p.stem:<18} {m['tradition']:<17} {m['title']}, your own, fetched")
    return 0


def _fetch(args) -> int:
    for tid in args.ids or list(texts.CATALOGUE):
        if tid not in texts.CATALOGUE:
            print(f"specdeck: unknown text {tid}; see `specdeck spirit texts`", file=sys.stderr)
            return 2
        print(f"{tid}: {texts.fetch(tid):,} passages")
    return 0


def _align(args, model) -> int:
    reqs = _reqs(args)
    ledger = A.load_ledger()
    ids = args.text or ([ledger["active"]] if ledger["active"] else None)
    if not ids:
        print("specdeck: choose a text with --text ID; see `specdeck spirit texts`", file=sys.stderr)
        return 2
    for tid in ids:
        print(f"{tid}:")
        A.align(reqs, tid, model, only=args.only, again=args.again)
    for rid in A.without_why(reqs):
        print(f"  {rid}: gives no why, so there's nothing to align")
    return 0


def _show(args) -> int:
    ledger = A.load_ledger()
    book = ledger["texts"].get(args.text or ledger["active"])
    if not book:
        print("specdeck: nothing aligned yet", file=sys.stderr)
        return 2
    for rid, e in book["entries"].items():
        if args.rule and rid != args.rule:
            continue
        print(f"{rid}\n  why   {e['why']}")
        if e.get("ref"):
            print(f"  {e['ref']} ({e['relation']}, {e['status']})\n    \"{e['quote']}\"\n  how   {e['how']}\n  read  {e['read_further']}")
        else:
            print("  no passage fits")
    return 0


def _check(args) -> int:
    res = A.check(_reqs(args))
    for p in res["problems"]:
        print(f"✖ {p}")
    for n in res["notes"]:
        print(f"· {n}")
    if not res["problems"]:
        print("specdeck: every why is aligned and current, and every quote is the text's own")
    return 1 if args.fail and res["problems"] else 0


def run(args) -> int:
    from .model import ModelError, Ollama

    cmd = args.spirit_cmd
    try:
        if cmd == "texts":
            return _texts()
        if cmd == "fetch":
            return _fetch(args)
        if cmd == "add-text":
            n = texts.add_text(args.id, Path(args.file), args.title, args.tradition, args.translation, args.licence)
            print(f"{args.id}: {n:,} passages")
            return 0
        if cmd == "index":
            for tid in args.ids:
                print(f"{tid}: {retrieve.build_index(texts.load(tid), texts.path_of(tid), Ollama())}")
            return 0
        if cmd == "align":
            return _align(args, Ollama())
        if cmd == "use":
            ledger = A.load_ledger()
            if args.id not in ledger["texts"]:
                print(f"specdeck: {args.id} isn't aligned yet; run `specdeck spirit align --text {args.id}`", file=sys.stderr)
                return 2
            ledger["active"] = args.id
            A.save_ledger(ledger)
            return 0
        if cmd == "show":
            return _show(args)
        if cmd in ("keep", "reject"):
            e = A.set_status(args.rule, "kept" if cmd == "keep" else "rejected", args.text)
            print(f"{args.rule}: {e['ref']} {'kept' if cmd == 'keep' else 'rejected; `specdeck spirit align` offers another'}")
            return 0
        if cmd == "read":
            for r in A.further_reading(_reqs(args), args.text or A.load_ledger()["active"], Ollama()):
                print(f"{r['read']}: {r['why']}")
            return 0
        if cmd == "report":
            from .report import render

            text = render(_reqs(args), A.load_ledger())
            if args.out == "-":
                print(text)
            else:
                Path(args.out).write_text(text, encoding="utf-8")
                print(f"specdeck: wrote {args.out}", file=sys.stderr)
            return 0
        if cmd == "check":
            return _check(args)
    except ModelError as e:
        print(f"specdeck: {e}", file=sys.stderr)
        return 1
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"specdeck: {e}", file=sys.stderr)
        return 2
    return 2
