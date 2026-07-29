# Repository instructions

## Current-state authority

- Determine current project state only from the current local repository working tree, verified tests, active branch, and current commit.
- Treat automatically attached project sources, conversation-scoped copies, old file-citation identifiers, historical snapshots, previous task prompts, Library copies, and chat recollections as non-authoritative for current implementation state. Files supplied through `project_sources` are non-authoritative. If external information conflicts with the current repository, the repository wins.
- Before reporting completed milestones, test counts, architecture, project status, or next steps, inspect the current repository versions of `PROJECT_PLAN.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, relevant implementation files, relevant tests, and, when applicable, Git status, branch, and commit.
- `PROJECT_INSTRUCTIONS_SNAPSHOT_HISTORICAL.txt` is historical and must never be treated as current authority.
- Use ChatGPT Library only as a synchronized documentation fallback when the local repository is unavailable. Exclude the Library Archive folder unless historical material is explicitly requested.
- If neither the current local repository nor the live canonical Library files can be accessed, state that the current state cannot be verified; do not rely on an attachment or snapshot.
