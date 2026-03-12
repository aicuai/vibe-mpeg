#!/usr/bin/env python3
"""
vibe-mpeg render.py - Execute video editing skills via ffmpeg.

Usage:
  python render.py concat --files '["a.mp4","b.mp4"]'
  python render.py mix-audio --video input.mp4 --audio bgm.mp3 --volume 0.3
  python render.py subtitles --video input.mp4 --srt captions.srt
  python render.py transition --video1 a.mp4 --video2 b.mp4 --effect fade
  python render.py --list
  echo '{"skill":"concat","params":{"files":["a.mp4","b.mp4"]}}' | python render.py --stdin
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"
OUT_DIR = ROOT / "out"


def load_skill(name: str) -> dict:
    skill_path = SKILLS_DIR / f"{name}.json"
    if not skill_path.exists():
        available = [p.stem for p in SKILLS_DIR.glob("*.json")]
        raise ValueError(f"Unknown skill: {name}. Available: {available}")
    with open(skill_path) as f:
        return json.load(f)


def ts_output(prefix: str = "output", ext: str = "mp4") -> str:
    return str(OUT_DIR / datetime.now().strftime(f"{prefix}_%Y-%m-%d-%H%M.{ext}"))


def ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (json.JSONDecodeError, KeyError):
        return 10.0


def run_ffmpeg(cmd: list[str]) -> dict:
    print(f"[vibe-mpeg] $ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"status": "error", "message": result.stderr[-2000:]}
    return {"status": "success"}


# === Skill Executors ===

def exec_concat(params: dict) -> dict:
    files = params["files"]
    output = params.get("output", ts_output("concat"))
    reencode = params.get("reencode", False)

    # Write concat list
    concat_list = OUT_DIR / "_concat.txt"
    OUT_DIR.mkdir(exist_ok=True)
    with open(concat_list, "w") as f:
        for path in files:
            f.write(f"file '{Path(path).resolve()}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list)]
    if reencode:
        cmd.extend(["-c:v", "libx264", "-crf", "23", "-c:a", "aac"])
    else:
        cmd.extend(["-c", "copy"])
    cmd.append(output)

    result = run_ffmpeg(cmd)
    concat_list.unlink(missing_ok=True)
    result["output"] = output
    return result


def exec_mix_audio(params: dict) -> dict:
    video = params["video"]
    audio = params["audio"]
    volume = params.get("volume", 0.3)
    replace = params.get("replace", False)
    output = params.get("output", ts_output("mixed"))
    OUT_DIR.mkdir(exist_ok=True)

    if replace:
        cmd = [
            "ffmpeg", "-y", "-i", video, "-i", audio,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            output,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", video, "-i", audio,
            "-filter_complex",
            f"[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
            output,
        ]

    result = run_ffmpeg(cmd)
    result["output"] = output
    return result


def exec_subtitles(params: dict) -> dict:
    video = params["video"]
    srt = params["srt"]
    font = params.get("font", "Helvetica")
    font_size = params.get("fontSize", 24)
    output = params.get("output", ts_output("subtitled"))
    OUT_DIR.mkdir(exist_ok=True)

    style = f"FontName={font},FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2"
    cmd = [
        "ffmpeg", "-y", "-i", video,
        "-vf", f"subtitles={srt}:force_style='{style}'",
        "-c:v", "libx264", "-crf", "23", "-c:a", "copy",
        output,
    ]

    result = run_ffmpeg(cmd)
    result["output"] = output
    return result


def exec_transition(params: dict) -> dict:
    v1 = params["video1"]
    v2 = params["video2"]
    effect = params.get("effect", "fade")
    dur = params.get("duration", 1)
    output = params.get("output", ts_output("transition"))
    OUT_DIR.mkdir(exist_ok=True)

    d1 = ffprobe_duration(v1)
    offset = d1 - dur

    cmd = [
        "ffmpeg", "-y", "-i", v1, "-i", v2,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition={effect}:duration={dur}:offset={offset}[outv];"
        f"[0:a][1:a]acrossfade=d={dur}[outa]",
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-crf", "23",
        output,
    ]

    result = run_ffmpeg(cmd)
    result["output"] = output
    return result


# Legacy template-based skills (demo, slideshow, text-overlay)
def exec_template(name: str, params: dict) -> dict:
    from engine.composition import Composition

    skill = load_skill(name)
    template_name = params.get("template", skill.get("template", name))
    template_path = ROOT / "templates" / f"{template_name}.html"
    if not template_path.exists():
        return {"status": "error", "message": f"Template not found: {template_path}"}

    fps = params.get("fps", 30)
    width = params.get("width", 1920)
    height = params.get("height", 1080)
    output = params.get("output", ts_output(name))

    if "durationSeconds" in params:
        duration = params["durationSeconds"]
    elif "slides" in params:
        duration = len(params["slides"]) * params.get("secondsPerSlide", 10)
    else:
        duration = skill.get("defaultDuration", 10)

    render_keys = {"fps", "width", "height", "output", "codec", "audio", "template", "durationSeconds"}
    props = {k: v for k, v in params.items() if k not in render_keys}

    comp = Composition(
        id=name, template=str(template_path),
        duration_seconds=duration, fps=fps, width=width, height=height, props=props,
    )

    try:
        out_path = comp.render(output=output, codec=params.get("codec", "libx264"))
        return {"status": "success", "output": str(out_path),
                "message": f"Rendered: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


EXECUTORS = {
    "concat": exec_concat,
    "mix-audio": exec_mix_audio,
    "subtitles": exec_subtitles,
    "transition": exec_transition,
}

TEMPLATE_SKILLS = {"demo", "slideshow", "text-overlay"}


def execute_skill(name: str, params: dict) -> dict:
    if name in EXECUTORS:
        return EXECUTORS[name](params)
    elif name in TEMPLATE_SKILLS:
        return exec_template(name, params)
    else:
        return {"status": "error", "message": f"Unknown skill: {name}"}


def main():
    parser = argparse.ArgumentParser(description="vibe-mpeg renderer")
    parser.add_argument("skill", nargs="?", help="Skill name")
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
