"""Each why in the spec, next to a passage from the chosen text. The ledger is spirit.yaml, committed with the project.

The steps for one why: Gemma says what concern sits under it, in the language of the tradition; BM25 and EmbeddingGemma
find candidates; Gemma picks one by number, or none. Only the number comes from the model, so the quote is always the
text's own, and `check` confirms that again against the text. A why with no honest match stays without a passage. A
passage is a proposal until the person keeps it, and one they reject isn't offered again."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import yaml

from . import retrieve, texts

LEDGER = "spirit.yaml"
RELATIONS = ("affirms", "challenges")
PURPOSE_ID = "(purpose)"
PURPOSE_STATEMENT = "What the project is for."

THEMES = """Someone building software wrote this reason for one of their project's rules:

"{why}"

They read {title} ({tradition}) and want to find what it says about the concern under this reason. Leave the technology
behind. What human concern is this really about (honesty, care for others, patience, keeping one's word, and so on), and
what words and images does this text use for it? Answer with JSON only:
{{"concern": "one short sentence with no technical words", "words": ["six to ten words or short phrases this text uses"]}}"""

CHOOSE = """Someone building software wrote this reason for one of their project's rules:

"{why}"

The concern under it: {concern}

They read {title} ({tradition}) and would like a passage to hold next to this reason. These passages came from a search:

{passages}

Choose the one passage that truly speaks to this concern when read in its own setting. It has to make sense on its own,
without the verses around it. A passage that is about another thing and only shares a word doesn't count, and neither
does one you'd have to stretch, like using a verse about killing for a small mistake. Saying none fits is a fine answer,
and often the right one. A passage may affirm
the reason or challenge it (ask more of the person, or warn against how they hold it).
Speak modestly: this is one reader's connection, not what the tradition teaches, and don't tell the person what to believe.
Answer with JSON only:
{{"choice": <the passage number, or 0 if none fits>, "relation": "affirms" or "challenges",
  "how": "one or two plain sentences on how this passage bears on the reason"}}"""

READING = """A software project's reasons were read next to {title} ({tradition}). This part of the text came up most often:
{book}

It opens:
{opening}

Passages from it that came up, and the reasons they were near:
{hits}

In one plain sentence that starts with "It", say what this part of the text is about and what someone working on this
project might take from reading it in full. Say only what the opening and the passages show. Don't guess at the project or
at what the reader is looking for. Answer with JSON only:
{{"why": "..."}}"""

REFLECT = """A software project exists for this purpose: {purpose}

Its reasons were read next to {title} ({tradition}), and these connections were found:
{found}

Write two or three plain, modest sentences on what the project seems to care about most when read this way, and one
question this text would put to the people building it. No flattery and no doctrine. Answer with JSON only:
{{"reflection": "..."}}"""


def fingerprint(why: str) -> str:
    return hashlib.sha256(" ".join(why.split()).encode()).hexdigest()[:12]


def whys(reqs) -> list:
    """[(id, why, statement)]: the project's purpose, then every requirement that gives a reason"""
    out = []
    purpose = " ".join(str(reqs.srs.get("purpose") or "").split())
    if purpose:
        out.append((PURPOSE_ID, purpose, PURPOSE_STATEMENT))
    for r in reqs.items.values():
        if r.rationale:
            out.append((r.id, " ".join(str(r.rationale).split()), " ".join(r.statement.split())))
    return out


def without_why(reqs) -> list:
    return [r.id for r in reqs.items.values() if not r.rationale]


def load_ledger(root: Path = Path(".")) -> dict:
    p = Path(root) / LEDGER
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or {}
    d.setdefault("active", None)
    d.setdefault("texts", {})
    return d


def save_ledger(ledger: dict, root: Path = Path(".")) -> Path:
    p = Path(root) / LEDGER
    head = ("# Each reason in requirements.yaml next to a passage from the text this project's people chose.\n"
            "# Written by `specdeck spirit align`; `status` is theirs to change: proposed, kept or rejected.\n")
    p.write_text(head + yaml.safe_dump(ledger, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return p


class Library:
    """one text, ready to search"""
    def __init__(self, text_id: str):
        self.id = text_id
        self.meta = texts.meta_of(text_id)
        self.passages = texts.load(text_id)
        self.bm25 = retrieve.BM25(self.passages)
        self.index = retrieve.Index.load(texts.path_of(text_id))
        if self.index is not None and len(self.index.vectors) != len(self.passages):
            self.index = None                               # built from an older fetch of the text


def align_one(lib: Library, why: str, statement: str, model, rejected=(), offers: int = 8) -> dict:
    title, tradition = lib.meta["title"], lib.meta["tradition"]
    ctx = why if statement == PURPOSE_STATEMENT else f"{why} (The rule: {statement})"
    themes = model.ask_json(THEMES.format(why=ctx, title=title, tradition=tradition), 250)
    concern = str(themes.get("concern") or why)
    found = themes.get("words") if isinstance(themes.get("words"), list) else []
    query = f"{concern} {' '.join(str(w) for w in found)}"
    hits = retrieve.candidates(lib.passages, lib.bm25, lib.index, query, model, n=offers + len(rejected))
    hits = [h for h in hits if lib.passages[h[0]]["ref"] not in rejected][:offers]
    listed = "\n\n".join(f"{n}. [{lib.passages[i]['ref']}] {lib.passages[i]['text']}" for n, (i, _) in enumerate(hits, 1))
    got = model.ask_json(CHOOSE.format(why=ctx, concern=concern, title=title, tradition=tradition, passages=listed), 300)
    choice = got.get("choice")
    entry = {"why": why, "why_hash": fingerprint(why), "concern": concern}
    if isinstance(choice, int) and not isinstance(choice, bool) and 1 <= choice <= len(hits):
        p = lib.passages[hits[choice - 1][0]]
        relation = got.get("relation") if got.get("relation") in RELATIONS else "affirms"
        entry.update(ref=p["ref"], quote=p["text"], read_further=p["book"], relation=relation,
                     how=" ".join(str(got.get("how") or "").split()), status="proposed")
    else:
        entry.update(ref=None, quote=None, status="no passage")
    entry["near"] = [{"ref": lib.passages[i]["ref"], "book": lib.passages[i]["book"], "score": round(s, 3)} for i, s in hits]
    if rejected:
        entry["rejected"] = list(rejected)
    return entry


def align(reqs, text_id: str, model, root: Path = Path("."), only=None, again: bool = False, log=print) -> dict:
    """Propose a passage for every why with no current entry (a changed why counts as none), saving after each.
    Kept passages stay, unless their why changed or `again` is asked for; a rejected one gets a new proposal."""
    ledger = load_ledger(root)
    if ledger["active"] is None:
        ledger["active"] = text_id
    meta = texts.meta_of(text_id)
    book = ledger["texts"].setdefault(text_id, {"title": meta["title"], "tradition": meta["tradition"],
                                                "translation": meta.get("translation", ""),
                                                "model": getattr(model, "name", "?"), "entries": {}})
    lib = Library(text_id)
    current = whys(reqs)
    book["entries"] = {k: v for k, v in book["entries"].items() if k in {w[0] for w in current}}
    for rid, why, statement in current:
        if only and rid not in only:
            continue
        old = book["entries"].get(rid)
        fresh = bool(old) and old.get("why_hash") == fingerprint(why)
        if fresh and not again and old.get("status") != "rejected":
            continue
        rejected = list((old or {}).get("rejected") or [])
        if old and old.get("status") == "rejected" and old.get("ref"):
            rejected.append(old["ref"])
        entry = align_one(lib, why, statement, model, rejected=rejected)
        book["entries"][rid] = entry
        save_ledger(ledger, root)
        log(f"  {rid}: {entry['ref'] or 'no passage fits'}")
    return ledger


def set_status(rid: str, status: str, text_id: Optional[str] = None, root: Path = Path(".")) -> dict:
    ledger = load_ledger(root)
    entry = ledger["texts"][text_id or ledger["active"]]["entries"][rid]
    if not entry.get("ref"):
        raise ValueError(f"{rid} has no passage to change")
    entry["status"] = status
    save_ledger(ledger, root)
    return entry


def verse_for(rid: str, root: Path = Path(".")) -> Optional[dict]:
    """the passage held next to a rule in the project's own text; None if there is none or it was rejected"""
    try:
        ledger = load_ledger(root)
        entry = ((ledger["texts"].get(ledger["active"]) or {}).get("entries") or {}).get(rid)
    except (OSError, yaml.YAMLError, AttributeError, KeyError):
        return None
    if not entry or not entry.get("ref") or entry.get("status") == "rejected":
        return None
    return entry


def further_reading(reqs, text_id: str, model, root: Path = Path("."), n: int = 5) -> list:
    """The parts of the text the project's reasons landed in most. The ranking is counted from the searches, so every part
    named exists; Gemma only says why it might be worth reading."""
    ledger = load_ledger(root)
    book = ledger["texts"][text_id]
    lib = Library(text_id)
    scores: dict = {}
    hits: dict = {}
    for e in book["entries"].values():
        for rank, near in enumerate(e.get("near") or []):
            scores[near["book"]] = scores.get(near["book"], 0.0) + max(near["score"], 0) / (rank + 1)
        if e.get("ref") and e.get("status") != "rejected":
            hits.setdefault(e["read_further"], []).append(f"{e['ref']}, near: {e['why']}")
            scores[e["read_further"]] = scores.get(e["read_further"], 0.0) + 1.0
    out = []
    for name, score in sorted(scores.items(), key=lambda kv: -kv[1])[:n]:
        opening = " ".join(p["text"] for p in lib.passages if p["book"] == name)[:600]
        got = model.ask_json(READING.format(title=book["title"], tradition=book["tradition"], book=name, opening=opening,
                                            hits="\n".join(hits.get(name, ["(near several reasons in the search)"]))), 150)
        out.append({"read": name, "score": round(score, 2), "why": " ".join(str(got.get("why") or "").split()),
                    "passages": len(hits.get(name, []))})
    book["reading"] = out
    found = [f"{e['why']} / {e['ref']}: {e['how']}" for e in book["entries"].values()
             if e.get("ref") and e.get("status") != "rejected"]
    purpose = " ".join(str(reqs.srs.get("purpose") or "").split()) or "(not stated)"
    got = model.ask_json(REFLECT.format(purpose=purpose, title=book["title"], tradition=book["tradition"],
                                        found="\n".join(found[:30])), 300)
    book["reflection"] = " ".join(str(got.get("reflection") or "").split())
    save_ledger(ledger, root)
    return out


def check(reqs, root: Path = Path(".")) -> dict:
    """What holds the ledger to the spec and to the text. Problems: a why with no entry in the project's own text, an entry
    whose why has changed, a quote that isn't in the text word for word. Notes: passages nobody has kept yet, whys with no
    passage, rules with no why."""
    ledger = load_ledger(root)
    if not ledger["active"]:
        return {"problems": ["no text chosen: run `specdeck spirit align --text ID`"], "notes": []}
    problems, notes = [], []
    current = whys(reqs)
    for text_id, book in ledger["texts"].items():
        own = text_id == ledger["active"]
        entries = book.get("entries") or {}
        by_ref = None
        if texts.is_fetched(text_id):
            by_ref = {p["ref"]: p["text"] for p in texts.load(text_id)}
        else:
            notes.append(f"{text_id}: not fetched here, so its quotes weren't compared with the text")
        for rid, why, _ in current:
            e = entries.get(rid)
            if e is None:
                if own:
                    problems.append(f"{rid}: its why has no entry in {text_id}")
            elif e.get("why_hash") != fingerprint(why):
                problems.append(f"{rid}: its why changed after it was aligned with {text_id}")
        for rid, e in entries.items():
            if e.get("ref") and by_ref is not None and by_ref.get(e["ref"]) != e.get("quote"):
                problems.append(f"{rid}: the quote from {e['ref']} isn't what {text_id} says there")
            if own and e.get("status") == "proposed":
                notes.append(f"{rid}: {e['ref']} is proposed, nobody has kept it yet")
            if own and e.get("status") == "no passage":
                notes.append(f"{rid}: no passage fits this why in {text_id}")
    notes += [f"{rid}: this rule gives no why, so there's nothing to align" for rid in without_why(reqs)]
    return {"problems": problems, "notes": notes}
