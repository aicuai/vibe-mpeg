#!/bin/bash
# vibe-mpeg setup - Interactive setup for macOS
# Checks and installs all dependencies, detects vibe-local

set -e

BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}vibe-mpeg setup${RESET}"
echo -e "Open AI-driven video editing for macOS"
echo ""

# --- Python ---
echo -e "${BOLD}[1/5] Python${RESET}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo -e "  ${GREEN}OK${RESET} $PY_VER"
else
    echo -e "  ${RED}NOT FOUND${RESET}"
    echo "  Install Python 3.12+: https://www.python.org/downloads/"
    exit 1
fi

# --- Homebrew ---
echo -e "${BOLD}[2/5] Homebrew + ffmpeg${RESET}"
if command -v brew &>/dev/null; then
    echo -e "  ${GREEN}OK${RESET} Homebrew found"
else
    echo -e "  ${YELLOW}Homebrew not found.${RESET}"
    read -p "  Install Homebrew? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]?$ ]]; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        echo "  Skipping Homebrew. You'll need to install ffmpeg manually."
    fi
fi

if command -v ffmpeg &>/dev/null; then
    FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1)
    echo -e "  ${GREEN}OK${RESET} $FFMPEG_VER"
else
    echo -e "  ${YELLOW}ffmpeg not found.${RESET}"
    read -p "  Install ffmpeg via Homebrew? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]?$ ]]; then
        brew install ffmpeg
    else
        echo -e "  ${RED}ffmpeg is required. Install it manually.${RESET}"
        exit 1
    fi
fi

# --- Playwright ---
echo -e "${BOLD}[3/5] Playwright${RESET}"
if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    echo -e "  ${GREEN}OK${RESET} Playwright Python package found"
else
    echo -e "  ${YELLOW}Playwright not found.${RESET}"
    read -p "  Install Playwright? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]?$ ]]; then
        pip3 install playwright
    else
        echo -e "  ${RED}Playwright is required.${RESET}"
        exit 1
    fi
fi

# Check Chromium browser
if python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    b.close()
" 2>/dev/null; then
    echo -e "  ${GREEN}OK${RESET} Chromium browser available"
else
    echo -e "  ${YELLOW}Chromium not installed for Playwright.${RESET}"
    read -p "  Install Chromium? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]?$ ]]; then
        playwright install chromium
    else
        echo -e "  ${RED}Chromium is required for rendering.${RESET}"
        exit 1
    fi
fi

# --- Ollama (optional) ---
echo -e "${BOLD}[4/5] Ollama + Qwen3 (optional, for AI chat)${RESET}"
if command -v ollama &>/dev/null; then
    echo -e "  ${GREEN}OK${RESET} Ollama found"
    # Check if qwen3 model is available
    if ollama list 2>/dev/null | grep -q "qwen3"; then
        echo -e "  ${GREEN}OK${RESET} Qwen3 model available"
    else
        echo -e "  ${YELLOW}Qwen3 model not found.${RESET}"
        read -p "  Pull qwen3:8b? (requires ~5GB) [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ollama pull qwen3:8b
        else
            echo "  Skipped. Run 'ollama pull qwen3:8b' later for AI chat."
        fi
    fi
else
    echo -e "  ${YELLOW}Ollama not found.${RESET}"
    echo "  AI chat features require Ollama: https://ollama.com"
    read -p "  Install Ollama via Homebrew? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install ollama
        echo "  Run 'ollama serve' then 'ollama pull qwen3:8b' to enable AI chat."
    else
        echo "  Skipped. Video rendering works without Ollama."
    fi
fi

# --- vibe-local detection ---
echo -e "${BOLD}[5/5] vibe-local (optional)${RESET}"
VIBE_LOCAL=""
# Check common locations
for dir in \
    "$(dirname "$(cd "$(dirname "$0")" && pwd)")/vibe-local" \
    "$HOME/git.local/vibe-local" \
    "$HOME/vibe-local" \
    "/usr/local/share/vibe-local"; do
    if [ -f "$dir/vibe-coder.py" ]; then
        VIBE_LOCAL="$dir"
        break
    fi
done

if [ -n "$VIBE_LOCAL" ]; then
    echo -e "  ${GREEN}OK${RESET} Found at $VIBE_LOCAL"
    # Save path for runtime use
    echo "VIBE_LOCAL_PATH=$VIBE_LOCAL" > .env.local
    echo "  Saved path to .env.local"
else
    echo -e "  ${YELLOW}Not found.${RESET}"
    echo "  vibe-local provides Ollama proxy and coding assistant features."
    echo "  Install from: https://github.com/aicuai/vibe-local"
fi

# --- Summary ---
echo ""
echo -e "${BOLD}Setup complete!${RESET}"
echo ""
echo "Quick start:"
echo "  python3 render.py demo              # Render demo video"
echo "  python3 render.py --list            # List available skills"
if command -v ollama &>/dev/null; then
    echo "  python3 qwen3-bridge.py             # AI chat video editor"
fi
echo ""
echo "  make help                           # All commands"
echo ""
