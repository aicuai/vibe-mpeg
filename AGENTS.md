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

## Editor UI

```
python3 server.py          # http://localhost:3333
```

Browser-based editor with Remotion-inspired layout:
- Left sidebar: Media browser (upload, rename, delete)
- Center: Preview player
- Bottom: Timeline (project steps)
- Right sidebar: Properties / Skills

## Skills

Skills are defined in `skills/*.json`. Each wraps an ffmpeg operation.

| Skill | Command |
|---|---|
| `concat` | `python3 render.py concat --files '[...]'` |
| `mix-audio` | `python3 render.py mix-audio --video X --audio Y` |
| `subtitles` | `python3 render.py subtitles --video X --sub Y` (SRT/ASS/VTT) |
| `transition` | `python3 render.py transition --video1 X --video2 Y --effect fade` |
| `probe` | `python3 render.py probe --file X` |
| `demo` | `python3 render.py demo` |
| `slideshow` | `python3 render.py slideshow --slides '[...]'` |
| `text-overlay` | `python3 render.py text-overlay --text "..."` |
| `render` | `python3 render.py render` (list all skills) |
| `project` | `python3 render.py project --name X` (run project pipeline) |

## Projects

Project definitions live in `projects/*.json`. Each project is a pipeline of skill steps.

### Output Naming

`{ProjectName}-{MMDD}-{HHMM}.mp4` (e.g., `PPSG-Elena-0312-2041.mp4`)

### Project JSON Schema

```json
{
  "name": "project-name",
  "description": "What this project produces",
  "media_dir": "media",
  "output_dir": "out",
  "format": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "codec": "libx264",
    "crf": 23,
    "audio_codec": "aac",
    "audio_bitrate": "192k",
    "pixel_format": "yuv420p"
  },
  "steps": [
    {
      "skill": "skill-name",
      "params": {
        "video": "media/input.mp4",
        "in": 0.0,
        "out": 30.0,
        "blend": "normal"
      }
    }
  ]
}
```

### Step Parameters (planned)

Each step can include ffmpeg-level parameters:

| Parameter | Type | Description |
|---|---|---|
| `in` | float | In-point (seconds) — start time for this clip |
| `out` | float | Out-point (seconds) — end time for this clip |
| `duration` | float | Duration override (alternative to out) |
| `blend` | string | Blending mode: normal, overlay, multiply, screen, add |
| `opacity` | float | Layer opacity (0.0–1.0) |
| `volume` | float | Audio volume (0.0–1.0) |
| `replace` | bool | Replace audio instead of mixing |
| `fade_in` | float | Fade-in duration (seconds) |
| `fade_out` | float | Fade-out duration (seconds) |
| `crop` | object | `{x, y, w, h}` — crop region |
| `scale` | object | `{w, h}` — resize (e.g., 1080x1920 for vertical) |
| `rotate` | float | Rotation in degrees |
| `position` | object | `{x, y}` — overlay position |
| `speed` | float | Playback speed (0.5 = half, 2.0 = double) |
| `filter` | string | Raw ffmpeg filter expression |
| `${prev.output}` | — | Reference previous step's output file |

### Format Presets (planned)

| Preset | Resolution | Use Case |
|---|---|---|
| `landscape` | 1920x1080 | Standard YouTube/TV |
| `vertical` | 1080x1920 | TikTok/Shorts/Reels |
| `square` | 1080x1080 | Instagram |
| `4k` | 3840x2160 | High-res |

## File Management

The editor UI can manage files in these directories:

| Directory | Operations | Notes |
|---|---|---|
| `media/` | Upload, rename, delete | Source files (video, audio, subtitles, images) |
| `out/` | Rename, delete | Rendered output files |
| `projects/` | Rename, delete | Project pipeline definitions |

Each managed directory contains a `readme.txt` warning that files may be modified by the editor.

## Config

`.vibe-mpeg.json` stores user preferences (media directory, etc.) set during tutorial.

## Key Files

- `server.py` — Editor web UI server (localhost:3333)
- `tutorial.py` — Interactive 8-step tutorial
- `render.py` — Skill executor (CLI + stdin JSON)
- `qwen3-bridge.py` — Ollama/Qwen3 chat interface with tool calling
- `engine/` — Playwright-based compositor (for template skills only)
- `templates/` — HTML/CSS/JS video templates
- `skills/` — JSON skill definitions
- `projects/` — Project pipeline definitions
- `media/` — Input media files
- `out/` — Rendered output files
- `setup.sh` — Dependency installer

## Conventions

- Mac-only. Reference installed system tools (ffmpeg, fonts) externally.
- ffmpeg is called as an external subprocess only — never linked or bundled.
- No proprietary dependencies.
- vibe-local is detected automatically if installed nearby, not bundled.
- The `demo` project always produces the latest README video explaining vibe-mpeg.
