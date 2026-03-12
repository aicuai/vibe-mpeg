#!/usr/bin/env python3
"""
vibe-mpeg tutorial - Interactive first-run tutorial.

Guides the user through:
  1. Environment check
  2. Install missing tools
  3. Video concatenation
  4. Specify media source directory
  5. Render with timestamped output
  6. Audio mixing
  7. Subtitle creation
  8. Transition effects

Modes:
  python3 tutorial.py            # Interactive (terminal)
  python3 tutorial.py --auto     # Non-interactive, use defaults
  python3 tutorial.py --step 1   # Run single step
  python3 tutorial.py --step 1-3 # Run step range
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "out"
MEDIA_DIR = ROOT / "media"
CONFIG_FILE = ROOT / ".vibe-mpeg.json"

# --- Colors ---
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"

# --- Auto mode flag ---
AUTO_MODE = False


def ask(prompt: str, default: str = "") -> str:
    if AUTO_MODE:
        print(f"{prompt} [{default}]: {DIM}(auto){RESET}")
        return default
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return val or default


def ask_yn(prompt: str, default: bool = True) -> bool:
    if AUTO_MODE:
        ans = "yes" if default else "no"
        print(f"{prompt} {DIM}(auto: {ans}){RESET}")
        return default
    hint = "Y/n" if default else "y/N"
    try:
        val = input(f"{prompt} [{hint}] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not val:
        return default
    return val.startswith("y")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"{DIM}  $ {' '.join(cmd)}{RESET}")
    return subprocess.run(cmd, **kwargs)


def header(step: int, total: int, title: str):
    print()
    print(f"{BOLD}{CYAN}[{step}/{total}] {title}{RESET}")
    print()


def save_config(config: dict):
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def timestamp_filename(prefix: str = "output", ext: str = "mp4") -> str:
    return datetime.now().strftime(f"{prefix}_%Y-%m-%d-%H%M.{ext}")


# ============================================================
# Step 1: Environment Check
# ============================================================
def step_check_env() -> dict:
    header(1, 8, "Environment Check")

    tools = {}

    # Python
    py_ver = sys.version.split()[0]
    print(f"  {GREEN}OK{RESET} Python {py_ver}")

    # ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        result = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
        ver = result.stdout.split("\n")[0] if result.stdout else "unknown"
        print(f"  {GREEN}OK{RESET} {ver}")
        tools["ffmpeg"] = ffmpeg
    else:
        print(f"  {RED}MISSING{RESET} ffmpeg")
        tools["ffmpeg"] = None

    # ffprobe
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        print(f"  {GREEN}OK{RESET} ffprobe found")
        tools["ffprobe"] = ffprobe
    else:
        print(f"  {RED}MISSING{RESET} ffprobe")
        tools["ffprobe"] = None

    # Playwright (optional for title card generation)
    try:
        import playwright
        print(f"  {GREEN}OK{RESET} Playwright (optional, for title cards)")
        tools["playwright"] = True
    except ImportError:
        print(f"  {YELLOW}SKIP{RESET} Playwright (optional, for title cards)")
        tools["playwright"] = False

    # Ollama (optional)
    ollama = shutil.which("ollama")
    if ollama:
        print(f"  {GREEN}OK{RESET} Ollama (optional, for AI chat)")
        tools["ollama"] = ollama
    else:
        print(f"  {YELLOW}SKIP{RESET} Ollama (optional, for AI chat)")
        tools["ollama"] = None

    # vibe-local (optional)
    vibe_local = None
    for d in [ROOT.parent / "vibe-local", Path.home() / "git.local/vibe-local", Path.home() / "vibe-local"]:
        if (d / "vibe-coder.py").exists():
            vibe_local = str(d)
            break
    if vibe_local:
        print(f"  {GREEN}OK{RESET} vibe-local at {vibe_local}")
    else:
        print(f"  {YELLOW}SKIP{RESET} vibe-local (optional)")
    tools["vibe_local"] = vibe_local

    return tools


# ============================================================
# Step 2: Install Missing Tools
# ============================================================
def step_install(tools: dict):
    header(2, 8, "Install Missing Tools")

    missing = []
    if not tools.get("ffmpeg"):
        missing.append("ffmpeg")

    if not missing:
        print(f"  {GREEN}All required tools are installed.{RESET}")
        return

    print(f"  Missing: {', '.join(missing)}")

    if "ffmpeg" in missing:
        if ask_yn("  Install ffmpeg via Homebrew?"):
            run(["brew", "install", "ffmpeg"])
            tools["ffmpeg"] = shutil.which("ffmpeg")
            tools["ffprobe"] = shutil.which("ffprobe")
        else:
            print(f"  {RED}ffmpeg is required. Install manually and retry.{RESET}")
            if not AUTO_MODE:
                sys.exit(1)


# ============================================================
# Step 3: Video Concatenation
# ============================================================
def step_concat(config: dict):
    header(3, 8, "Video Concatenation")

    print("  Let's try concatenating videos.")
    print("  Place MP4 files in a directory, and we'll join them.")
    print()

    media_path = ask("  Directory with MP4 files", str(MEDIA_DIR))
    media_dir = Path(media_path).expanduser().resolve()

    if not media_dir.exists():
        media_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Created {media_dir}")
        print(f"  {YELLOW}Put some .mp4 files there, then re-run this step.{RESET}")
        config["media_dir"] = str(media_dir)
        return None

    mp4s = sorted(media_dir.glob("*.mp4"))
    if not mp4s:
        print(f"  {YELLOW}No .mp4 files found in {media_dir}{RESET}")
        print(f"  Put some .mp4 files there, then re-run this step.")
        config["media_dir"] = str(media_dir)
        return None

    print(f"  Found {len(mp4s)} files:")
    for f in mp4s:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
            capture_output=True, text=True,
        )
        try:
            info = json.loads(result.stdout)
            dur = float(info["format"]["duration"])
            size_mb = int(info["format"]["size"]) / 1024 / 1024
            print(f"    {f.name}  ({dur:.1f}s, {size_mb:.1f}MB)")
        except (json.JSONDecodeError, KeyError):
            print(f"    {f.name}")

    if len(mp4s) < 2:
        print(f"\n  {YELLOW}Need at least 2 files to concatenate. Skipping.{RESET}")
        config["media_dir"] = str(media_dir)
        return str(mp4s[0]) if mp4s else None

    if not ask_yn(f"\n  Concatenate these {len(mp4s)} files?"):
        config["media_dir"] = str(media_dir)
        return str(mp4s[0])

    # Create concat list file
    concat_list = media_dir / "_concat.txt"
    with open(concat_list, "w") as f:
        for mp4 in mp4s:
            f.write(f"file '{mp4}'\n")

    output = OUT_DIR / timestamp_filename("concat")
    OUT_DIR.mkdir(exist_ok=True)

    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(output),
    ])

    concat_list.unlink()

    if output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"\n  {GREEN}OK{RESET} {output.name} ({size_mb:.1f}MB)")
        config["media_dir"] = str(media_dir)
        return str(output)
    else:
        print(f"\n  {RED}Concatenation failed.{RESET}")
        return None


# ============================================================
# Step 4: Media Source Directory
# ============================================================
def step_media_dir(config: dict):
    header(4, 8, "Media Source Directory")

    current = config.get("media_dir", str(MEDIA_DIR))
    print(f"  Current: {current}")
    print(f"  This is where vibe-mpeg looks for input files (MP4, MP3, images).")
    print()

    new_path = ask("  Media directory", current)
    media_dir = Path(new_path).expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    config["media_dir"] = str(media_dir)
    print(f"  {GREEN}OK{RESET} Media directory: {media_dir}")


# ============================================================
# Step 5: Render with Timestamp
# ============================================================
def step_render(config: dict, input_video: str | None):
    header(5, 8, "Render with Timestamped Output")

    print("  Renders produce files named YYYY-MM-DD-HHmm.mp4")
    print(f"  Output directory: {OUT_DIR}")
    print()

    if not input_video:
        media_dir = Path(config.get("media_dir", str(MEDIA_DIR)))
        mp4s = sorted(media_dir.glob("*.mp4"))
        if mp4s:
            input_video = str(mp4s[0])
            print(f"  Using: {input_video}")
        else:
            print(f"  {YELLOW}No input video available. Skipping.{RESET}")
            return None

    if not ask_yn("  Re-encode to standard format (h264/aac)?"):
        print(f"  Skipped.")
        return input_video

    output = OUT_DIR / timestamp_filename()
    OUT_DIR.mkdir(exist_ok=True)

    run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-c:v", "libx264", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output),
    ])

    if output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"\n  {GREEN}OK{RESET} {output.name} ({size_mb:.1f}MB)")
        return str(output)
    else:
        print(f"\n  {RED}Render failed.{RESET}")
        return input_video


# ============================================================
# Step 6: Audio Mixing
# ============================================================
def step_audio_mix(config: dict, input_video: str | None):
    header(6, 8, "Audio Mixing")

    print("  Add an MP3 track (BGM, narration) to a video.")
    print()

    if not input_video:
        print(f"  {YELLOW}No input video. Skipping.{RESET}")
        return input_video

    media_dir = Path(config.get("media_dir", str(MEDIA_DIR)))
    mp3s = sorted(media_dir.glob("*.mp3"))

    if not mp3s:
        print(f"  No .mp3 files in {media_dir}")
        print(f"  Put an MP3 file there to try audio mixing.")
        return input_video

    print(f"  Available audio files:")
    for f in mp3s:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
            capture_output=True, text=True,
        )
        try:
            info = json.loads(result.stdout)
            dur = float(info["format"]["duration"])
            print(f"    {f.name}  ({dur:.1f}s)")
        except (json.JSONDecodeError, KeyError):
            print(f"    {f.name}")

    if not ask_yn("\n  Mix audio into video?"):
        return input_video

    audio_file = ask("  Audio file", str(mp3s[0]))
    volume = ask("  BGM volume (0.0-1.0)", "0.3")

    output = OUT_DIR / timestamp_filename("mixed")

    # Amerge: keep original audio + add BGM at lower volume
    run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-i", audio_file,
        "-filter_complex",
        f"[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output),
    ])

    if output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"\n  {GREEN}OK{RESET} {output.name} ({size_mb:.1f}MB)")
        return str(output)
    else:
        print(f"\n  {RED}Audio mixing failed.{RESET}")
        return input_video


# ============================================================
# Step 7: Subtitles
# ============================================================
def step_subtitles(config: dict, input_video: str | None):
    header(7, 8, "Subtitles")

    print("  Create and burn subtitles into video.")
    print()

    if not input_video:
        print(f"  {YELLOW}No input video. Skipping.{RESET}")
        return input_video

    media_dir = Path(config.get("media_dir", str(MEDIA_DIR)))
    srt_files = sorted(media_dir.glob("*.srt"))

    if srt_files:
        print(f"  Found subtitle files: {[f.name for f in srt_files]}")
        srt_path = ask("  SRT file to use", str(srt_files[0]))
    else:
        print(f"  No .srt files found. Let's create a sample one.")
        if not ask_yn("  Create sample subtitle file?"):
            return input_video

        srt_path = str(media_dir / "sample.srt")
        Path(srt_path).write_text(
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "vibe-mpeg: Open Video Editing\n"
            "\n"
            "2\n"
            "00:00:05,000 --> 00:00:08,000\n"
            "Powered by ffmpeg + AI\n"
            "\n"
            "3\n"
            "00:00:09,000 --> 00:00:12,000\n"
            "No proprietary dependencies\n\n",
            encoding="utf-8",
        )
        print(f"  {GREEN}Created{RESET} {srt_path}")
        print(f"  Edit this file to customize your subtitles.")

    if not ask_yn("\n  Burn subtitles into video?"):
        return input_video

    font = ask("  Font name", "Helvetica")
    font_size = ask("  Font size", "24")

    output = OUT_DIR / timestamp_filename("subtitled")

    run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", f"subtitles={srt_path}:force_style='FontName={font},FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
        "-c:v", "libx264", "-crf", "23",
        "-c:a", "copy",
        str(output),
    ])

    if output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"\n  {GREEN}OK{RESET} {output.name} ({size_mb:.1f}MB)")
        return str(output)
    else:
        print(f"\n  {RED}Subtitle burn failed.{RESET}")
        return input_video


# ============================================================
# Step 8: Transition Effects
# ============================================================
def step_transitions(config: dict):
    header(8, 8, "Transition Effects")

    print("  Create transitions between video clips using ffmpeg xfade filter.")
    print()

    media_dir = Path(config.get("media_dir", str(MEDIA_DIR)))
    mp4s = sorted(media_dir.glob("*.mp4"))

    if len(mp4s) < 2:
        print(f"  {YELLOW}Need at least 2 MP4 files in {media_dir} for transitions.{RESET}")
        print()
        print("  Available xfade transitions:")
        transitions = [
            "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
            "slideleft", "slideright", "slideup", "slidedown",
            "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
            "radial", "smoothleft", "smoothright", "smoothup", "smoothdown",
            "dissolve",
        ]
        for i, t in enumerate(transitions):
            print(f"    {t}", end="  ")
            if (i + 1) % 5 == 0:
                print()
        print()
        return

    print(f"  Found {len(mp4s)} clips:")
    durations = []
    for f in mp4s:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)],
            capture_output=True, text=True,
        )
        try:
            info = json.loads(result.stdout)
            dur = float(info["format"]["duration"])
            durations.append(dur)
            print(f"    {f.name}  ({dur:.1f}s)")
        except (json.JSONDecodeError, KeyError):
            durations.append(10.0)
            print(f"    {f.name}")

    transitions = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "circlecrop", "dissolve",
        "fadeblack", "fadewhite", "radial", "smoothleft", "smoothright",
    ]
    print(f"\n  Available transitions: {', '.join(transitions)}")

    effect = ask("\n  Transition effect", "fade")
    duration_str = ask("  Transition duration (seconds)", "1")
    xfade_dur = float(duration_str)

    if not ask_yn(f"\n  Apply '{effect}' transition ({xfade_dur}s) between clips?"):
        return

    if len(mp4s) == 2:
        # Simple 2-clip xfade
        offset = durations[0] - xfade_dur
        output = OUT_DIR / timestamp_filename("transition")

        run([
            "ffmpeg", "-y",
            "-i", str(mp4s[0]),
            "-i", str(mp4s[1]),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition={effect}:duration={xfade_dur}:offset={offset}[outv];"
            f"[0:a][1:a]acrossfade=d={xfade_dur}[outa]",
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", "23",
            str(output),
        ])
    else:
        # Chain multiple xfades
        inputs = []
        for f in mp4s:
            inputs.extend(["-i", str(f)])

        # Build xfade chain
        n = len(mp4s)
        filter_parts = []
        offsets = []
        cumulative = 0.0
        for i in range(n - 1):
            cumulative += durations[i] - xfade_dur
            offsets.append(cumulative)

        # Video chain
        prev = "[0:v]"
        for i in range(1, n):
            next_in = f"[{i}:v]"
            out_label = f"[v{i}]" if i < n - 1 else "[outv]"
            offset = offsets[i - 1]
            filter_parts.append(
                f"{prev}{next_in}xfade=transition={effect}:duration={xfade_dur}:offset={offset:.3f}{out_label}"
            )
            prev = out_label if i < n - 1 else ""

        # Audio chain
        prev_a = "[0:a]"
        for i in range(1, n):
            next_a = f"[{i}:a]"
            out_a = f"[a{i}]" if i < n - 1 else "[outa]"
            filter_parts.append(
                f"{prev_a}{next_a}acrossfade=d={xfade_dur}{out_a}"
            )
            prev_a = out_a if i < n - 1 else ""

        filter_complex = ";".join(filter_parts)
        output = OUT_DIR / timestamp_filename("transition")

        run([
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-crf", "23",
            str(output),
        ])

    if output.exists():
        size_mb = output.stat().st_size / 1024 / 1024
        print(f"\n  {GREEN}OK{RESET} {output.name} ({size_mb:.1f}MB)")
    else:
        print(f"\n  {RED}Transition rendering failed.{RESET}")


# ============================================================
# Step Registry
# ============================================================
ALL_STEPS = {
    1: ("Environment Check", lambda c, v: (step_check_env(), v)),
    2: ("Install Missing Tools", lambda c, v: (step_install(step_check_env()), v)),
    3: ("Video Concatenation", lambda c, v: (None, step_concat(c))),
    4: ("Media Source Directory", lambda c, v: (step_media_dir(c), v)),
    5: ("Render", lambda c, v: (None, step_render(c, v))),
    6: ("Audio Mixing", lambda c, v: (None, step_audio_mix(c, v))),
    7: ("Subtitles", lambda c, v: (None, step_subtitles(c, v))),
    8: ("Transition Effects", lambda c, v: (step_transitions(c), v)),
}


def parse_step_range(s: str) -> list[int]:
    """Parse '3', '1-3', '1,3,5' into list of step numbers."""
    steps = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            steps.extend(range(int(a), int(b) + 1))
        else:
            steps.append(int(part))
    return [s for s in steps if 1 <= s <= 8]


# ============================================================
# Main
# ============================================================
def main():
    global AUTO_MODE

    parser = argparse.ArgumentParser(description="vibe-mpeg tutorial")
    parser.add_argument("--auto", action="store_true",
                        help="Non-interactive mode, use all defaults")
    parser.add_argument("--step", type=str,
                        help="Run specific step(s): '1', '1-3', '1,3,5'")
    parser.add_argument("--media", type=str,
                        help="Set media directory")
    args = parser.parse_args()

    AUTO_MODE = args.auto

    print()
    print(f"{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  vibe-mpeg Tutorial{RESET}")
    print(f"{BOLD}  Open AI-driven Video Editing{RESET}")
    if AUTO_MODE:
        print(f"{DIM}  (auto mode){RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")

    config = load_config()
    if args.media:
        config["media_dir"] = str(Path(args.media).expanduser().resolve())

    if args.step:
        # Run specific steps
        steps = parse_step_range(args.step)
        result_video = None
        for s in steps:
            if s in ALL_STEPS:
                _, result_video = ALL_STEPS[s][1](config, result_video)
        save_config(config)
        return

    # Full tutorial
    # Step 1: Check
    tools = step_check_env()

    # Step 2: Install
    step_install(tools)

    if not tools.get("ffmpeg"):
        print(f"\n{RED}ffmpeg is required. Exiting.{RESET}")
        sys.exit(1)

    # Step 3: Concat
    result_video = step_concat(config)

    # Step 4: Media dir
    step_media_dir(config)

    # Step 5: Render
    result_video = step_render(config, result_video)

    # Step 6: Audio
    result_video = step_audio_mix(config, result_video)

    # Step 7: Subtitles
    result_video = step_subtitles(config, result_video)

    # Step 8: Transitions
    step_transitions(config)

    # Save config
    save_config(config)

    # Done
    print()
    print(f"{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  Tutorial Complete!{RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")
    print()
    print(f"  Config saved to: {CONFIG_FILE}")
    print(f"  Media directory: {config.get('media_dir')}")
    print(f"  Output directory: {OUT_DIR}")
    print()
    print(f"  Next steps:")
    print(f"    python3 render.py --list          # Available skills")
    print(f"    python3 qwen3-bridge.py           # AI chat editor")
    print(f"    python3 tutorial.py               # Run again anytime")
    print()


if __name__ == "__main__":
    main()
