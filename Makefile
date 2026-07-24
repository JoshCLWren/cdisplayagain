.PHONY: help lint pytest sync venv run smoke clean-build build build-onedir macos-app macos-install linux-install install install-bin install-desktop mime-query redo ci-test-debian ci-test-local ci-build-image githook install-githook

# Configuration
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib

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

pytest:  ## Run tests (requires xvfb to prevent GUI windows)
	@if ! command -v xvfb-run >/dev/null 2>&1; then \
		echo "ERROR: xvfb-run is required to run tests."; \
		echo "Install xvfb: sudo apt-get install xvfb"; \
		exit 1; \
	fi
	xvfb-run -a -s "-screen 0 1280x1024x24" uv run --active pytest

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
	uv run --active python cdisplayagain.py "$(FILE)"

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

build: clean-build  ## Build single-file executable (slower startup)
	uv run --active pyinstaller --onefile --name cdisplayagain cdisplayagain.py

build-onedir:  ## Build onedir bundle (faster startup than onefile)
	uv run --active pyinstaller \
		--onedir \
		--icon=cdisplayagain.png \
		--name cdisplayagain \
		cdisplayagain.py

macos-app: clean-build  ## Build a macOS app bundle associated with CBZ/CBR files
	@if [ "$$(uname -s)" != "Darwin" ]; then echo "macos-app requires macOS"; exit 1; fi
	mkdir -p build/cdisplayagain.iconset
	sips -z 16 16 cdisplayagain.png --out build/cdisplayagain.iconset/icon_16x16.png >/dev/null
	sips -z 32 32 cdisplayagain.png --out build/cdisplayagain.iconset/icon_16x16@2x.png >/dev/null
	sips -z 32 32 cdisplayagain.png --out build/cdisplayagain.iconset/icon_32x32.png >/dev/null
	sips -z 64 64 cdisplayagain.png --out build/cdisplayagain.iconset/icon_32x32@2x.png >/dev/null
	sips -z 128 128 cdisplayagain.png --out build/cdisplayagain.iconset/icon_128x128.png >/dev/null
	sips -z 256 256 cdisplayagain.png --out build/cdisplayagain.iconset/icon_128x128@2x.png >/dev/null
	sips -z 256 256 cdisplayagain.png --out build/cdisplayagain.iconset/icon_256x256.png >/dev/null
	sips -z 512 512 cdisplayagain.png --out build/cdisplayagain.iconset/icon_256x256@2x.png >/dev/null
	sips -z 512 512 cdisplayagain.png --out build/cdisplayagain.iconset/icon_512x512.png >/dev/null
	sips -z 1024 1024 cdisplayagain.png --out build/cdisplayagain.iconset/icon_512x512@2x.png >/dev/null
	iconutil -c icns build/cdisplayagain.iconset -o build/cdisplayagain.icns
	uv run --active pyinstaller --noconfirm cdisplayagain-macos.spec

macos-install: macos-app  ## Install the macOS app and register it with Launch Services
	mkdir -p "$(HOME)/Applications"
	ditto dist/cdisplayagain.app "$(HOME)/Applications/cdisplayagain.app"
	/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
		-f "$(HOME)/Applications/cdisplayagain.app"
	@if command -v duti >/dev/null 2>&1; then \
		duti -s com.cdisplayagain.viewer .cbz all; \
		duti -s com.cdisplayagain.viewer .cbr all; \
	else \
		echo "Install duti to make cdisplayagain the default CBZ/CBR opener: brew install duti"; \
	fi
	@echo "Installed $(HOME)/Applications/cdisplayagain.app"

linux-install: build-onedir install  ## Build and install the Linux CBZ/CBR file association


install: install-bin install-desktop  ## Install everything

install-bin:  ## Install binary to system
	@if [ -f dist/cdisplayagain ]; then \
		echo "Installing onefile binary to $(BINDIR)/cdisplayagain"; \
		install -d $(BINDIR); \
		install -m 0755 dist/cdisplayagain $(BINDIR)/cdisplayagain; \
	elif [ -f dist/cdisplayagain/cdisplayagain ]; then \
		echo "Installing onedir bundle to $(LIBDIR)/cdisplayagain and wrapper to $(BINDIR)/cdisplayagain"; \
		rm -rf $(LIBDIR)/cdisplayagain; \
		install -d $(LIBDIR)/cdisplayagain; \
		cp -a dist/cdisplayagain/* $(LIBDIR)/cdisplayagain/; \
		install -d $(BINDIR); \
		rm -rf $(BINDIR)/cdisplayagain; \
		printf '%s\n' '#!/usr/bin/env sh' 'exec $(LIBDIR)/cdisplayagain/cdisplayagain "$$@"' > $(BINDIR)/cdisplayagain; \
		chmod 0755 $(BINDIR)/cdisplayagain; \
	else \
		echo "No dist output found. Run 'make build' or 'make build-onedir' first."; \
		exit 1; \
	fi

install-desktop:  ## Install desktop entry
	mkdir -p $(HOME)/.local/share/applications
	mkdir -p $(HOME)/.local/share/mime/packages
	install -m 0644 packaging/linux/cdisplayagain.xml $(HOME)/.local/share/mime/packages/cdisplayagain.xml
	update-mime-database $(HOME)/.local/share/mime
	mkdir -p $(HOME)/.local/share/icons/hicolor/1024x1024/apps
	install -m 0644 cdisplayagain.png $(HOME)/.local/share/icons/hicolor/1024x1024/apps/cdisplayagain.png
	printf '%s\n' \
		'[Desktop Entry]' \
		'Type=Application' \
		'Name=cdisplayagain' \
		"Exec=$(BINDIR)/cdisplayagain %f" \
		'Icon=cdisplayagain' \
		'Terminal=false' \
		'Categories=Graphics;Viewer;' \
		'MimeType=application/x-cbz;application/x-cbr;' \
		> $(HOME)/.local/share/applications/cdisplayagain.desktop
	update-desktop-database $(HOME)/.local/share/applications || true
	xdg-mime default cdisplayagain.desktop application/x-cbz
	xdg-mime default cdisplayagain.desktop application/x-cbr

mime-query:  ## Query current MIME associations
	@echo "CBZ:" $$(xdg-mime query default application/x-cbz)
	@echo "CBR:" $$(xdg-mime query default application/x-cbr)

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
