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

## Style guidelines

- Keep helpers explicit and descriptive (snake_case), and annotate public
  functions with precise types.
- Avoid shell-specific shortcuts; prefer Python APIs and `pathlib.Path` helpers.
- Do not mutate archives or leave temporary files behind.
