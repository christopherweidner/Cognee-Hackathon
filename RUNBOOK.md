# Company Brain — Step-by-Step Runbook

A complete, do-anything guide for the Cognee Cloud Hackathon.
Project: **Onboarding Buddy** — a Company Brain that learns from feedback.

Everything you copy-paste is below. Follow the steps in order.

---

## 0. What you already have in this folder

```
company_docs/      5 fake company docs (vacation_2024 & 2026 conflict on purpose)
my_skills/         qa-answerer/ and linter/ skills (the agent's instructions)
demo.py            the runnable before/after demo
RUNBOOK.md         this file
```

You do NOT need any API keys before the event. They hand you a Cognee Cloud
URL + key + an OpenAI key at kickoff.

---

## 1. One-time setup (5 min, do at the event)

Open a terminal in this folder, then run each line:

```bash
# create + activate a clean python environment
uv venv && source .venv/bin/activate

# install the exact hackathon version
uv pip install cognee==1.2.0.dev1

# paste the LLM key they give you at kickoff
export LLM_API_KEY="<key-they-give-you>"

# REQUIRED on the dev build: skip a buggy pre-flight LLM test
export COGNEE_SKIP_CONNECTION_TEST=true
```

If `uv` is missing: `pip install uv` first. Python must be 3.10–3.14.

> The two `export` lines only last for the current terminal window. If you
> open a new terminal, run them again — or put them in a `.env` file in this
> folder (cognee auto-loads it):
>
> ```
> LLM_API_KEY=<key-they-give-you>
> COGNEE_SKIP_CONNECTION_TEST=true
> ```

---

## 2. Run the demo locally (2 min)

```bash
python demo.py
```

You should see three blocks print:
- **BEFORE** — a weak answer (may use the old 2024 vacation doc, no source).
- *Feedback recorded* — the brain rewrites its own skill.
- **AFTER** — a better answer (HR portal, with a source cited).

That's the whole self-improvement loop working. If it runs, you have a
submittable project already.

---

## 3. See the brain visually (optional, great for the demo)

```bash
cognee-cli -ui
```

Opens a graph explorer at http://localhost:3000. Show the knowledge graph
growing — judges love the visual.

---

## 4. Earn the Cognee Cloud bonus (5 min, do this — it's free points)

At kickoff they give you a Cloud URL + key. Then:

```bash
export COGNEE_CLOUD_URL="https://your-instance.cognee.ai"
export COGNEE_API_KEY="ck_..."
```

Open `demo.py`, find this line in `main()` and remove the `#`:

```python
    # await push_to_cloud()   ->   await push_to_cloud()
```

Run `python demo.py` again. Your brain now lives in Cognee Cloud. Mention this
in the submission — it counts toward "Best use of Cognee Cloud."

---

## 5. The 3-minute demo script (rehearse this 2–3 times)

1. **Setup line (10s):** "Meet the Onboarding Buddy — a company brain that
   gets smarter every time it's used."
2. **BEFORE (40s):** Ask *"How do I request vacation?"* It answers weakly /
   from the outdated doc. Score 0.3. "Not good enough."
3. **The learning (40s):** Give thumbs-down. Show the brain rewrite its own
   skill file (the diff) and flag the 2024 doc as stale.
4. **AFTER (40s):** Ask the *same* question. Now: "Through the HR portal
   (source: vacation_2026.md); the 2024 email process is deprecated."
   Score 0.9.
5. **Close (30s):** Show the score jump 0.3 → 0.9 and "running on Cognee
   Cloud." Done.

The single most important thing: the **same question, asked twice, gets
visibly better**. Rehearse until that lands cleanly.

---

## 6. How to refine if you have extra time (in priority order)

1. **Lint demo** — wire `my_skills/linter` to actually report the
   vacation 2024 vs 2026 conflict on screen. Most teams skip lint; doing it
   stands out.
2. **More questions** — add a second before/after (e.g. retention metric) to
   prove it's not a one-off.
3. **Real feedback UI** — a tiny thumbs up/down in the terminal instead of a
   hardcoded 0.3 score, so judges can click it live.
4. **More docs** — drop your own real docs into `company_docs/` to show it
   works on anything.

Don't add features at the cost of rehearsal. A smooth 3-min demo beats more code.

---

## 7. Submission checklist (due 9:00 PM)

Copy `templates/SUBMISSION.md` from the hackathon repo and fill in:

- [ ] Short writeup: idea = Onboarding Buddy; loop = feedback rewrites the
      qa-answerer skill + distills corrections into the graph.
- [ ] The code (this whole folder).
- [ ] Before/after evidence: screenshot the BEFORE 0.3 and AFTER 0.9 output.
- [ ] Note you used Cognee Cloud (`cognee.serve` / `cognee.push`).
- [ ] 3-minute demo (rehearsed).

---

## 8. If something breaks

- **`model_json_schema` / "LLM connection test timed out"** → buggy pre-flight
  test in the dev build. Run `export COGNEE_SKIP_CONNECTION_TEST=true` and
  re-run. (Already in the `.env` above.)
- **`cognee` not found** → activate the venv: `source .venv/bin/activate`.
- **LLM / auth error** → re-check `export LLM_API_KEY=...` is set in THIS terminal.
- **`remember()` returns a dict, not an object** → read items as
  `result["items"]` instead of `result.items` (known local-backend quirk).
- **Skill name looks like `skill-0000`** → that's fine; the code already reads
  the real name back from `remembered.items`.
- **Cloud push fails** → make sure both `COGNEE_CLOUD_URL` and `COGNEE_API_KEY`
  are exported, and that you ran `cognee.serve(...)` first (push_to_cloud does).

---

Reference: hackathon brief and https://docs.cognee.ai/
