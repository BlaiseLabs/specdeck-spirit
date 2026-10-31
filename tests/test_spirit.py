"""The spirit layer: quotes stay the text's own, the person decides, and the ledger stays honest. Offline, with a stand-in model."""
import json
import re

import pytest

from specdeck import scenario
from specdeck.requirements import load
from specdeck.spirit import align as A
from specdeck.spirit import texts as T


class Stand:
    """Answers like the models, on purpose: embed by shared words, choose what `choice` says"""
    name = "stand-in"

    def __init__(self, choice=1):
        self.choice = choice
        self.offered = []

    def ask_json(self, prompt, num_predict=500):
        if '"concern"' in prompt:
            return {"concern": "being honest with weights and measures", "words": ["balance", "weight", "just"]}
        if '"choice"' in prompt:
            self.offered.append(re.findall(r"^\d+\. \[(.+?)\]", prompt, re.M))
            return {"choice": self.choice, "relation": "affirms",
                    "how": 'It says "a verse no text has ever said" about money.'}
        if '"reflection"' in prompt:
            return {"reflection": "This project cares about being exact."}
        return {"why": "It is about honest dealing."}

    def embed(self, texts, query=False):
        vecs = []
        for t in texts:
            v = [0.0] * 32
            for w in re.findall(r"[a-z]+", t.lower()):
                v[sum(map(ord, w)) % 32] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            vecs.append([x / n for x in v])
        return vecs


SCROLL = "\n\n".join([
    "A false balance is an abomination, but a just weight is a delight.",
    "The honest measure of the merchant stands for ever, the just balance of the market.",
    "The river runs down to the sea and the sea is not full.",
    "Be patient with the slow ox, for the field is long."])


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECDECK_SPIRIT_HOME", str(tmp_path / "texts"))
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "scroll.txt"
    src.write_text(SCROLL)
    T.add_text("scroll", src, "The Scroll", "Test", "plain", "CC0")
    (tmp_path / "requirements.yaml").write_text("""
srs:
  purpose: Keep honest accounts for a small shop.
requirements:
  - id: money.decimal
    statement: Money amounts shall be Decimal values.
    rationale: A float made a refund a cent short and the balance would not reconcile.
    type: design-constraint
  - id: no.reason
    statement: Files shall end with a newline.
    type: process
""")
    return tmp_path


@scenario(covers=["spirit.quotes-are-the-texts"])
def test_the_quote_is_the_texts_own_whatever_the_model_says(project):
    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(choice=1), log=lambda _: None)
    entry = A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]
    passages = {p["ref"]: p["text"] for p in T.load("scroll")}
    assert entry["quote"] == passages[entry["ref"]]
    assert "no text has ever said" not in entry["quote"]


@scenario(covers=["spirit.none-fits"])
@pytest.mark.parametrize("choice", [0, 99, -1, True, "1", None])
def test_no_fitting_or_a_bad_choice_means_no_passage(project, choice):
    A.align(load("requirements.yaml"), "scroll", Stand(choice=choice), log=lambda _: None)
    entry = A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]
    assert entry["ref"] is None and entry["quote"] is None and entry["status"] == "no passage"
    assert A.verse_for("money.decimal") is None


@scenario(covers=["spirit.person-decides"])
def test_a_passage_is_proposed_until_kept_and_a_kept_one_stays(project):
    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    assert A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]["status"] == "proposed"
    A.set_status("money.decimal", "kept")
    before = A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]["ref"]
    A.align(reqs, "scroll", Stand(choice=2), log=lambda _: None)
    entry = A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]
    assert entry["status"] == "kept" and entry["ref"] == before


@scenario(covers=["spirit.person-decides"])
def test_a_rejected_passage_is_not_offered_again(project):
    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    first = A.set_status("money.decimal", "rejected")["ref"]
    assert A.verse_for("money.decimal") is None
    stand = Stand()
    A.align(reqs, "scroll", stand, log=lambda _: None)
    assert all(first not in offered for offered in stand.offered)
    entry = A.load_ledger()["texts"]["scroll"]["entries"]["money.decimal"]
    assert entry["ref"] != first and first in entry["rejected"]


@scenario(covers=["spirit.stale-why"])
def test_check_reports_a_changed_why_a_missing_one_and_a_changed_quote(project):
    reqs = load("requirements.yaml")
    assert A.check(reqs)["problems"] == ["no text chosen: run `specdeck spirit align --text ID`"]
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    res = A.check(reqs)
    assert res["problems"] == []
    assert any("nobody has kept" in n for n in res["notes"]) and any("no.reason" in n for n in res["notes"])

    ledger = A.load_ledger()
    ledger["texts"]["scroll"]["entries"]["money.decimal"]["quote"] = "Thou shalt use Decimal."
    A.save_ledger(ledger)
    assert any("isn't what scroll says" in p for p in A.check(reqs)["problems"])

    text = (project / "requirements.yaml").read_text().replace("a cent short", "two cents short")
    (project / "requirements.yaml").write_text(text)
    assert any("money.decimal: its why changed" in p for p in A.check(load("requirements.yaml"))["problems"])

    ledger = A.load_ledger()
    del ledger["texts"]["scroll"]["entries"]["money.decimal"]
    A.save_ledger(ledger)
    assert any("money.decimal: its why has no entry" in p for p in A.check(load("requirements.yaml"))["problems"])


