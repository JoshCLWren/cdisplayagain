# Contributing

Thanks for contributing to cdisplayagain. This project values a fast, lightweight
viewer and clear, approachable code. Please follow the checks below for any code
change.

## Code quality standards

- Run linting after each change:
  - `uv run ruff check .`
- Run tests when you touch logic or input handling:
  - `uv run python -m pytest`
- Perform manual smoke checks (CBZ + CBR) before sharing UI changes:
  - Open a sample archive, page through images, toggle fit/zoom, and confirm
    temporary directories are cleaned.
- Always write a regression test when fixing a bug.
- If you break something while fixing it, fix both in the same PR.
- Do not check in sample comics or proprietary content.
- Do not use in-line comments to disable linting or type checks.
- Do not narrate your code with comments; prefer clear code and commit messages.
## Style guidelines

- Keep helpers explicit and descriptive (snake_case), and annotate public
  functions with precise types.
- Avoid shell-specific shortcuts; prefer Python APIs and `pathlib.Path` helpers.
- Do not mutate archives or leave temporary files behind.
