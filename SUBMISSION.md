# Team Submission

## Team

- Team name: Chris
- Participants: Christopher Weidner
- Company Brain / project name: Self-Healing Company Brain

## Company Brain Overview

A Company Brain for new-hire / employee questions that **measurably gets smarter
from feedback**. It answers questions from a knowledge graph of company docs,
and when an answer is weak it does two things: it rewrites its own answering
**skill**, and it **distills new team knowledge from session memory into the
permanent graph** so the same question is answered correctly on the next run.
A lint pass keeps the graph coherent by pruning superseded documents.

- Domain or data sources: company knowledge — HR/vacation, billing ownership,
  retention metric, onboarding (`company_docs/*.md`) plus team knowledge that
  arrives as conversation/feedback at runtime.
- Primary use case: an onboarding buddy that reliably answers employee questions
  and absorbs new tribal knowledge the moment it's told.
- What makes it stand out: a **hard, reproducible before/after metric (2/5 → 5/5)**
  driven by the two-tier distillation loop, plus a working self-rewriting skill
  and a graph linter that resolves a real stale-vs-current conflict.

## The Three Operations

### Ingest

- What goes in: company markdown docs, the agent's skills (`SKILL.md` files), and
  new team facts delivered during a session.
- How it is captured: `cognee.remember(DOCS_DIR, dataset_name=...)` for docs,
  `cognee.remember(SKILLS_DIR, content_type="skills")` for skills, and
  `cognee.remember(fact, session_id=...)` for runtime team knowledge.
- Code entry point: `demo.py` → `ingest()` and `teach()`; skill at
  `my_skills/ingestor/SKILL.md`.

### Query + Self-improve

- How users query: `cognee.search(question, query_type=SearchType.GRAPH_COMPLETION,
  datasets=["company-brain"], session_id=...)` — retrieves from the graph and answers.
- Where feedback comes from: an automated eval (`brain_eval.py`) of 5 questions,
  each graded PASS/FAIL by an **LLM-judge critic** (gpt-4o-mini) against a rubric.
- How feedback updates the brain: (1) a `SkillRunEntry` with the eval failures and
  a low `success_score` triggers a proposed `qa-answerer/SKILL.md` rewrite, applied
  via `improve_skill(apply=True)`; (2) new team facts written to session memory are
  promoted into the permanent graph via `cognee.improve(dataset, session_ids=[...])`.
- Code entry point: `demo.py` → `make_ask()`, `self_improve()`, `distill()`; skill at
  `my_skills/qa-answerer/SKILL.md`.

### Lint

- What "linting" means: detect documents that cover the same topic in conflicting
  versions and prune the superseded one (here: `vacation_2024.md` is superseded by
  `vacation_2026.md`).
- How it runs: on-demand each cycle, after distillation.
- Code entry point: `demo.py` → `lint()` + `brain_lint.pick_stale_doc_ids()` →
  `cognee.forget(data_id=..., dataset=...)`; skill at `my_skills/linter/SKILL.md`.

## Self-Improvement Evidence

The brain is tested on 5 questions: 3 are **facts it has never seen** (all-hands
time, guest-WiFi password, office manager) and 2 are **controls** already in the
docs (billing owner, retention formula).

### Baseline Run

- Query / task: answer all 5 eval questions before any feedback.
- Result: cannot answer any of the 3 unseen facts; answers the 2 controls.
- Score (own metric): **2 / 5**.
- Recorded feedback (the `SkillRunEntry` we write):

```text
error_type:     low_eval_score
error_message:  Eval failures: allhands (no correct schedule); wifi (no correct
                password); office_mgr (does not name Priya Shah)
feedback:       -1.0
success_score:  0.4
```

### Improved Run

- Query / task: the same 5 questions, in a **fresh session**, after one feedback cycle.
- Result: all 3 previously-unknown facts are now answered correctly; controls stay green.
- Score: **5 / 5**.
- What changed in the brain between runs: the three team facts were distilled from
  session memory into the permanent graph (`cognee.improve`), so a fresh-session
  query now retrieves them; the `qa-answerer` skill was rewritten from feedback; and
  the stale `vacation_2024` document was pruned.

```text
Before:
  Q: Who is the office manager?
  A: "The office manager is a key individual responsible for overseeing operations..."  (no name -> FAIL)
  PROOF score: 2/5

After:
  Q: Who is the office manager?
  A: "The office manager is Priya Shah. She handles building access badges..."  (PASS)
  Q: What is the guest WiFi password?      -> "Acme-Welcome-2026" (PASS)
  Q: When is the all-hands meeting?        -> "first Monday of every month at 10am" (PASS)
  Stale docs pruned: ['vacation_2024']
  PROOF score: 5/5
```

## Architecture

```text
[company docs + skills + new team facts]
        |
        v
[ cognee instance — session memory ]   <- hot, per-conversation (session_id="onboarding-feedback")
        |
        | distillation: cognee.improve(dataset, session_ids=[...])
        | (feedback weights on used nodes + session Q&A cognified into the graph)
        v
[ cognee instance — permanent graph ]  <- durable, cross-session (no session_id)
        |
        v
[ query: GRAPH_COMPLETION ]  ->  [ eval + LLM judge -> SkillRunEntry -> improve_skill ]
        |
        v
[ lint: forget superseded docs ]  ->  [ cognee.push() to Cognee Cloud ]
```