@scenario(covers=["spirit.rule-shows-passage"])
def test_agent_instructions_show_the_passage_unless_rejected(project):
    from specdeck.agents import block

    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    quote = A.verse_for("money.decimal")["quote"]
    assert f'Read with: "{quote}"' in block(reqs, None)
    A.set_status("money.decimal", "rejected")
    assert "Read with" not in block(reqs, None)


@scenario(covers=["spirit.rule-shows-passage"])
def test_a_broken_rule_is_reported_with_its_passage(pytester, monkeypatch):
    monkeypatch.setenv("SPECDECK_SPIRIT_HOME", str(pytester.path / "texts"))
    pytester.makefile(".yaml", requirements="""
requirements:
  - id: money.decimal
    statement: Money amounts shall be Decimal values.
    rationale: A float made a refund a cent short.
    type: design-constraint
""")
    pytester.makefile(".yaml", spirit="""
active: scroll
texts:
  scroll:
    title: The Scroll
    tradition: Test
    entries:
      money.decimal: {why: x, why_hash: y, ref: Scroll 1, quote: A just weight is a delight., status: kept}
""")
    pytester.makepyfile("""
from specdeck import scenario
@scenario(covers=["money.decimal"])
def test_money():
    assert False
""")
    result = pytester.runpytest()
    result.stdout.fnmatch_lines(["*rule money.decimal broken*", '*"A just weight is a delight." (Scroll 1)*'])


@scenario(covers=["spirit.any-tradition"])
def test_a_persons_own_text_from_plain_text_or_json_lines(project):
    jsonl = project / "own.jsonl"
    jsonl.write_text(json.dumps({"ref": "Teaching 1", "text": "Keep a just balance in all your dealing."}) + "\n")
    assert T.add_text("own", jsonl, "Our Teachings", "Family") == 1
    A.align(load("requirements.yaml"), "own", Stand(), log=lambda _: None)
    assert A.load_ledger()["texts"]["own"]["entries"]["money.decimal"]["ref"] == "Teaching 1"
    assert T.load("scroll")[0]["ref"] == "The Scroll, passage 1"


@scenario(covers=["spirit.reading-exists"])
def test_further_reading_names_only_parts_that_exist(project):
    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    reading = A.further_reading(reqs, "scroll", Stand())
    parts = {p["book"] for p in T.load("scroll")}
    assert reading and all(r["read"] in parts for r in reading)
    assert A.load_ledger()["texts"]["scroll"]["reflection"]


def test_report_and_cli_read_the_ledger(project, capsys):
    from specdeck.cli import main
    from specdeck.spirit.report import render

    reqs = load("requirements.yaml")
    A.align(reqs, "scroll", Stand(), log=lambda _: None)
    text = render(reqs, A.load_ledger())
    assert "The Scroll (Test)" in text and A.verse_for("money.decimal")["quote"] in text
    assert main(["spirit", "check", "--fail"]) == 0
    assert main(["spirit", "keep", "money.decimal"]) == 0
    assert main(["spirit", "show", "money.decimal"]) == 0
    assert "kept" in capsys.readouterr().out


def test_parsers_keep_each_traditions_citations(monkeypatch):
    kjv = [{"name": "Proverbs", "chapters": [["{A} false balance is abomination."]]}]
    monkeypatch.setattr(T, "_get", lambda url, retries=3: json.dumps(kjv))
    assert T.kjv() == [{"ref": "Proverbs 1:1", "book": "Proverbs 1", "text": "A false balance is abomination."}]
    quran = {"data": {"surahs": [{"englishName": "Al-Faatiha", "number": 1,
                                  "ayahs": [{"numberInSurah": 1, "text": "In the name of Allah."}]}]}}
    monkeypatch.setattr(T, "_get", lambda url, retries=3: json.dumps(quran))
    assert T.quran()[0]["ref"] == "Surah Al-Faatiha 1:1"
    dhp = {"dhp1:0.3": "1. Pairs ", "dhp1:1": "Intention is the leader; ", "dhp1:2": "intention is first. "}
    monkeypatch.setattr(T, "_get", lambda url, retries=3: json.dumps(dhp))
    monkeypatch.setattr(T, "DHP", ["1-1"])
    assert T.dhammapada() == [{"ref": "Dhammapada 1", "book": "Chapter 1. Pairs", "text": "Intention is the leader; intention is first."}]


def test_long_passages_are_cut_between_sentences():
    chunks = T._chunks(["One sentence here. " * 80], 200)
    assert len(chunks) > 1 and all(len(c) <= 200 for c in chunks)
