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
import os
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
    return str(OUT_DIR / datetime.now().strftime(f"{prefix}-%m%d-%H%M.{ext}"))


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
    sub = params.get("srt") or params.get("sub") or params.get("ass")
    font = params.get("font", "Helvetica")
    font_size = params.get("fontSize", 24)
    output = params.get("output", ts_output("subtitled"))
    OUT_DIR.mkdir(exist_ok=True)

    # Detect subtitle format by extension
    sub_ext = Path(sub).suffix.lower()
    if sub_ext == ".ass":
        # ASS: use ass filter to preserve native styling
        vf = f"ass={sub}"
    else:
        # SRT/VTT: use subtitles filter with force_style
        style = f"FontName={font},FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2"
        vf = f"subtitles={sub}:force_style='{style}'"

    cmd = [
        "ffmpeg", "-y", "-i", video,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "23", "-c:a", "copy",
        output,
    ]

    result = run_ffmpeg(cmd)
    result["output"] = output
    return result


def exec_reformat(params: dict) -> dict:
    """Crop, scale, trim, or speed-adjust a video."""
    video = params["video"]
    output = params.get("output", ts_output("reformat"))
    OUT_DIR.mkdir(exist_ok=True)

    filters = []
    # Trim (in/out points)
    input_args = []
    if "in" in params:
        input_args += ["-ss", str(params["in"])]
    if "out" in params:
        input_args += ["-to", str(params["out"])]
    elif "duration" in params:
        input_args += ["-t", str(params["duration"])]
    # Crop
    if "crop" in params:
        c = params["crop"]
        filters.append(f"crop={c['w']}:{c['h']}:{c.get('x',0)}:{c.get('y',0)}")
    # Scale
    if "scale" in params:
        s = params["scale"]
        filters.append(f"scale={s['w']}:{s['h']}")
    # Speed
    if "speed" in params:
        spd = params["speed"]
        filters.append(f"setpts={1/spd}*PTS")
    # Rotate
    if "rotate" in params:
        deg = params["rotate"]
        if deg == 90:
            filters.append("transpose=1")
        elif deg == 270 or deg == -90:
            filters.append("transpose=2")
        elif deg == 180:
            filters.append("transpose=1,transpose=1")
    # Pad (for letterbox/pillarbox)
    if "pad" in params:
        p = params["pad"]
        filters.append(f"pad={p['w']}:{p['h']}:{p.get('x','(ow-iw)/2')}:{p.get('y','(oh-ih)/2')}:black")
    # Fade
    if "fade_in" in params:
        filters.append(f"fade=t=in:st=0:d={params['fade_in']}")
    if "fade_out" in params:
        filters.append(f"fade=t=out:st={params.get('fade_out_start', 0)}:d={params['fade_out']}")
    # Raw filter passthrough
    if "filter" in params:
        filters.append(params["filter"])

    cmd = ["ffmpeg", "-y"] + input_args + ["-i", video]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += ["-c:v", "libx264", "-crf", str(params.get("crf", 23)), "-c:a", "aac", output]

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


def exec_probe(params: dict) -> dict:
    file = params["file"]
    show_streams = params.get("streams", True)
    show_tags = params.get("tags", True)

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format",
    ]
    if show_streams:
        cmd.append("-show_streams")
    cmd.append(file)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"status": "error", "message": result.stderr[-1000:]}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Failed to parse ffprobe output"}

    # Build clean response
    info = {"status": "success", "file": file}

    fmt = data.get("format", {})
    info["format"] = {
        "filename": fmt.get("filename"),
        "format_name": fmt.get("format_name"),
        "duration": float(fmt["duration"]) if "duration" in fmt else None,
        "size_bytes": int(fmt["size"]) if "size" in fmt else None,
        "bit_rate": int(fmt["bit_rate"]) if "bit_rate" in fmt else None,
    }

    if show_tags and "tags" in fmt:
        info["tags"] = fmt["tags"]

    if show_streams and "streams" in data:
        info["streams"] = []
        for s in data["streams"]:
            stream = {
                "index": s.get("index"),
                "codec_type": s.get("codec_type"),
                "codec_name": s.get("codec_name"),
            }
            if s.get("codec_type") == "audio":
                stream.update({
                    "sample_rate": s.get("sample_rate"),
                    "channels": s.get("channels"),
                    "channel_layout": s.get("channel_layout"),
                    "bit_rate": s.get("bit_rate"),
                })
            elif s.get("codec_type") == "video":
                stream.update({
                    "width": s.get("width"),
                    "height": s.get("height"),
                    "fps": s.get("r_frame_rate"),
                    "pix_fmt": s.get("pix_fmt"),
                })
            if show_tags and "tags" in s:
                stream["tags"] = s["tags"]
            info["streams"].append(stream)

    return info


