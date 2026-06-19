import asyncio
import os
import cognee
from cognee import SearchType
from cognee.memory import SkillRunEntry
from cognee.modules.engine.operations.setup import setup

DATASET = "meta-brain"
SESSION = "dev-session-1"
SKILLS_DIR = "./my_skills"
DOCS_DIR = "./docs"

async def main():
    # 1. Connect to Cloud (Secures your Cloud Bonus!)
    await cognee.serve(
        url=os.environ["COGNEE_CLOUD_URL"],
        api_key=os.environ["COGNEE_API_KEY"],
    )
    
    # 2. Reset the graph so we have a clean slate for testing
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await setup()

    print("🧠 1. Ingesting knowledge and skills...")
    # Ingest the architecture rules
    await cognee.remember(DOCS_DIR, dataset_name=DATASET)
    
    # Ingest the skills
    remembered = await cognee.remember(SKILLS_DIR, dataset_name=DATASET, content_type="skills")
    
    # Extract the actual name Cognee gave our skill
    skill_to_improve = None
    
    # Check if 'remembered' is a plain dictionary
    if isinstance(remembered, dict):
        # We read defensively from the "items" key
        items_list = remembered.get("items", [])
    else:
        # It's an object, we read its items property
        items_list = getattr(remembered, "items", [])

    for item in items_list:
        if item.get("kind") == "skill":
            skill_to_improve = item["name"]
            break

        if not skill_to_improve:
            print("Failed to find ingested skill. Check your SKILL.md file.")
            return

    print(f"✅ Loaded skill: {skill_to_improve}")

    print("\n🤖 2. Running Baseline Query...")
    task_prompt = "Write a Python calculator script."
    answer = await cognee.search(
        task_prompt,
        query_type=SearchType.AGENTIC_COMPLETION,
        datasets=[DATASET],
        skills=[skill_to_improve],
        max_iter=3,
        session_id=SESSION,
    )
    print("\n--- Baseline Answer ---")
    print(answer)
    print("-----------------------\n")

    print("📉 3. Scoring the run as a failure (0.2) because it didn't use a REPL...")
    
    # We record feedback that the bot failed our architectural rule
    proposal_result = await cognee.remember(
        SkillRunEntry(
            selected_skill_id=skill_to_improve,
            task_text=task_prompt,
            result_summary="The agent wrote a standard calculator, completely ignoring the architecture rule requiring a REPL loop.",
            success_score=0.2,
            feedback=-1.0, # Negative feedback triggers the rewrite
        ),
        dataset_name=DATASET,
        session_id=SESSION,
        skill_improvement={
            "skill_name": skill_to_improve,
            "apply": True, # We tell it to automatically apply the new rule!
            "score_threshold": 0.9,
        },
    )

    print("✨ 4. Skill successfully rewritten based on feedback!")
    print("Check your my_skills/coder/SKILL.md file to see the AI's new brain.")

if __name__ == "__main__":
    asyncio.run(main())