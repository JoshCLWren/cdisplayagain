.PHONY: help lint pytest sync venv run smoke clean-build build build-onedir package-linux install install-bin install-desktop mime-query redo ci-test-debian ci-test-local ci-build-image githook install-githook deploy build-macos install-macos uninstall-macos package-macos pytest-container

# Configuration
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib
XDG_DATA_HOME ?= $(HOME)/.local/share
APPDIR ?= $(XDG_DATA_HOME)/applications
UNAME := $(shell uname)
MACOS_APPDIR ?= /Applications
# Recursive (=) so the helper only runs for the targets that need Tk on macOS.
TK_ENV = $(shell bash scripts/tk-env.sh)

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:  ## Run code linting
	bash scripts/lint.sh

install-githook:  ## Install pre-commit hook for new developers
	@mkdir -p .git/hooks
	@cp .githooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed to .git/hooks/pre-commit"

githook: install-githook  ## Run lint checks manually (installs pre-commit hook if missing)
	bash scripts/lint.sh

pytest:  ## Run tests (xvfb on Linux; macOS opens real windows, see pytest-container)
	@if [ "$(UNAME)" = "Darwin" ]; then \
		echo "NOTE: macOS has no xvfb, so this run opens real Tk windows and takes"; \
		echo "      over the display for ~30s. 'make pytest-container' is headless."; \
		$(TK_ENV) TK_SILENCE_DEPRECATION=1 uv run --active pytest; \
	elif ! command -v xvfb-run >/dev/null 2>&1; then \
		echo "ERROR: xvfb-run is required to run tests."; \
		echo "Install xvfb: sudo apt-get install xvfb"; \
		exit 1; \
	else \
		xvfb-run -a -s "-screen 0 1280x1024x24" uv run --active pytest; \
	fi

profile-cbz:  ## Profile CBZ launch performance (Usage: make profile-cbz FILE=path/to/comic.cbz)
	@if [ -z "$(FILE)" ]; then echo "Usage: make profile-cbz FILE=path/to/comic.cbz"; exit 1; fi
	@echo "Profiling CBZ launch..."
	@time uv run --active python cdisplayagain.py "$(FILE)"

profile-cbr:  ## Profile CBR launch performance (Usage: make profile-cbr FILE=path/to/comic.cbr)
	@if [ -z "$(FILE)" ]; then echo "Usage: make profile-cbr FILE=path/to/comic.cbr"; exit 1; fi
	@echo "Profiling CBR launch..."
	@time uv run --active python cdisplayagain.py "$(FILE)"

sync:  ## Install dependencies
	uv sync --locked

venv:  ## Create virtual environment
	uv venv

run:  ## Run the app (Usage: make run FILE=path/to/comic.cbz)
	@if [ -z "$(FILE)" ]; then echo "Usage: make run FILE=path/to/comic.cbz"; exit 1; fi
	$(TK_ENV) uv run --active python cdisplayagain.py "$(FILE)"

smoke:  ## Run manual smoke test checklist
	@if [ -z "$(FILE)" ]; then echo "Usage: make smoke FILE=path/to/comic.cbz"; exit 1; fi
	@echo "Manual smoke test checklist:"
	@echo "- Open both CBZ and CBR archives (CBR requires unar)"
	@echo "- Page through images to confirm ordering"
	@echo "- Toggle fit-to-screen, fit-to-width, and zoom modes"
	@echo "- Confirm temp directories are cleaned on exit"
	uv run --active python cdisplayagain.py "$(FILE)"

clean-build:  ## Clean build artifacts
	rm -rf build dist __pycache__ .pytest_cache

deploy: clean-build build-onedir install  ## Build + install for this machine (one command)

build: build-onedir  ## Build the PyInstaller onedir bundle

build-onedir:  ## Build onedir bundle (adds cdisplayagain.app on macOS)
	uv run --active python scripts/generate_build_info.py
	$(TK_ENV) uv run --active pyinstaller --clean --noconfirm cdisplayagain.spec

package-linux: build-onedir  ## Package the tested Linux onedir bundle
	bash scripts/package-linux.sh


install: build-onedir  ## Build, then install (.app on macOS, bundle + desktop entry on Linux)
	@if [ "$(UNAME)" = "Darwin" ]; then \
		$(MAKE) --no-print-directory install-macos; \
	else \
		$(MAKE) --no-print-directory install-bin install-desktop; \
	fi

install-macos:  ## Install cdisplayagain.app to $(MACOS_APPDIR) and register file types
	@bash scripts/install-macos.sh

uninstall-macos:  ## Remove the installed macOS app bundle
	@bash scripts/install-macos.sh --uninstall

package-macos: build-onedir  ## Package the macOS .app into a distributable zip
	@bash scripts/package-macos.sh

