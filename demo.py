"""
Self-Healing Company Brain — hackathon demo.

Proves the brain gets measurably smarter from feedback:

  1. Build the brain locally (docs + skills). Skills are local-only; the
     working OpenAI key is chat-only so embeddings run via fastembed.
  2. Score it on a fixed 5-question eval -> BEFORE score (it fails: the
     starting skill guesses, never cites, and trusts the outdated 2024 doc).
  3. One feedback round fires three coordinated effects:
       * Self-improvement loop: score the run, propose a SKILL.md rewrite,
         apply it (improve_skill).
       * Distillation (two-tier memory): cognee.improve(session_ids=[...])
         promotes the session-memory Q&A + feedback weights into the
         permanent graph.
       * Lint: detect the vacation_2024 vs vacation_2026 conflict and
         cognee.forget the superseded doc.
  4. Re-score -> AFTER score jumps. The delta is the proof.
  5. push() the healed brain to Cognee Cloud (the Cloud bonus).

Run:  python demo.py
"""

import os

# --- must be set BEFORE importing cognee so config picks them up ---
os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("COGNEE_LOG_FILE", "false")
os.environ.setdefault("EMBEDDING_PROVIDER", "fastembed")
os.environ.setdefault("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "384")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import asyncio
from uuid import UUID

import cognee
from cognee import SearchType
from cognee.context_global_variables import set_database_global_context_variables
from cognee.memory import SkillRunEntry
from cognee.modules.data.methods import get_dataset_data
from cognee.modules.memify.skill_improvement import improve_skill
from cognee.modules.pipelines.layers.resolve_authorized_user_datasets import (
    resolve_authorized_user_datasets,
)
from cognee.modules.tools.resolve_skills import find_skill_by_name

from brain_eval import EVAL_QUESTIONS, llm_judge, run_eval
from brain_lint import DocRef, pick_stale_doc_ids

DATASET = "company-brain"
DOCS_DIR = "./company_docs"
SKILLS_DIR = "./my_skills"
FEEDBACK_SESSION = "onboarding-feedback"

# Team knowledge the brain has NOT seen yet. In a real Company Brain these
# arrive as chat/feedback during a session; here we write them to session
# memory, then distill them into the permanent graph via cognee.improve().
# These are deliberately specific, unguessable facts (so a brain that hasn't
# learned them genuinely cannot answer) on topics with no competing doc.
LEARNED_FACTS = [
    "The company all-hands meeting is held on the first Monday of every month at 10am.",
    "The guest WiFi password is Acme-Welcome-2026.",
    "The office manager is Priya Shah; she sits at desk 4B and handles building "
    "access badges.",
]


def _items(result):
    return result.get("items", []) if isinstance(result, dict) else getattr(result, "items", [])


def _dataset_id(result):
    return result["dataset_id"] if isinstance(result, dict) else result.dataset_id


def _unwrap(answer):
    if isinstance(answer, list) and answer:
        return _unwrap(answer[0])
    if isinstance(answer, dict) and "search_result" in answer:
        return _unwrap(answer["search_result"])
    return answer


async def ingest():
    """Fresh slate, then load docs + skills into the local brain."""
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await cognee.remember(DOCS_DIR, dataset_name=DATASET)
    remembered = await cognee.remember(SKILLS_DIR, dataset_name=DATASET, content_type="skills")
    skill_names = [i["name"] for i in _items(remembered) if i.get("kind") == "skill"]
    if not skill_names:
        raise RuntimeError("No skills ingested.")
    user, datasets = await resolve_authorized_user_datasets(UUID(str(_dataset_id(remembered))))
    print(f"Ingested {len(skill_names)} skills: {skill_names}")
    return skill_names, user, datasets[0]


def make_ask(session_id):
    """Return an `ask(question)` that queries the brain in a fresh session.

    Uses GRAPH_COMPLETION: it retrieves directly from the knowledge graph and
    answers, which deterministically tests "is this knowledge in the graph?" —
    exactly what the distillation proof needs.
    """
    async def ask(question):
        answer = await cognee.search(
            question,
            query_type=SearchType.GRAPH_COMPLETION,
            datasets=[DATASET],
            session_id=session_id,
        )
        return _unwrap(answer)

    return ask


async def skill_body(name, dataset, user):
    owner_id = getattr(dataset, "owner_id", None) or getattr(user, "id", None)
    async with set_database_global_context_variables(dataset.id, owner_id):
        skill = await find_skill_by_name(name, dataset_id=dataset.id)
    return skill.procedure.strip() if skill else ""


async def self_improve(skill_names, user, dataset, report):
    """Self-improvement loop: score -> propose SKILL.md rewrite -> apply."""
    target = next((s for s in skill_names if "qa" in s or "answer" in s), skill_names[0])
    fails = "; ".join(f"{r.id}: {r.reason}" for r in report.rows if not r.passed) or "weak answers"
    proposal = await cognee.remember(
        SkillRunEntry(
            selected_skill_id=target,
            task_text="Answer company questions accurately and with sources",
            result_summary=f"Eval failures: {fails}",
            success_score=report.score / max(report.total, 1),
            feedback=-1.0,
        ),
        dataset_name=DATASET,
        session_id=FEEDBACK_SESSION,
        skill_improvement={"skill_name": target, "apply": False, "score_threshold": 0.9},
    )
    proposal_id = next(
        (i["proposal_id"] for i in _items(proposal) if i.get("kind") == "skill_improvement_proposal"),
        None,
    )
    if proposal_id is None:
        raise RuntimeError("No skill-improvement proposal was generated.")
    before = await skill_body(target, dataset, user)
    await improve_skill(target, dataset=dataset, user=user, proposal_id=proposal_id, apply=True)
    after = await skill_body(target, dataset, user)
    return target, before, after


async def teach(facts):
    """Write new team knowledge into the fast session-memory tier."""
    for fact in facts:
        await cognee.remember(fact, dataset_name=DATASET, session_id=FEEDBACK_SESSION)


async def distill():
    """Two-tier memory: distill session memory into the permanent graph so the
    facts become part of the durable brain (retrievable in any future session)."""
    await cognee.improve(dataset=DATASET, session_ids=[FEEDBACK_SESSION])


async def lint(dataset):
    """Forget superseded documents (e.g. the outdated 2024 vacation policy)."""
    data = await get_dataset_data(dataset.id)
    docs = [DocRef(str(d.id), d.name) for d in data]
    stale_ids = set(pick_stale_doc_ids(docs))
    for data_id in stale_ids:
        await cognee.forget(data_id=UUID(data_id), dataset=DATASET)
    return [d.name for d in docs if d.data_id in stale_ids]


async def push_to_cloud():
    url = os.environ.get("COGNEE_CLOUD_URL")
    key = os.environ.get("COGNEE_API_KEY")
    if not (url and key):
        print("No COGNEE_CLOUD_URL / COGNEE_API_KEY — skipping Cloud push.")
        return
    try:
        await cognee.serve(url=url, api_key=key)
        print(f"Pushed '{DATASET}' to Cognee Cloud: {await cognee.push(DATASET)}")
    except Exception as exc:  # best-effort: never break the local demo
        print(f"Cloud push skipped ({type(exc).__name__}): {exc}")


def print_report(label, report):
    print(f"\n===== {label}: {report.score}/{report.total} =====")
    for r in report.rows:
        print(f"  [{'PASS' if r.passed else 'FAIL'}] {r.id}: {r.reason}")


async def main():
    skill_names, user, dataset = await ingest()

    # 1. Baseline: the brain can't answer the learnable questions yet.
    before = await run_eval(EVAL_QUESTIONS, make_ask("eval-before"), llm_judge)
    print_report("BEFORE (brain has not learned yet)", before)

    # 2. Team feedback arrives in the fast session-memory tier.
    await teach(LEARNED_FACTS)

    # 3. Self-improvement loop (visible artifact): score the run, propose a
    #    SKILL.md rewrite, apply it.
    target, body_before, body_after = await self_improve(skill_names, user, dataset, before)

    # 4. Distillation (the core): promote session memory into the permanent graph.
    await distill()

    # 5. Lint (visible artifact): forget the superseded 2024 vacation policy.
    pruned = await lint(dataset)

    print(f"\nSkill '{target}' rewritten from feedback. Stale docs pruned: {pruned}")
    print(f"--- skill BEFORE ---\n{body_before}\n--- skill AFTER ---\n{body_after}")

    # 6. Re-test in a fresh session: the only way the brain can now answer the
    #    learnable questions is from the distilled permanent graph.
    after = await run_eval(EVAL_QUESTIONS, make_ask("eval-after"), llm_judge)
    print_report("AFTER (distilled into permanent graph)", after)
    print(f"\nPROOF: the brain improved {before.score}/{before.total} -> {after.score}/{after.total}")

    await push_to_cloud()


if __name__ == "__main__":
    asyncio.run(main())
