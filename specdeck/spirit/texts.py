"""The catalogue of spiritual texts: where each one comes from, its licence, and how it becomes numbered passages.

Only texts whose translation is public domain or openly licensed are listed. Each is downloaded once, on request, into
~/.specdeck/spirit (SPECDECK_SPIRIT_HOME moves it) as one JSON object a line: {"ref", "text", "book"}. `ref` cites the
passage the way readers of that text do and `book` is the part of it to read further in. Any other text can be added
with `specdeck spirit add-text`, since this list is only what could be found openly, not a judgement of what counts."""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

UA = {"User-Agent": "specdeck-spirit/0.1 (https://github.com/BlaiseLabs/specdeck-spirit)"}


def home() -> Path:
    return Path(os.environ.get("SPECDECK_SPIRIT_HOME", Path.home() / ".specdeck" / "spirit"))


def _get(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8-sig", errors="replace")
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError


def _clean(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text)).split())


def _gutenberg(n: int) -> str:
    t = _get(f"https://www.gutenberg.org/cache/epub/{n}/pg{n}.txt").replace("\r\n", "\n")
    a = t.index("\n", t.index("*** START OF"))
    return t[a:t.index("*** END OF")]


def _paragraphs(text: str) -> list:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def kjv() -> list:
    out = []
    for book in json.loads(_get("https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json")):
        for c, chapter in enumerate(book["chapters"], 1):
            for v, verse in enumerate(chapter, 1):
                out.append({"ref": f"{book['name']} {c}:{v}", "book": f"{book['name']} {c}",
                            "text": _clean(verse.replace("{", "").replace("}", ""))})
    return out


TANAKH = {"Torah": ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"],
          "Prophets": ["Joshua", "Judges", "I Samuel", "II Samuel", "I Kings", "II Kings", "Isaiah", "Jeremiah", "Ezekiel",
                       "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
                       "Zechariah", "Malachi"],
          "Writings": ["Psalms", "Proverbs", "Job", "Song of Songs", "Ruth", "Lamentations", "Ecclesiastes", "Esther",
                       "Daniel", "Ezra", "Nehemiah", "I Chronicles", "II Chronicles"]}


def tanakh() -> list:
    out = []
    base = "https://storage.googleapis.com/sefaria-export/json/Tanakh"
    version = "The%20Holy%20Scriptures%20A%20New%20Translation%20JPS%201917.json"
    for part, books in TANAKH.items():
        for book in books:
            d = json.loads(_get(f"{base}/{part}/{book.replace(' ', '%20')}/English/{version}"))
            for c, chapter in enumerate(d["text"], 1):
                for v, verse in enumerate(chapter, 1):
                    verse = _clean(re.sub(r"<sup.*?</sup>|<i class=\"footnote\">.*?</i>", "", verse, flags=re.S))
                    if verse:
                        out.append({"ref": f"{book} {c}:{v}", "book": f"{book} {c}", "text": verse})
    return out


def quran() -> list:
    d = json.loads(_get("https://api.alquran.cloud/v1/quran/en.pickthall"))["data"]
    out = []
    for s in d["surahs"]:
        for a in s["ayahs"]:
            out.append({"ref": f"Surah {s['englishName']} {s['number']}:{a['numberInSurah']}",
                        "book": f"Surah {s['englishName']} ({s['number']})", "text": _clean(a["text"])})
    return out


DHP = ["1-20", "21-32", "33-43", "44-59", "60-75", "76-89", "90-99", "100-115", "116-128", "129-145", "146-156", "157-166",
       "167-178", "179-196", "197-208", "209-220", "221-234", "235-255", "256-272", "273-289", "290-305", "306-319",
       "320-333", "334-359", "360-382", "383-423"]


def dhammapada() -> list:
    out = []
    base = "https://raw.githubusercontent.com/suttacentral/bilara-data/published/translation/en/sujato/sutta/kn/dhp"
    for part in DHP:
        verses: dict = {}
        title = part
        for key, seg in json.loads(_get(f"{base}/dhp{part}_translation-en-sujato.json")).items():
            m = re.match(r"dhp(\d+):(\S+)", key)
            if m.group(2).startswith("0"):
                if m.group(2) == "0.3":
                    title = seg.strip()
            elif seg.strip():
                verses.setdefault(int(m.group(1)), []).append(seg.strip())
        for n, lines in sorted(verses.items()):
            out.append({"ref": f"Dhammapada {n}", "book": f"Chapter {title}", "text": " ".join(lines)})
    return out


