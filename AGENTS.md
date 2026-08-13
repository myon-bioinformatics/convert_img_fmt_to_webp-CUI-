# Repository guidance

## Scope

- Read the relevant documentation, source, and existing workflows before changing anything.
- Keep changes scoped to the request. Do not refactor unrelated code or upgrade dependencies without an explicit request.
- Preserve existing CI, deployment, and GitHub Pages configuration unless the task specifically requires a change.

## Workflow changes

- When modifying `.github/workflows/`, ensure actionlint passes.
- Quote YAML scalar values that contain `: ` or special characters.
- Do not broaden workflow permissions or alter deployment settings without a clear need.

## Validation and delivery

- Run the smallest relevant checks already supported by the repository.
- Work on a feature branch and open a pull request; do not merge without explicit approval.
- In each PR, summarize the change, verification performed, and any known limitations.
