#!/usr/bin/env python3
"""
vibe-mpeg render.py - Render video compositions from CLI or LLM tool calls.

Uses Playwright (MIT) for HTML→frame rendering, ffmpeg for encoding.
Both are external dependencies — not bundled, not linked.

Usage:
  python render.py demo
  python render.py slideshow --slides '[{"text":"Hello"},{"text":"World"}]'
  python render.py text-overlay --text "Title Card"
  echo '{"skill":"slideshow","params":{"slides":[{"text":"Hello"}]}}' | python render.py --stdin
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"
TEMPLATES_DIR = ROOT / "templates"


def load_skill(name: str) -> dict:
    """Load a skill definition JSON."""
    skill_path = SKILLS_DIR / f"{name}.json"
    if not skill_path.exists():
        available = [p.stem for p in SKILLS_DIR.glob("*.json")]
        raise ValueError(f"Unknown skill: {name}. Available: {available}")
    with open(skill_path) as f:
        return json.load(f)


def resolve_template(skill: dict, params: dict) -> str:
    """Resolve HTML template path from skill definition or params."""
    template_name = params.get("template", skill.get("template", "demo"))
    # Allow full path or just name
    template_path = Path(template_name)
    if not template_path.exists():
        template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    return str(template_path)


def execute_skill(name: str, params: dict) -> dict:
    """Execute a skill using the vibe-mpeg engine."""
    from engine.composition import Composition

    skill = load_skill(name)
    template = resolve_template(skill, params)

    # Extract render-level params
    fps = params.get("fps", 30)
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    output = params.get("output", f"out/{name}.mp4")
    codec = params.get("codec", "libx264")
    audio = params.get("audio")

    # Calculate duration
    if "durationSeconds" in params:
        duration = params["durationSeconds"]
    elif "slides" in params:
        slides = params["slides"]
        sps = params.get("secondsPerSlide", 10)
        duration = len(slides) * sps
    else:
        duration = skill.get("defaultDuration", 10)

    # Build props (exclude render-level keys)
    render_keys = {"fps", "width", "height", "output", "codec", "audio", "template", "durationSeconds"}
    props = {k: v for k, v in params.items() if k not in render_keys}

    comp = Composition(
        id=name,
        template=template,
        duration_seconds=duration,
        fps=fps,
        width=width,
        height=height,
        props=props,
    )

    try:
        out_path = comp.render(output=output, codec=codec, audio=audio)
        return {
            "status": "success",
            "output": str(out_path),
            "message": f"Video rendered: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="vibe-mpeg renderer")
    parser.add_argument("skill", nargs="?", help="Skill name (demo, slideshow, text-overlay)")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    parser.add_argument("--list", action="store_true", help="List available skills")

    args, extra = parser.parse_known_args()

    if args.list:
        for p in sorted(SKILLS_DIR.glob("*.json")):
            skill = load_skill(p.stem)
            print(f"  {p.stem}: {skill.get('description', '')}")
        return

    if args.stdin:
        data = json.load(sys.stdin)
        skill_name = data.get("skill", data.get("name"))
        params = data.get("params", data.get("parameters", {}))
    elif args.skill:
        skill_name = args.skill
        params = {}
        i = 0
        while i < len(extra):
            if extra[i].startswith("--"):
                key = extra[i][2:]
                if i + 1 < len(extra) and not extra[i + 1].startswith("--"):
                    value = extra[i + 1]
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    params[key] = value
                    i += 2
                else:
                    params[key] = True
                    i += 1
            else:
                i += 1
    else:
        parser.print_help()
        return

    result = execute_skill(skill_name, params)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