def _chunks(paras: list, limit: int = 700) -> list:
    """paragraphs joined up to a passage of readable size; a longer paragraph is cut between sentences"""
    pieces = []
    for p in paras:
        cur = ""
        for sent in re.split(r"(?<=[.!?;:])\s+", p) if len(p) > limit else [p]:
            if cur and len(cur) + len(sent) > limit:
                pieces.append(cur)
                cur = ""
            cur = f"{cur} {sent}".strip()
        pieces.append(cur)
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = ""
        cur = f"{cur} {p}".strip()
    return out + ([cur] if cur else [])


def gita() -> list:
    body = _gutenberg(2388)
    parts = re.split(r"\n\s*CHAPTER ([IVXL]+)\s*\n", body)
    out = []
    for ch, text in zip(parts[1::2], parts[2::2]):
        text = re.sub(r"\[FN#\d+\]", "", re.split(r"HERE ENDETH", text)[0])
        for i, chunk in enumerate(_chunks(_paragraphs(text)), 1):
            out.append({"ref": f"Bhagavad Gita, Chapter {ch}, passage {i}", "book": f"Chapter {ch}", "text": chunk})
    return out


def tao() -> list:
    body = _gutenberg(216)
    parts = re.split(r"\n(\d+)\.[ \n]", "\n" + body[body.index("1. 1. The Tao"):])
    chapters, want = {}, 1
    for n, text in zip(parts[1::2], parts[2::2]):
        # a chapter opens with its number and then "1." or plain text after a wider gap; "2." inside a chapter does not
        opens = int(n) == want and (want == 1 or text.startswith("1. ") or gap.endswith("\n\n"))
        if opens:
            chapters[want] = text
            want += 1
        elif chapters:
            chapters[want - 1] += f"\n{n}. {text}"
        gap = text
    out = []
    for n, text in chapters.items():
        chunks = _chunks(_paragraphs(re.sub(r"\n\s*(?:Part|PART) \d+.*", "", text)), 600)
        for i, chunk in enumerate(chunks, 1):
            out.append({"ref": f"Tao Te Ching {n}" + (f", passage {i}" if len(chunks) > 1 else ""),
                        "book": f"Chapter {n}", "text": chunk})
    return out


def analects() -> list:
    body = _gutenberg(3330)
    parts = re.split(r"\n\s*BOOK ([IVXL]+)\.[^\n]*\n", body)
    out = []
    for bk, text in zip(parts[1::2], parts[2::2]):
        for m in re.finditer(r"CHAP\.\s*([IVXLC]+)\.\s*(.*?)(?=\n\s*CHAP\.|\Z)", "CHAP. I. " + text if "CHAP." not in text[:300] else text, re.S):
            chunks = _chunks([re.sub(r"^CHAPTER [IVXLC]+\. ", "", " ".join(m.group(2).split()))]) if m.group(2).strip() else []
            for i, t in enumerate(chunks, 1):
                out.append({"ref": f"Analects {bk}.{m.group(1)}" + (f" ({i})" if i > 1 else ""), "book": f"Book {bk}", "text": t})
    return out


def meditations() -> list:
    body = _gutenberg(2680)
    parts = re.split(r"\n\s*THE (\w+) BOOK\s*\n", body)
    out = []
    for name, text in zip(parts[1::2], parts[2::2]):
        text = re.split(r"\n\s*(?:APPENDIX|NOTES|GLOSSARY)\s*\n", text)[0]
        for m in re.finditer(r"(?:^|\n)\s*([IVXLC]+)\. (.*?)(?=\n\s*[IVXLC]+\. |\Z)", text, re.S):
            for i, chunk in enumerate(_chunks(_paragraphs(m.group(2)), 800), 1):
                out.append({"ref": f"Meditations, {name.title()} Book, {m.group(1)}" + (f" ({i})" if i > 1 else ""),
                            "book": f"The {name.title()} Book", "text": chunk})
    return out


def kojiki() -> list:
    out = []
    for n in range(1, 181):
        page = _get("https://en.wikisource.org/w/index.php?title=" +
                    f"Kojiki_(Chamberlain,_1882)/Section_{n}&action=render")
        page = re.sub(r"<style.*?</style>|<sup.*?</sup>|<ol class=\"(?:mw-)?references\".*?</ol>|data-mw='.*?'", "", page, flags=re.S)
        paras = [_clean(p) for p in re.findall(r"<p[ >].*?</p>", page, flags=re.S)]
        text = " ".join(p for p in paras if p)
        text = text.replace("\u200b", "")
        title = re.search(r"\[?\s*Sect\.\s*[IVXLC]+\.\W*([^\].]+)\.?\s*\]?", text)
        text = re.sub(r"\[?\s*Sect\.\s*[IVXLC]+\.\W*[^\].]+\.?\s*\]?|RECORDS OF ANCIENT MATTERS\.|\[\s*\d+\s*\]", "", text)
        for i, chunk in enumerate(_chunks([" ".join(text.split())], 800), 1):
            out.append({"ref": f"Kojiki, Section {n}" + (f" ({i})" if i > 1 else ""),
                        "book": f"Section {n}" + (f", {title.group(1)}" if title else ""), "text": chunk})
        time.sleep(0.2)
    return out


