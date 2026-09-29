# Content prompts
Run these in Claude Code / Codex at the ROOT of this repo. Full wording: see the official Content Guide PDF; below are repo-specific angles.

## Prompt 1: 20 titles
Use the guide's Prompt 1 verbatim. Angles the code supports:
- Recall vs. no-recall on the same LLM (the honest ablation)
- Novel incidents don't improve, repeats do (a real limitation)
- Storing team rules as memories instead of prompt text
- Retaining the agent's own wrong suggestions

## Prompt 2: article (`article.md`)
Use the guide's Prompt 2 verbatim with your chosen title. Point it at `app/agent.py` (`triage`, `resolve`), `app/memory.py`, and `docs/results.json`. Replace mock numbers with your real run. Include the three Hindsight links.

## Prompt 3: LinkedIn post (<800 chars)
Use the guide's Prompt 3 verbatim. Add the repo link to the main post body.

## Prompt 4/5: video script + 5 titles
Use `docs/DEMO_SCRIPT.md` as the skeleton with the guide's video-script prompt.

## Prompt 6: thumbnail (Google Nano Banana, 16:9)
Use the guide's thumbnail prompt with your script and a team photo.