Components: `demo.py` (orchestration), `brain_eval.py` (eval + LLM judge),
`brain_lint.py` (conflict/stale detection), `my_skills/{ingestor,linter,qa-answerer}`.

### Cognee Cloud (used — `serve` + `push` + live `search`)

Yes. We connect with `cognee.serve(...)`, host the brain in the managed instance
with `cognee.push(...)`, and query knowledge live on Cloud with `cognee.search(...)`.

- **What we write to session memory (`session_id="onboarding-feedback"`):** the new
  team facts and the run's `SkillRunEntry` feedback — the hot, per-conversation
  scratchpad.
- **What goes straight to the permanent graph (no `session_id`):** the seed company
  docs and the ingested skills. Knowledge ingested to Cloud with
  `cognee.remember(text, dataset_name=...)` is cognified server-side and is
  immediately queryable there — verified live: *"Who is the office manager?"* →
  *"Priya Shah"* answered by the Cloud instance.
- **How/when content is distilled into the permanent graph:** after the baseline
  eval, `cognee.improve(dataset, session_ids=["onboarding-feedback"])` applies
  feedback weights to the nodes used and cognifies the session Q&A into durable
  graph nodes. We then `cognee.push("company-brain")` the healed graph to Cloud for
  durable, cross-session hosting.
- **What stays session-only vs promoted:** raw turn text stays in session; the
  durable facts and the feedback signal are promoted into the permanent graph.
- **Proof the brain got smarter:** baseline **2/5** → improved **5/5** in a fresh
  session (see Self-Improvement Evidence). Push result:
  `status='completed', nodes=62, edges=87`.

> Transparency: on our assigned tenant the distillation step (`cognee.improve` with
> `session_ids`) runs in our local cognee instance (the Cloud build returns 404 for
> that endpoint and does not persist `session_id` writes), so we distill locally and
> push the result to Cloud, where the brain's knowledge is queryable via
> `cognee.remember` + `cognee.search`.

## Agents / Skills

```text
Skill path(s): my_skills/ingestor/SKILL.md, my_skills/linter/SKILL.md,
               my_skills/qa-answerer/SKILL.md
Roles:
  - Ingestor: pull raw company knowledge into the graph, tagged + deduped
  - Querier:  answer questions from the graph and cite sources (qa-answerer)
  - Linter:   find conflicting/stale entries and prune the outdated one
  - Critic:   LLM judge (gpt-4o-mini) that scores each answer in brain_eval.py
```

## Reproduction

```bash
# from meta-brain/
uv pip install --python .venv/bin/python cognee==1.2.0.dev1 fastembed
python demo.py
```

Environment variables required (in `.env`):

```text
COGNEE_CLOUD_URL    # your dedicated Cognee Cloud instance URL (https://your-instance.cognee.ai)
COGNEE_API_KEY      # your Cognee Cloud API key
LLM_API_KEY         # OpenAI key (chat access; gpt-4o-mini)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=fastembed         # local embeddings (provided key has no embedding access)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

## Demo

The whole demo is one command — `python demo.py` — which prints, in order:
BEFORE 2/5 → skill rewrite → pruned stale doc → AFTER 5/5 → Cloud push. Talk over it.

3-minute spoken script (with what's on screen):

```text
0:00  Idea — "A Company Brain shouldn't be a static FAQ. Ours learns from its
      team and gets measurably smarter. Watch the score." Run: python demo.py

0:20  Ingest — point at "Ingested 3 skills: ingestor, linter, qa-answerer" and
      company_docs/. "Three operations as skills: Ingest, Query, Lint. Docs are in
      the permanent graph."

0:40  Query BEFORE — point at "BEFORE ... 2/5": the 3 new team facts (all-hands,
      WiFi, office manager) FAIL — "the brain has never been told these." The 2
      doc-based controls PASS.

1:10  Self-improve + distill + lint — "Feedback fires three things:" (a) the
      qa-answerer SKILL.md is rewritten and applied (show BEFORE/AFTER skill body);
      (b) cognee.improve distills the session-memory facts into the PERMANENT graph
      — the two-tier memory core; (c) the linter forgets the stale vacation_2024 doc
      (show "Stale docs pruned: ['vacation_2024']").

1:50  Query AFTER — point at "AFTER ... 5/5" in a FRESH session: all 3 facts now
      answered. "Same questions, new session — it can only know these because they
      were distilled into the graph. PROOF: 2/5 -> 5/5."

2:20  Cloud — point at "Pushed 'company-brain' to Cognee Cloud: ... completed".
      "Built and self-improved locally, hosted on Cognee Cloud; knowledge is also
      queryable live there via cognee.search."

2:45  Next — "Automate feedback from real users, schedule the linter, scale on Cloud."
```

Tip: if demoing a live query *on Cloud*, ask a non-sensitive fact (e.g. "Who is the
office manager?"). The model refuses to read out the WiFi *password* on Cloud.

## Links

- Repo: https://github.com/christopherweidner/Cognee-Hackathon
- Slides / writeup: this file
- Anything else: embeddings run locally via fastembed because the provided OpenAI
  key is chat-only; completions use gpt-4o-mini.
