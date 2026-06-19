import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain_lint import DocRef, extract_year, topic_key, pick_stale_doc_ids
from brain_eval import EvalQuestion, run_eval, parse_verdict


def test_extract_year():
    assert extract_year("vacation_2024") == 2024
    assert extract_year("vacation_2026.md") == 2026
    assert extract_year("billing") is None


def test_topic_key_groups_versions():
    assert topic_key("vacation_2024.md") == "vacation"
    assert topic_key("vacation_2026.md") == "vacation"
    assert topic_key("billing") == "billing"


def test_pick_stale_doc_ids_removes_older_version():
    docs = [
        DocRef("id-2024", "vacation_2024"),
        DocRef("id-2026", "vacation_2026"),
        DocRef("id-bill", "billing"),
    ]
    assert pick_stale_doc_ids(docs) == ["id-2024"]


def test_pick_stale_doc_ids_no_conflict():
    docs = [DocRef("a", "billing"), DocRef("b", "retention")]
    assert pick_stale_doc_ids(docs) == []


def test_parse_verdict():
    assert parse_verdict('{"pass": true, "reason": "ok"}') == (True, "ok")
    assert parse_verdict('{"pass": false, "reason": "no cite"}') == (False, "no cite")


def test_run_eval_scores_with_fakes():
    qs = [EvalQuestion("a", "Q1?", "rubric"), EvalQuestion("b", "Q2?", "rubric")]

    async def ask(question):
        return "answer:" + question

    async def judge(rubric, answer):
        return (answer == "answer:Q1?", "")

    report = asyncio.run(run_eval(qs, ask, judge))
    assert report.total == 2
    assert report.score == 1


def test_run_eval_counts_ask_error_as_fail():
    qs = [EvalQuestion("a", "Q1?", "rubric")]

    async def ask(question):
        raise RuntimeError("boom")

    async def judge(rubric, answer):
        return (True, "")

    report = asyncio.run(run_eval(qs, ask, judge))
    assert report.score == 0
    assert report.rows[0].passed is False


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok", name)
            except AssertionError as exc:
                failures += 1
                print("FAIL", name, exc)
    print("ALL PASS" if failures == 0 else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
