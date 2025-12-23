.PHONY: lint pytest sync venv run smoke

lint:
	uv run ruff check .

pytest:
	uv run pytest

sync:
	uv sync --locked

venv:
	uv venv

run:
	@if [ -z "$(FILE)" ]; then echo "Usage: make run FILE=path/to/comic.cbz"; exit 1; fi
	uv run python cdisplayagain.py "$(FILE)"

smoke:
	@if [ -z "$(FILE)" ]; then echo "Usage: make smoke FILE=path/to/comic.cbz"; exit 1; fi
	@echo "Manual smoke test checklist:"
	@echo "- Open both CBZ and CBR archives (CBR requires unar)"
	@echo "- Page through images to confirm ordering"
	@echo "- Toggle fit-to-screen, fit-to-width, and zoom modes"
	@echo "- Confirm temp directories are cleaned on exit"
	uv run python cdisplayagain.py "$(FILE)"
