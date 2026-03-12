# vibe-mpeg - Open AI-driven video editing for macOS
# Requires: Python 3.12+, ffmpeg (brew install ffmpeg)

.PHONY: tutorial setup check render chat list-skills clean help

# === First Run ===
tutorial:
	python3 tutorial.py

# === Setup ===
setup:
	./setup.sh

check:
	@which python3 > /dev/null || (echo "ERROR: python3 not found" && exit 1)
	@which ffmpeg > /dev/null || (echo "ERROR: ffmpeg not found. Run: brew install ffmpeg" && exit 1)
	@which ffprobe > /dev/null || (echo "ERROR: ffprobe not found" && exit 1)
	@echo "All OK."

# === Render ===
render:
	@test -n "$(SKILL)" || (echo "Usage: make render SKILL=concat ARGS='--files ...' " && exit 1)
	python3 render.py $(SKILL) $(ARGS)

# === Qwen3 Chat ===
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
	@echo "  make tutorial        First-run interactive tutorial"
	@echo "  make setup           Install dependencies"
	@echo "  make check           Verify dependencies"
	@echo "  make render SKILL=X  Render skill X"
	@echo "  make chat            Qwen3 interactive editor"
	@echo "  make list-skills     List available skills"
	@echo "  make clean           Delete outputs"
