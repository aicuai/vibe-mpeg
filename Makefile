# vibe-mpeg - Open AI-driven video editing for macOS
# Requires: Python 3.12+, ffmpeg (brew install ffmpeg), Playwright

.PHONY: setup dev render-demo chat clean help check

# === Prerequisites Check ===
check:
	@echo "Checking dependencies..."
	@which python3 > /dev/null || (echo "ERROR: python3 not found" && exit 1)
	@which ffmpeg > /dev/null || (echo "ERROR: ffmpeg not found. Run: brew install ffmpeg" && exit 1)
	@python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null || \
		(echo "ERROR: playwright not found. Run: pip install playwright && playwright install chromium" && exit 1)
	@echo "All dependencies OK."

# === Setup ===
setup:
	pip install playwright
	playwright install chromium
	@echo "Setup complete."

# === Render ===
render-demo:
	python3 render.py demo

render-slideshow:
	python3 render.py slideshow --slides '[{"text":"Slide 1"},{"text":"Slide 2"},{"text":"Slide 3"}]'

render:
	@test -n "$(SKILL)" || (echo "Usage: make render SKILL=demo" && exit 1)
	python3 render.py $(SKILL) $(ARGS)

# === Qwen3 Chat Interface ===
chat:
	python3 qwen3-bridge.py

# === Skills ===
list-skills:
	python3 render.py --list

# === Clean ===
clean:
	rm -rf out/*.mp4
	@echo "Cleaned."

# === Help ===
help:
	@echo "vibe-mpeg - Open AI-driven video editing"
	@echo ""
	@echo "  make setup           Install Playwright + Chromium"
	@echo "  make check           Verify dependencies"
	@echo "  make render-demo     Render demo video"
	@echo "  make render SKILL=X  Render skill X"
	@echo "  make chat            Qwen3 interactive editor"
	@echo "  make list-skills     List available skills"
	@echo "  make clean           Delete outputs"