def book_of_mormon() -> list:
    out, book = [], None
    for p in _paragraphs(_gutenberg(17)):
        m = re.match(r"(.+?) Chapter \d+$", p)
        if m:
            book = m.group(1)
            continue
        m = re.match(r"(\d+):(\d+) (.*)", p)
        if m and book:
            out.append({"ref": f"{book} {m.group(1)}:{m.group(2)}", "book": f"{book} {m.group(1)}", "text": m.group(3)})
    return out


@dataclass(frozen=True)
class Text:
    id: str
    title: str
    tradition: str
    translation: str
    licence: str
    source: str
    build: Optional[Callable] = None


CATALOGUE = {t.id: t for t in [
    Text("bible-kjv", "The Holy Bible", "Christian", "King James Version, 1611", "public domain in the US",
         "github.com/thiagobodruk/bible", kjv),
    Text("tanakh-jps", "The Tanakh", "Jewish", "Jewish Publication Society, 1917", "public domain", "Sefaria export", tanakh),
    Text("quran-pickthall", "The Qur'an", "Muslim", "The Meaning of the Glorious Koran, Pickthall, 1930",
         "public domain in the US", "api.alquran.cloud", quran),
    Text("dhammapada", "The Dhammapada", "Buddhist", "Bhikkhu Sujato", "CC0", "SuttaCentral bilara-data", dhammapada),
    Text("gita-arnold", "The Bhagavad Gita", "Hindu", "The Song Celestial, Edwin Arnold, 1885", "public domain",
         "Project Gutenberg 2388", gita),
    Text("kojiki", "The Kojiki", "Shinto", "Basil Hall Chamberlain, 1882", "public domain", "Wikisource", kojiki),
    Text("tao-te-ching", "The Tao Te Ching", "Taoist", "James Legge, 1891", "public domain", "Project Gutenberg 216", tao),
    Text("analects", "The Analects", "Confucian", "James Legge, 1861", "public domain", "Project Gutenberg 3330", analects),
    Text("meditations", "Meditations of Marcus Aurelius", "Stoic", "Jeremy Collier, 1701, revised Zimmern", "public domain",
         "Project Gutenberg 2680", meditations),
    Text("book-of-mormon", "The Book of Mormon", "Latter-day Saint", "Project Gutenberg edition", "public domain", "Project Gutenberg 17",
         book_of_mormon),
]}


def path_of(text_id: str) -> Path:
    return home() / f"{text_id}.jsonl"


def is_fetched(text_id: str) -> bool:
    return path_of(text_id).exists()


def _save(text_id: str, passages: list, meta: dict) -> Path:
    home().mkdir(parents=True, exist_ok=True)
    p = path_of(text_id)
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in passages), encoding="utf-8")
    p.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return p


def fetch(text_id: str) -> int:
    t = CATALOGUE[text_id]
    passages = t.build()
    if not passages:
        raise ValueError(f"{text_id}: the source gave no passages")
    _save(text_id, passages, {"id": t.id, "title": t.title, "tradition": t.tradition, "translation": t.translation,
                              "licence": t.licence, "source": t.source})
    return len(passages)


def add_text(text_id: str, file: Path, title: str, tradition: str, translation: str = "", licence: str = "") -> int:
    """a text of the person's own: JSON lines with ref and text, or plain text where a blank line ends a passage"""
    raw = Path(file).read_text(encoding="utf-8")
    if Path(file).suffix == ".jsonl":
        passages = [json.loads(line) for line in raw.splitlines() if line.strip()]
        for p in passages:
            p.setdefault("book", p["ref"])
    else:
        passages = [{"ref": f"{title}, passage {i}", "book": f"{title}, part {(i - 1) // 20 + 1}", "text": chunk}
                    for i, chunk in enumerate(_chunks(_paragraphs(raw)), 1)]
    if not passages:
        raise ValueError(f"{file}: no passages")
    _save(text_id, passages, {"id": text_id, "title": title, "tradition": tradition, "translation": translation,
                              "licence": licence, "source": str(file)})
    return len(passages)


def meta_of(text_id: str) -> dict:
    p = path_of(text_id).with_suffix(".meta.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    t = CATALOGUE[text_id]
    return {"id": t.id, "title": t.title, "tradition": t.tradition, "translation": t.translation, "licence": t.licence,
            "source": t.source}


def load(text_id: str) -> list:
    p = path_of(text_id)
    if not p.exists():
        raise FileNotFoundError(f"{text_id} is not fetched yet: run `specdeck spirit fetch {text_id}`")
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
