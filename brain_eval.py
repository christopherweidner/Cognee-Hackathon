"""Eval harness for the Company Brain: fixed questions + LLM-judge grading."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

# A judge takes (rubric, answer) and returns (passed, reason).
Judge = Callable[[str, str], Awaitable[tuple[bool, str]]]
# An ask takes a question and returns the brain's answer.
Ask = Callable[[str], Awaitable[str]]


@dataclass
class EvalQuestion:
    id: str
    question: str
    rubric: str


@dataclass
class EvalRow:
    id: str
    question: str
    answer: str
    passed: bool
    reason: str


@dataclass
class EvalReport:
    rows: list[EvalRow]

    @property
    def score(self) -> int:
        return sum(1 for r in self.rows if r.passed)

    @property
    def total(self) -> int:
        return len(self.rows)


# Two kinds of eval questions:
#  * LEARNABLE — the answer is NOT in the seed docs. The brain can only answer
#    these AFTER team feedback is distilled from session memory into the graph.
#    BEFORE: the brain refuses (FAIL). AFTER: the brain knows (PASS).
#  * CONTROL — already answerable from the seed docs. PASS before and after,
#    proving distillation + lint did not damage existing knowledge.
EVAL_QUESTIONS: list[EvalQuestion] = [
    EvalQuestion(
        "allhands",
        "When is the company all-hands meeting held?",
        "A correct answer states the all-hands meeting is on the first Monday of "
        "every month at 10am. If the answer says it does not know or gives a "
        "different time, it FAILS.",
    ),
    EvalQuestion(
        "wifi",
        "What is the guest WiFi password?",
        "A correct answer states the guest WiFi password is Acme-Welcome-2026. "
        "If it says it does not know or gives a different password, it FAILS.",
    ),
    EvalQuestion(
        "office_mgr",
        "Who is the office manager?",
        "A correct answer names Priya Shah as the office manager. If it says it "
        "does not know, gives only a generic description, or names someone else, "
        "it FAILS.",
    ),
    EvalQuestion(
        "billing_owner",
        "Who owns the billing system?",
        "A correct answer says the billing system is owned by the Payments team. "
        "Naming the contact (Dana Lee) is a nice-to-have but not required.",
    ),
    EvalQuestion(
        "retention_calc",
        "How is retention calculated?",
        "A correct answer describes retention as the ratio of users active this "
        "month who were also active last month, divided by users active last "
        "month. Mentioning that trial accounts are excluded is a plus but not "
        "required.",
    ),
]


async def run_eval(questions: list[EvalQuestion], ask: Ask, judge: Judge) -> EvalReport:
    rows: list[EvalRow] = []
    for q in questions:
        try:
            answer = await ask(q.question)
        except Exception as exc:  # a failed query is a failed answer
            rows.append(EvalRow(q.id, q.question, f"<error: {exc}>", False, "query failed"))
            continue
        passed, reason = await judge(q.rubric, str(answer))
        rows.append(EvalRow(q.id, q.question, str(answer), passed, reason))
    return EvalReport(rows)


def parse_verdict(raw: str) -> tuple[bool, str]:
    """Parse a judge's JSON reply: {"pass": bool, "reason": str}."""
    data = json.loads(raw)
    return bool(data["pass"]), str(data.get("reason", ""))


async def llm_judge(rubric: str, answer: str) -> tuple[bool, str]:
    """Grade an answer against a rubric using gpt-4o-mini (the key has chat access)."""
    import openai

    client = openai.AsyncOpenAI(api_key=os.environ["LLM_API_KEY"])
    prompt = (
        "You grade an answer from a company knowledge assistant.\n\n"
        f"RUBRIC (what a correct answer must satisfy):\n{rubric}\n\n"
        f"ANSWER:\n{answer}\n\n"
        'Reply with strict JSON only: {"pass": true or false, "reason": "<short>"}'
    )
    resp = await client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return parse_verdict(resp.choices[0].message.content)