def exec_render(params: dict) -> dict:
    """List available skills or show skill details."""
    skill_name = params.get("skill")
    if skill_name:
        try:
            defn = load_skill(skill_name)
            return {"status": "success", "skill": defn}
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    # List all skills
    skills = []
    for p in sorted(SKILLS_DIR.glob("*.json")):
        if p.stem == "render":
            continue
        defn = load_skill(p.stem)
        skills.append({"name": p.stem, "description": defn.get("description", "")})
    return {"status": "success", "skills": skills}


EXECUTORS = {
    "concat": exec_concat,
    "mix-audio": exec_mix_audio,
    "subtitles": exec_subtitles,
    "transition": exec_transition,
    "probe": exec_probe,
    "render": exec_render,
    "reformat": exec_reformat,
}

TEMPLATE_SKILLS = {"demo", "slideshow", "text-overlay"}

PROJECTS_DIR = ROOT / "projects"


def exec_project(params: dict) -> dict:
    """Run a project (sequence of skill steps) or list available projects."""
    project_name = params.get("name") or params.get("project")
    if not project_name:
        # List projects
        projects = []
        if PROJECTS_DIR.is_dir():
            for p in sorted(PROJECTS_DIR.glob("*.json")):
                try:
                    with open(p) as f:
                        defn = json.load(f)
                    projects.append({
                        "name": p.stem,
                        "description": defn.get("description", ""),
                        "steps": len(defn.get("steps", [])),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        return {"status": "success", "projects": projects}

    # Load and run project
    project_path = PROJECTS_DIR / f"{project_name}.json"
    if not project_path.exists():
        available = [p.stem for p in PROJECTS_DIR.glob("*.json")] if PROJECTS_DIR.is_dir() else []
        return {"status": "error", "message": f"Unknown project: {project_name}. Available: {available}"}

    with open(project_path) as f:
        project = json.load(f)

    results = []
    prev_result = {}
    for i, step in enumerate(project.get("steps", [])):
        skill_name = step["skill"]
        step_params = dict(step.get("params", {}))
        # Resolve ${prev.output} references
        for k, v in step_params.items():
            if isinstance(v, str) and "${prev.output}" in v:
                prev_output = prev_result.get("output", "")
                step_params[k] = v.replace("${prev.output}", prev_output)
        print(f"[{i+1}/{len(project['steps'])}] {skill_name}", file=sys.stderr)
        result = execute_skill(skill_name, step_params)
        results.append({"step": i + 1, "skill": skill_name, "result": result})
        prev_result = result
        if result.get("status") == "error":
            return {"status": "error", "message": f"Step {i+1} ({skill_name}) failed", "results": results}

    # Rename final output to {project}-{MMDD}-{HHMM}.mp4
    final_output = prev_result.get("output", "")
    if final_output and os.path.isfile(final_output):
        ext = Path(final_output).suffix
        renamed = str(OUT_DIR / datetime.now().strftime(f"{project_name}-%m%d-%H%M{ext}"))
        os.rename(final_output, renamed)
        prev_result["output"] = renamed
        results[-1]["result"]["output"] = renamed
        print(f"[output] {renamed}", file=sys.stderr)

    return {"status": "success", "project": project_name, "output": prev_result.get("output", ""), "results": results}


EXECUTORS["project"] = exec_project


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