install-bin:  ## Install binary to system
	@if [ -f dist/cdisplayagain ]; then \
		echo "Installing onefile binary to $(BINDIR)/cdisplayagain"; \
		install -d $(BINDIR); \
		install -m 0755 dist/cdisplayagain $(BINDIR)/cdisplayagain; \
		install -m 0755 scripts/cdisplayagain-launcher.sh $(BINDIR)/cdisplayagain-launcher; \
	elif [ -f dist/cdisplayagain/cdisplayagain ]; then \
		echo "Installing onedir bundle to $(LIBDIR)/cdisplayagain and wrapper to $(BINDIR)/cdisplayagain"; \
		rm -rf $(LIBDIR)/cdisplayagain; \
		install -d $(LIBDIR)/cdisplayagain; \
		cp -a dist/cdisplayagain/* $(LIBDIR)/cdisplayagain/; \
		install -d $(BINDIR); \
		rm -rf $(BINDIR)/cdisplayagain; \
		printf '%s\n' '#!/usr/bin/env sh' 'exec $(LIBDIR)/cdisplayagain/cdisplayagain "$$@"' > $(BINDIR)/cdisplayagain; \
		chmod 0755 $(BINDIR)/cdisplayagain; \
		install -m 0755 scripts/cdisplayagain-launcher.sh $(BINDIR)/cdisplayagain-launcher; \
	else \
		echo "No dist output found. Run 'make build' or 'make build-onedir' first."; \
		exit 1; \
	fi

install-desktop:  ## Install desktop entry (Linux) or app symlink (macOS)
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "macOS: file associations handled by 'open' command and Launch Services."; \
		echo "Double-click a .cbz/.cbr once and choose cdisplayagain, then 'Always Open With'."; \
	else \
		mkdir -p $(APPDIR); \
		printf '%s\n' \
			'[Desktop Entry]' \
			'Type=Application' \
			'Name=cdisplayagain' \
			"Exec=$(BINDIR)/cdisplayagain-launcher %f" \
			'Terminal=false' \
			'Categories=Graphics;Viewer;' \
			'MimeType=application/x-cbz;application/x-cbr;application/vnd.comicbook+zip;application/vnd.comicbook-rar;application/x-ext-cbz;application/x-ext-cbr;' \
			> $(APPDIR)/cdisplayagain.desktop; \
		update-desktop-database $(APPDIR) || true; \
		for mime in application/x-cbz application/x-cbr application/vnd.comicbook+zip application/vnd.comicbook-rar application/x-ext-cbz application/x-ext-cbr; do \
			xdg-mime default cdisplayagain.desktop "$$mime" 2>/dev/null || true; \
		done; \
		echo "MIME associations:"; \
		$(MAKE) --no-print-directory mime-query; \
	fi

mime-query:  ## Query current MIME associations (Linux)
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "macOS: use 'open -a cdisplayagain file.cbz' to test."; \
	else \
		echo "CBZ:" $$(xdg-mime query default application/x-cbz); \
		echo "CBR:" $$(xdg-mime query default application/x-cbr); \
	fi

redo: build-onedir install-bin  ## Rebuild and run (Usage: make redo FILE=...)
	@if [ -n "$(FILE)" ]; then \
		$(BINDIR)/cdisplayagain "$(FILE)"; \
	else \
		echo "Usage: make redo FILE=path/to/comic.cbz"; \
	fi

ci-test-local:  ## Run CI-like tests locally (requires xvfb and libvips)
	@echo "Running CI-like test locally..."
	@if ! command -v xvfb-run >/dev/null 2>&1; then \
		echo "WARNING: xvfb-run not found. Running without virtual display..."; \
		uv run --active pytest tests/ -q --tb=short 2>&1 | tee ci-test-output.log; \
	else \
		xvfb-run -a uv run --active pytest tests/ -q --tb=short 2>&1 | tee ci-test-output.log; \
	fi
	@if [ -f ci-test-output.log ]; then \
		echo ""; \
		echo "=== CI Test Output Summary ==="; \
		grep -E "passed|failed|ERROR|coverage" ci-test-output.log | tail -10; \
	fi

pytest-container:  ## Run the suite headless in Docker without touching the host .venv
	@if ! docker info >/dev/null 2>&1; then \
		echo "ERROR: Docker is not available or not running."; \
		echo "Start Docker, or run natively with 'make pytest GUI_TESTS=1'."; \
		exit 1; \
	fi
	@if ! docker image inspect cdisplayagain-ci:13 >/dev/null 2>&1; then \
		$(MAKE) --no-print-directory ci-build-image; \
	fi
	@docker run --rm \
		-v "$(CURDIR):/app" \
		-v cdisplayagain-container-venv:/app/.venv \
		-w /app \
		-e PATH="/root/.local/bin:$$PATH" \
		cdisplayagain-ci:13 \
		bash -c 'uv sync --locked && xvfb-run -a --server-args="-screen 0 1280x1024x24" uv run pytest tests/ -q --tb=short'

ci-build-image:  ## Build/rebuild cached debian image
	@echo "Building cached debian image..."
	@docker compose build ci

ci-test-debian:  ## Run tests in cached debian container (like GitHub CI)
	@echo "Running tests in cached debian container..."
	@if ! docker image inspect cdisplayagain-ci:13 >/dev/null 2>&1; then \
		echo "Cached image not found, building..."; \
		$(MAKE) ci-build-image; \
	fi
	@docker run --rm \
		-v "$(CURDIR):/app" \
		-v "$(CURDIR)/.venv:/app/.venv" \
		-w /app \
		-e PATH="/root/.local/bin:$$PATH" \
		cdisplayagain-ci:13 \
		bash -c 'uv sync --locked && timeout 300 xvfb-run -a --server-args="-screen 0 1280x1024x24" .venv/bin/pytest tests/ -q --tb=short' \
		2>&1 | tee ci-test-debian-output.log
	@if [ -f ci-test-debian-output.log ]; then \
		echo "=== CI Test Output Summary ==="; \
		grep -E "passed|failed|ERROR|coverage" ci-test-debian-output.log | tail -10; \
	fi

ci-check:  ## Check if CI prerequisites are installed
	@echo "Checking CI prerequisites..."
	@echo "libvips: $$(dpkg -l | grep -q libvips && echo 'INSTALLED' || echo 'NOT FOUND')"
	@echo "xvfb: $$(command -v xvfb-run && echo 'INSTALLED' || echo 'NOT FOUND')"
	@echo "python3-tk: $$(dpkg -l | grep -q python3-tk && echo 'INSTALLED' || echo 'NOT FOUND')"
	@echo "docker: $$(command -v docker && echo 'INSTALLED' || echo 'NOT FOUND')"
