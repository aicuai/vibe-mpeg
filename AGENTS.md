# vibe-mpeg Agent Instructions

## Overview

vibe-mpeg is an open, offline-first video editing environment driven by local LLMs.
All video operations are ffmpeg commands wrapped as JSON skill definitions.

## First Run

On the user's first interaction, run the tutorial automatically:

```
python3 tutorial.py
```

After the first run, the tutorial can be invoked with `/tutorial`.

## Skills

Skills are defined in `skills/*.json`. Each wraps an ffmpeg operation.

| Skill | Command |
|---|---|
| `concat` | `python3 render.py concat --files '[...]'` |
| `mix-audio` | `python3 render.py mix-audio --video X --audio Y` |
| `subtitles` | `python3 render.py subtitles --video X --srt Y` |
| `transition` | `python3 render.py transition --video1 X --video2 Y --effect fade` |
| `demo` | `python3 render.py demo` |
| `slideshow` | `python3 render.py slideshow --slides '[...]'` |
| `text-overlay` | `python3 render.py text-overlay --text "..."` |

## Output Convention

All rendered files go to `out/` with timestamp naming: `prefix_YYYY-MM-DD-HHmm.mp4`

## Config

`.vibe-mpeg.json` stores user preferences (media directory, etc.) set during tutorial.

## Key Files

- `tutorial.py` — Interactive 8-step tutorial
- `render.py` — Skill executor (CLI + stdin JSON)
- `qwen3-bridge.py` — Ollama/Qwen3 chat interface with tool calling
- `engine/` — Playwright-based compositor (for template skills only)
- `templates/` — HTML/CSS/JS video templates
- `skills/` — JSON skill definitions
- `setup.sh` — Dependency installer

## Conventions

- Mac-only. Reference installed system tools (ffmpeg, fonts) externally.
- ffmpeg is called as an external subprocess only — never linked or bundled.
- No proprietary dependencies.
- vibe-local is detected automatically if installed nearby, not bundled.
