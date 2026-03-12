#!/usr/bin/env python3
"""
vibe-mpeg editor server — localhost web UI for media browsing, timeline, and preview.
Inspired by Remotion Studio layout.

Usage:
    python3 server.py              # http://localhost:3333
    python3 server.py --port 8080  # custom port
"""

import argparse
import json
import mimetypes
import os
import socket
import subprocess
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).parent
MEDIA_DIR = ROOT / "media"
OUT_DIR = ROOT / "out"
PROJECTS_DIR = ROOT / "projects"
SKILLS_DIR = ROOT / "skills"


def probe_file(filepath: str) -> dict:
    """Get media file metadata via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", filepath],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def scan_media(directory: Path) -> list:
    """Scan directory for media files."""
    files = []
    if not directory.is_dir():
        return files
    for f in sorted(directory.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            stat = f.stat()
            ext = f.suffix.lower()
            media_type = "video" if ext in (".mp4", ".mov", ".webm", ".mkv") else \
                         "audio" if ext in (".mp3", ".wav", ".aac", ".m4a") else \
                         "subtitle" if ext in (".srt", ".ass", ".lrc", ".vtt") else \
                         "image" if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "other"
            files.append({
                "name": f.name,
                "path": str(f),
                "relpath": str(f.relative_to(ROOT)),
                "size": stat.st_size,
                "type": media_type,
                "ext": ext,
            })
    return files


class EditorHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the editor UI and API endpoints."""

    def log_message(self, format, *args):
        pass  # quiet

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # API routes
        if path == "/api/media":
            self._json_response(scan_media(MEDIA_DIR))
        elif path == "/api/output":
            self._json_response(scan_media(OUT_DIR))
        elif path == "/api/skills":
            skills = []
            if SKILLS_DIR.is_dir():
                for p in sorted(SKILLS_DIR.glob("*.json")):
                    with open(p) as f:
                        skills.append(json.load(f))
            self._json_response(skills)
        elif path == "/api/projects":
            projects = []
            if PROJECTS_DIR.is_dir():
                for p in sorted(PROJECTS_DIR.glob("*.json")):
                    with open(p) as f:
                        projects.append(json.load(f))
            self._json_response(projects)
        elif path.startswith("/api/probe"):
            qs = urllib.parse.parse_qs(parsed.query)
            filepath = qs.get("file", [""])[0]
            if filepath and os.path.isfile(filepath):
                self._json_response(probe_file(filepath))
            else:
                self._json_response({"error": "file not found"}, 404)
        elif path.startswith("/file/"):
            # Serve media/output files directly
            relpath = urllib.parse.unquote(path[6:])
            fullpath = ROOT / relpath
            if fullpath.is_file():
                self._serve_file(fullpath)
            else:
                self._json_response({"error": "not found"}, 404)
        elif path == "/" or path == "/index.html":
            self._serve_html()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/render":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            skill = body.get("skill", "")
            params = body.get("params", {})
            try:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "render.py"), "--stdin"],
                    input=json.dumps({"skill": skill, "params": params}),
                    capture_output=True, text=True, timeout=120,
                    cwd=str(ROOT),
                )
                output = json.loads(result.stdout) if result.stdout.strip() else {}
                self._json_response(output)
            except Exception as e:
                self._json_response({"status": "error", "message": str(e)}, 500)
        elif parsed.path == "/api/project/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            name = body.get("name", "")
            try:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "render.py"), "project", "--name", name],
                    capture_output=True, text=True, timeout=300,
                    cwd=str(ROOT),
                )
                output = json.loads(result.stdout) if result.stdout.strip() else {}
                self._json_response(output)
            except Exception as e:
                self._json_response({"status": "error", "message": str(e)}, 500)
        elif parsed.path == "/api/file/rename":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            self._handle_file_rename(body)
        elif parsed.path == "/api/file/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            self._handle_file_delete(body)
        elif parsed.path == "/api/upload":
            self._handle_upload()
        elif parsed.path == "/api/project/save":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            self._handle_project_save(body)
        elif parsed.path == "/api/project/create":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            self._handle_project_create(body)
        else:
            self.send_error(404)

    # ── Allowed directories for file operations ──
    MANAGED_DIRS = ("out", "projects", "media")

    def _validate_managed_path(self, relpath: str) -> Path | None:
        """Validate that relpath is within out/ or projects/. Returns absolute path or None."""
        if not relpath:
            return None
        # Normalize and resolve to prevent traversal
        target = (ROOT / relpath).resolve()
        for d in self.MANAGED_DIRS:
            allowed = (ROOT / d).resolve()
            if str(target).startswith(str(allowed) + os.sep) or target == allowed:
                if target.exists():
                    return target
        return None

    def _handle_file_rename(self, body: dict):
        filepath = body.get("path", "")
        new_name = body.get("newName", "")
        if not new_name or os.sep in new_name or "/" in new_name:
            self._json_response({"error": "Invalid new name"}, 400)
            return
        target = self._validate_managed_path(filepath)
        if not target:
            self._json_response({"error": "File not found or not in managed directory"}, 403)
            return
        new_path = target.parent / new_name
        if new_path.exists():
            self._json_response({"error": f"{new_name} already exists"}, 409)
            return
        target.rename(new_path)
        self._json_response({"status": "success", "path": str(new_path.relative_to(ROOT))})

    def _handle_file_delete(self, body: dict):
        filepath = body.get("path", "")
        target = self._validate_managed_path(filepath)
        if not target:
            self._json_response({"error": "File not found or not in managed directory"}, 403)
            return
        if target.name == "readme.txt":
            self._json_response({"error": "Cannot delete readme.txt"}, 403)
            return
        target.unlink()
        self._json_response({"status": "success"})

    def _handle_project_save(self, body: dict):
        """Save project steps back to JSON."""
        name = body.get("name", "")
        steps = body.get("steps")
        if not name or steps is None:
            self._json_response({"error": "name and steps required"}, 400)
            return
        project_path = PROJECTS_DIR / f"{name}.json"
        if not project_path.exists():
            self._json_response({"error": f"Project {name} not found"}, 404)
            return
        with open(project_path) as f:
            project = json.load(f)
        project["steps"] = steps
        if "description" in body:
            project["description"] = body["description"]
        if "format" in body:
            project["format"] = body["format"]
        with open(project_path, "w") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)
            f.write("\n")
        self._json_response({"status": "success"})

    def _handle_project_create(self, body: dict):
        """Create a new project."""
        name = body.get("name", "").strip()
        if not name or "/" in name or "\\" in name:
            self._json_response({"error": "Invalid project name"}, 400)
            return
        project_path = PROJECTS_DIR / f"{name}.json"
        if project_path.exists():
            self._json_response({"error": f"Project {name} already exists"}, 409)
            return
        project = {
            "name": name,
            "description": body.get("description", ""),
            "media_dir": "media",
            "output_dir": "out",
            "steps": body.get("steps", []),
        }
        PROJECTS_DIR.mkdir(exist_ok=True)
        with open(project_path, "w") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)
            f.write("\n")
        self._json_response({"status": "success", "name": name})

    def _handle_upload(self):
        """Handle multipart file upload to media/."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._json_response({"error": "Expected multipart/form-data"}, 400)
            return
        # Parse boundary
        boundary = content_type.split("boundary=")[-1].encode()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        # Simple multipart parser
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" not in part:
                continue
            # Extract filename
            header_end = part.find(b"\r\n\r\n")
            if header_end < 0:
                continue
            header = part[:header_end].decode("utf-8", errors="replace")
            file_data = part[header_end + 4:]
            if file_data.endswith(b"\r\n"):
                file_data = file_data[:-2]
            # Get filename from Content-Disposition
            fname = ""
            for line in header.split("\r\n"):
                if "filename=" in line:
                    fname = line.split('filename="')[-1].rstrip('"')
                    break
            if not fname or "/" in fname or "\\" in fname:
                continue
            dest = MEDIA_DIR / fname
            with open(dest, "wb") as f:
                f.write(file_data)
            self._json_response({
                "status": "success",
                "name": fname,
                "size": len(file_data),
                "path": str(dest.relative_to(ROOT)),
            })
            return
        self._json_response({"error": "No file found in upload"}, 400)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: Path):
        mime, _ = mimetypes.guess_type(str(filepath))
        if not mime:
            mime = "application/octet-stream"
        size = filepath.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _serve_html(self):
        html = EDITOR_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


EDITOR_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vibe-mpeg editor</title>
<style>
:root {
  --bg: #1f2428;
  --bg-dark: #111;
  --bg-input: #2f363d;
  --border: rgba(255,255,255,0.08);
  --blue: #0b84f3;
  --text: #e1e4e8;
  --text-dim: #8b949e;
  --green: #3fb950;
  --orange: #d29922;
  --red: #f85149;
  --sidebar-w: 240px;
  --toolbar-h: 44px;
  --timeline-h: 220px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  height: 100vh;
  width: 100vw;
}

/* Layout */
.editor { display: flex; flex-direction: column; height: 100vh; }
.toolbar {
  height: var(--toolbar-h);
  background: var(--bg-dark);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
  flex-shrink: 0;
}
.toolbar .logo { font-weight: 700; font-size: 14px; color: var(--blue); }
.toolbar .spacer { flex: 1; }
.toolbar button {
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}
.toolbar button:hover { background: var(--blue); }
.toolbar button.primary { background: var(--blue); border-color: var(--blue); }

.main { display: flex; flex: 1; overflow: hidden; }

/* Left Sidebar */
.sidebar-left {
  width: var(--sidebar-w);
  background: var(--bg-dark);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sidebar-tabs button {
  flex: 1;
  background: none;
  border: none;
  color: var(--text-dim);
  padding: 8px 0;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.sidebar-tabs button.active {
  color: var(--text);
  border-bottom-color: var(--blue);
}
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.file-item {
  padding: 6px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  border-left: 3px solid transparent;
}
.file-item:hover { background: rgba(255,255,255,0.05); }
.file-item.selected { background: rgba(11,132,243,0.15); border-left-color: var(--blue); }
.file-item .icon { font-size: 14px; flex-shrink: 0; }
.file-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: text; }
.file-item .name:hover { text-decoration: underline; text-decoration-style: dotted; }
.file-item .meta { color: var(--text-dim); font-size: 10px; flex-shrink: 0; }
.file-item .actions { display: none; gap: 2px; flex-shrink: 0; }
.file-item.selected .actions, .file-item:hover .actions { display: flex; }
.file-item .actions button {
  background: none; border: none; cursor: pointer; font-size: 12px;
  padding: 2px 4px; border-radius: 3px; color: var(--text-dim); line-height: 1;
}
.file-item .actions button:hover { background: rgba(255,255,255,0.1); color: var(--text); }
.file-item .actions button.danger:hover { color: var(--red); }
.upload-zone {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.upload-zone label {
  display: block;
  text-align: center;
  padding: 8px;
  border: 1px dashed var(--border);
  border-radius: 4px;
  font-size: 11px;
  color: var(--text-dim);
  cursor: pointer;
}
.upload-zone label:hover { border-color: var(--blue); color: var(--blue); }
.upload-zone input { display: none; }

/* Center: Canvas/Preview */
.canvas-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #000;
  position: relative;
}
.preview-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}
.preview-container video {
  max-width: 100%;
  max-height: 100%;
  border-radius: 2px;
}
.preview-container .empty-state {
  color: var(--text-dim);
  font-size: 14px;
  text-align: center;
}
.preview-container .empty-state .hint { font-size: 11px; margin-top: 8px; }

/* Player Controls */
.player-controls {
  height: 48px;
  background: var(--bg);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
  flex-shrink: 0;
}
.player-controls button {
  background: none;
  border: none;
  color: var(--text);
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}
.player-controls button:hover { background: rgba(255,255,255,0.1); }
.player-controls .time {
  font-size: 12px;
  font-family: 'SF Mono', 'Menlo', monospace;
  color: var(--text-dim);
  min-width: 120px;
}
.player-controls .progress-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-input);
  border-radius: 2px;
  cursor: pointer;
  position: relative;
}
.player-controls .progress-bar .fill {
  height: 100%;
  background: var(--blue);
  border-radius: 2px;
  transition: width 0.1s;
}

/* Right Sidebar */
.sidebar-right {
  width: 260px;
  background: var(--bg-dark);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.props-section {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}
.props-section h3 {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-dim);
  margin-bottom: 8px;
}
.prop-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}
.prop-row .label { color: var(--text-dim); }
.prop-row .value { color: var(--text); font-family: 'SF Mono', 'Menlo', monospace; font-size: 11px; }
.skill-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.skill-item {
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12px;
  border-left: 3px solid transparent;
}
.skill-item:hover { background: rgba(255,255,255,0.05); }
.skill-item .skill-name { font-weight: 600; color: var(--blue); }
.skill-item .skill-desc { color: var(--text-dim); font-size: 11px; margin-top: 2px; }

/* Splitter handles */
.splitter-h, .splitter-v {
  flex-shrink: 0;
  background: var(--border);
  z-index: 10;
}
.splitter-h {
  height: 3px;
  cursor: row-resize;
}
.splitter-v {
  width: 3px;
  cursor: col-resize;
}
.splitter-h:hover, .splitter-v:hover { background: var(--blue); }

/* Timeline */
.timeline-area {
  height: var(--timeline-h);
  background: var(--bg-dark);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.timeline-header {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-bottom: 1px solid var(--border);
  gap: 8px;
  flex-shrink: 0;
}
.timeline-header h3 {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-dim);
}
.timeline-header select {
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}
.timeline-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.timeline-labels {
  width: 140px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  overflow-y: auto;
}
.timeline-label {
  height: 48px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
}
.timeline-tracks-area {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
  position: relative;
}
.timeline-ruler {
  height: 24px;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 5;
}
.timeline-ruler canvas { width: 100%; height: 100%; }
.timeline-tracks { position: relative; }
.timeline-track {
  height: 48px;
  position: relative;
  border-bottom: 1px solid var(--border);
}
.timeline-clip {
  position: absolute;
  top: 4px;
  height: 40px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.timeline-clip.video { background: rgba(11,132,243,0.4); border: 1px solid rgba(11,132,243,0.6); color: #7cc4fa; }
.timeline-clip.audio { background: rgba(63,185,80,0.3); border: 1px solid rgba(63,185,80,0.5); color: #7ee787; }
.timeline-clip.subtitle { background: rgba(210,153,34,0.3); border: 1px solid rgba(210,153,34,0.5); color: #e3b341; }
.timeline-clip.effect { background: rgba(188,86,221,0.3); border: 1px solid rgba(188,86,221,0.5); color: #d2a8ff; }

.timeline-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--red);
  z-index: 20;
  pointer-events: none;
}
.timeline-playhead::before {
  content: '';
  position: absolute;
  top: 0;
  left: -5px;
  width: 12px;
  height: 12px;
  background: var(--red);
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}

/* Scrollbar styling */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }

/* Status bar */
.status-bar {
  height: 24px;
  background: var(--bg-dark);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 11px;
  color: var(--text-dim);
  gap: 16px;
  flex-shrink: 0;
}
.status-bar .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); }

/* Toast */
.toast {
  position: fixed;
  bottom: 40px;
  right: 16px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 12px;
  z-index: 1000;
  display: none;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<div class="editor" id="app">
  <!-- Toolbar -->
  <div class="toolbar">
    <span class="logo">vibe-mpeg</span>
    <span style="font-size:11px;color:var(--text-dim)">editor</span>
    <span class="spacer"></span>
    <button onclick="refreshAll()">Refresh</button>
    <button class="primary" onclick="runProject()">Render Project</button>
  </div>

  <!-- Main -->
  <div class="main">
    <!-- Left Sidebar -->
    <div class="sidebar-left" id="sidebarLeft">
      <div class="sidebar-tabs">
        <button class="active" onclick="switchTab(this,'media')">Media</button>
        <button onclick="switchTab(this,'output')">Output</button>
      </div>
      <div class="file-list" id="mediaList"></div>
      <div class="file-list" id="outputList" style="display:none"></div>
      <div class="upload-zone" id="uploadZone">
        <label for="fileUpload">+ Upload to media/</label>
        <input type="file" id="fileUpload" multiple accept="video/*,audio/*,image/*,.srt,.ass,.vtt,.lrc" onchange="uploadFiles(this.files)">
      </div>
    </div>

    <div class="splitter-v" id="splitterLeft"></div>

    <!-- Center -->
    <div class="canvas-area">
      <div class="preview-container" id="previewContainer">
        <div class="empty-state">
          <div>No media selected</div>
          <div class="hint">Click a file in the sidebar to preview</div>
        </div>
      </div>
      <div class="player-controls">
        <button onclick="playerAction('prev')" title="Previous">&#9198;</button>
        <button onclick="playerAction('play')" id="btnPlay" title="Play/Pause">&#9654;</button>
        <button onclick="playerAction('next')" title="Next">&#9197;</button>
        <span class="time" id="timeDisplay">00:00.0 / 00:00.0</span>
        <div class="progress-bar" id="progressBar" onclick="seekTo(event)">
          <div class="fill" id="progressFill" style="width:0"></div>
        </div>
      </div>
    </div>

    <div class="splitter-v" id="splitterRight"></div>

    <!-- Right Sidebar -->
    <div class="sidebar-right" id="sidebarRight">
      <div class="sidebar-tabs">
        <button class="active" onclick="switchRightTab(this,'props')">Properties</button>
        <button onclick="switchRightTab(this,'skills')">Skills</button>
      </div>
      <div id="propsPanel">
        <div class="props-section" id="fileProps">
          <h3>File Info</h3>
          <div style="font-size:12px;color:var(--text-dim);padding:4px 0;">Select a file</div>
        </div>
      </div>
      <div id="skillsPanel" style="display:none">
        <div class="skill-list" id="skillList"></div>
      </div>
    </div>
  </div>

  <!-- Splitter (horizontal) -->
  <div class="splitter-h" id="splitterTimeline"></div>

  <!-- Timeline -->
  <div class="timeline-area" id="timelineArea">
    <div class="timeline-header">
      <h3>Timeline</h3>
      <select id="projectSelect" onchange="loadProject(this.value)">
        <option value="">-- Select Project --</option>
      </select>
    </div>
    <div class="timeline-body">
      <div class="timeline-labels" id="timelineLabels"></div>
      <div class="timeline-tracks-area" id="timelineTracksArea">
        <div class="timeline-ruler" id="timelineRuler"></div>
        <div class="timeline-tracks" id="timelineTracks">
          <div class="timeline-playhead" id="playhead" style="left:0"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Status Bar -->
  <div class="status-bar">
    <span class="dot"></span>
    <span>Ready</span>
    <span class="spacer"></span>
    <span id="statusInfo">localhost</span>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── State ──
let state = {
  media: [],
  output: [],
  skills: [],
  projects: [],
  selected: null, // {path, name, type, relpath}
  probeData: null,
  currentProject: null,
};

// ── API ──
async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.json();
}

// ── Init ──
async function refreshAll() {
  const [media, output, skills, projects] = await Promise.all([
    api('/api/media'), api('/api/output'), api('/api/skills'), api('/api/projects'),
  ]);
  state.media = media;
  state.output = output;
  state.skills = skills;
  state.projects = projects;
  renderMediaList();
  renderOutputList();
  renderSkillList();
  renderProjectSelect();
}

// ── Media List ──
function fileItemHTML(f, listName, index) {
  const sel = state.selected?.path === f.path ? 'selected' : '';
  const canDelete = f.name !== 'readme.txt';
  return `
    <div class="file-item ${sel}" onclick="selectFromList('${listName}',${index})">
      <span class="icon">${typeIcon(f.type)}</span>
      <span class="name" onclick="event.stopPropagation();renameFile('${listName}',${index})" title="Click to rename">${esc(f.name)}</span>
      <span class="actions">
        ${f.type === 'video' || f.type === 'audio' || f.type === 'subtitle'
          ? `<button onclick="event.stopPropagation();addToTimeline('${listName}',${index})" title="Add to timeline">↙️</button>` : ''}
        ${canDelete ? `<button class="danger" onclick="event.stopPropagation();deleteFile('${listName}',${index})" title="Delete">🗑️</button>` : ''}
      </span>
      <span class="meta">${formatSize(f.size)}</span>
    </div>`;
}

function renderMediaList() {
  const el = document.getElementById('mediaList');
  el.innerHTML = state.media.map((f, i) => fileItemHTML(f, 'media', i)).join('');
}

function renderOutputList() {
  const el = document.getElementById('outputList');
  el.innerHTML = state.output.map((f, i) => fileItemHTML(f, 'output', i)).join('');
}

function selectFromList(list, index) {
  const file = list === 'media' ? state.media[index] : state.output[index];
  if (file) selectFile(file);
}

// ── File Operations ──
async function renameFile(list, index) {
  const file = (list === 'media' ? state.media : state.output)[index];
  if (!file || file.name === 'readme.txt') return;
  const newName = prompt('Rename:', file.name);
  if (!newName || newName === file.name) return;
  const res = await api('/api/file/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: file.relpath, newName }),
  });
  if (res.status === 'success') {
    toast(`Renamed → ${newName}`);
    await refreshAll();
  } else {
    toast(res.error || 'Rename failed');
  }
}

async function deleteFile(list, index) {
  const file = (list === 'media' ? state.media : state.output)[index];
  if (!file || file.name === 'readme.txt') return;
  if (!confirm(`Delete ${file.name}?`)) return;
  const res = await api('/api/file/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: file.relpath }),
  });
  if (res.status === 'success') {
    toast(`Deleted ${file.name}`);
    if (state.selected?.path === file.path) state.selected = null;
    await refreshAll();
  } else {
    toast(res.error || 'Delete failed');
  }
}

function addToTimeline(list, index) {
  const file = (list === 'media' ? state.media : state.output)[index];
  if (!file) return;
  // Determine skill based on type
  const skill = file.type === 'audio' ? 'mix-audio' : file.type === 'subtitle' ? 'subtitles' : 'probe';
  const paramKey = file.type === 'audio' ? 'audio' : file.type === 'subtitle' ? 'sub' : 'video';
  toast(`↙️ ${file.name} → timeline as ${skill} (${paramKey})`);
  // TODO: interactive timeline editing — for now show what would be added
}

async function uploadFiles(files) {
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/api/upload', { method: 'POST', body: form });
      const data = await res.json();
      if (data.status === 'success') {
        toast(`Uploaded ${data.name} (${formatSize(data.size)})`);
      } else {
        toast(data.error || 'Upload failed');
      }
    } catch (e) {
      toast('Upload error: ' + e.message);
    }
  }
  document.getElementById('fileUpload').value = '';
  await refreshAll();
}

function typeIcon(type) {
  return { video: '🎬', audio: '🎵', subtitle: '📝', image: '🖼', other: '📄' }[type] || '📄';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + 'KB';
  return (bytes/1048576).toFixed(1) + 'MB';
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── File Selection ──
async function selectFile(file) {
  if (typeof file === 'string') file = JSON.parse(file);
  state.selected = file;
  renderMediaList();
  renderOutputList();

  // Preview
  const container = document.getElementById('previewContainer');
  if (file.type === 'video') {
    container.innerHTML = `<video id="videoPlayer" src="/file/${encodeURIComponent(file.relpath)}" controls></video>`;
    const vid = document.getElementById('videoPlayer');
    vid.addEventListener('timeupdate', updateTime);
    vid.addEventListener('loadedmetadata', updateTime);
    vid.addEventListener('play', () => document.getElementById('btnPlay').innerHTML = '&#9646;&#9646;');
    vid.addEventListener('pause', () => document.getElementById('btnPlay').innerHTML = '&#9654;');
  } else if (file.type === 'audio') {
    container.innerHTML = `
      <div style="text-align:center">
        <div style="font-size:64px;margin-bottom:16px">🎵</div>
        <div style="font-size:14px;color:var(--text)">${esc(file.name)}</div>
        <audio id="videoPlayer" src="/file/${encodeURIComponent(file.relpath)}" controls style="margin-top:16px;width:80%"></audio>
      </div>`;
    const aud = document.getElementById('videoPlayer');
    aud.addEventListener('timeupdate', updateTime);
    aud.addEventListener('loadedmetadata', updateTime);
  } else {
    container.innerHTML = `<div class="empty-state"><div>${esc(file.name)}</div><div class="hint">${file.type} file</div></div>`;
  }

  // Probe
  state.probeData = await api(`/api/probe?file=${encodeURIComponent(file.path)}`);
  renderProps();
}

function renderProps() {
  const el = document.getElementById('fileProps');
  const f = state.selected;
  const p = state.probeData;
  if (!f) { el.innerHTML = '<h3>File Info</h3><div style="font-size:12px;color:var(--text-dim);padding:4px 0;">Select a file</div>'; return; }

  let rows = `<div class="prop-row"><span class="label">Name</span><span class="value">${esc(f.name)}</span></div>`;
  rows += `<div class="prop-row"><span class="label">Size</span><span class="value">${formatSize(f.size)}</span></div>`;
  rows += `<div class="prop-row"><span class="label">Type</span><span class="value">${esc(f.type)}</span></div>`;

  if (p?.format) {
    const dur = parseFloat(p.format.duration || 0);
    rows += `<div class="prop-row"><span class="label">Duration</span><span class="value">${formatTime(dur)}</span></div>`;
    if (p.format.bit_rate) rows += `<div class="prop-row"><span class="label">Bitrate</span><span class="value">${Math.round(parseInt(p.format.bit_rate)/1000)}kbps</span></div>`;
  }
  if (p?.streams) {
    for (const s of p.streams) {
      if (s.codec_type === 'video') {
        rows += `<div class="prop-row"><span class="label">Video</span><span class="value">${s.codec_name} ${s.width}x${s.height}</span></div>`;
        if (s.r_frame_rate) rows += `<div class="prop-row"><span class="label">FPS</span><span class="value">${evalFps(s.r_frame_rate)}</span></div>`;
      } else if (s.codec_type === 'audio') {
        rows += `<div class="prop-row"><span class="label">Audio</span><span class="value">${s.codec_name} ${s.sample_rate}Hz ${s.channels}ch</span></div>`;
      }
    }
  }

  el.innerHTML = `<h3>File Info</h3>${rows}`;
}

function evalFps(rate) {
  if (!rate) return '?';
  const [n, d] = rate.split('/');
  return d ? (parseInt(n)/parseInt(d)).toFixed(1) : rate;
}

// ── Skills ──
function renderSkillList() {
  const el = document.getElementById('skillList');
  el.innerHTML = state.skills.filter(s => s.name !== 'render' && s.name !== 'project').map(s => `
    <div class="skill-item" onclick="showSkillDetail('${esc(s.name)}')">
      <div class="skill-name">/${esc(s.name)}</div>
      <div class="skill-desc">${esc(s.description || '')}</div>
    </div>
  `).join('');
}

function showSkillDetail(name) {
  const skill = state.skills.find(s => s.name === name);
  if (!skill) return;
  toast(`/${name}: ${skill.description}`);
}

// ── Projects / Timeline ──
function renderProjectSelect() {
  const el = document.getElementById('projectSelect');
  el.innerHTML = '<option value="">-- Select Project --</option>' +
    state.projects.map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${p.steps?.length || 0} steps)</option>`).join('');
}

function loadProject(name) {
  if (!name) { clearTimeline(); return; }
  const proj = state.projects.find(p => p.name === name);
  if (!proj) return;
  state.currentProject = proj;
  renderTimeline(proj);
}

function clearTimeline() {
  document.getElementById('timelineLabels').innerHTML = '';
  document.getElementById('timelineTracks').innerHTML = '<div class="timeline-playhead" id="playhead" style="left:0"></div>';
  state.currentProject = null;
}

function renderTimeline(project) {
  const steps = project.steps || [];
  const totalDuration = steps.length * 30; // estimate 30s per step
  const pxPerSec = 10;
  const totalWidth = totalDuration * pxPerSec;

  // Labels
  const labels = document.getElementById('timelineLabels');
  labels.innerHTML = steps.map((s, i) => `
    <div class="timeline-label">${i+1}. ${s.skill}</div>
  `).join('');

  // Tracks
  const tracks = document.getElementById('timelineTracks');
  tracks.style.width = totalWidth + 'px';
  let html = '<div class="timeline-playhead" id="playhead" style="left:0"></div>';

  steps.forEach((step, i) => {
    const left = i * 30 * pxPerSec;
    const width = 28 * pxPerSec;
    const clipType = step.skill === 'probe' ? 'effect' :
                     step.skill.includes('audio') || step.skill.includes('mix') ? 'audio' :
                     step.skill.includes('subtitle') ? 'subtitle' : 'video';
    html += `
      <div class="timeline-track">
        <div class="timeline-clip ${clipType}" style="left:${left}px;width:${width}px" title="${step.skill}">
          ${step.skill}
        </div>
      </div>
    `;
  });
  tracks.innerHTML = html;

  // Ruler
  drawRuler(totalDuration, pxPerSec);
}

function drawRuler(totalDuration, pxPerSec) {
  const area = document.getElementById('timelineRuler');
  area.innerHTML = `<canvas id="rulerCanvas" width="${totalDuration * pxPerSec}" height="24"></canvas>`;
  const canvas = document.getElementById('rulerCanvas');
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#8b949e';
  ctx.font = '10px -apple-system, sans-serif';
  for (let t = 0; t <= totalDuration; t += 5) {
    const x = t * pxPerSec;
    ctx.fillRect(x, 16, 1, 8);
    if (t % 10 === 0) {
      ctx.fillRect(x, 12, 1, 12);
      ctx.fillText(formatTime(t), x + 3, 10);
    }
  }
}

// ── Player ──
function playerAction(action) {
  const player = document.getElementById('videoPlayer');
  if (!player) return;
  if (action === 'play') { player.paused ? player.play() : player.pause(); }
  else if (action === 'prev') { player.currentTime = Math.max(0, player.currentTime - 5); }
  else if (action === 'next') { player.currentTime = Math.min(player.duration, player.currentTime + 5); }
}

function updateTime() {
  const player = document.getElementById('videoPlayer');
  if (!player) return;
  const cur = player.currentTime || 0;
  const dur = player.duration || 0;
  document.getElementById('timeDisplay').textContent = `${formatTime(cur)} / ${formatTime(dur)}`;
  const pct = dur > 0 ? (cur / dur * 100) : 0;
  document.getElementById('progressFill').style.width = pct + '%';
}

function seekTo(e) {
  const player = document.getElementById('videoPlayer');
  if (!player || !player.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const ratio = (e.clientX - rect.left) / rect.width;
  player.currentTime = ratio * player.duration;
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1);
  return `${String(m).padStart(2,'0')}:${s.padStart(4,'0')}`;
}

// ── Tab Switching ──
function switchTab(btn, tab) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('mediaList').style.display = tab === 'media' ? '' : 'none';
  document.getElementById('outputList').style.display = tab === 'output' ? '' : 'none';
}

function switchRightTab(btn, tab) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('propsPanel').style.display = tab === 'props' ? '' : 'none';
  document.getElementById('skillsPanel').style.display = tab === 'skills' ? '' : 'none';
}

// ── Render ──
async function runProject() {
  if (!state.currentProject) { toast('Select a project first'); return; }
  toast(`Rendering ${state.currentProject.name}...`);
  try {
    const result = await api('/api/project/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: state.currentProject.name }),
    });
    if (result.status === 'success') {
      toast('Render complete!');
      // Refresh output list and auto-select latest output
      state.output = await api('/api/output');
      renderOutputList();
      // Switch to Output tab and select latest video
      const tabs = document.querySelector('.sidebar-tabs');
      const btns = tabs.querySelectorAll('button');
      btns.forEach(b => b.classList.remove('active'));
      btns[1].classList.add('active');
      document.getElementById('mediaList').style.display = 'none';
      document.getElementById('outputList').style.display = '';
      const latest = [...state.output].reverse().find(f => f.type === 'video');
      if (latest) selectFile(latest);
    } else {
      toast('Render failed: ' + (result.message || 'unknown error'));
    }
  } catch (e) {
    toast('Render error: ' + e.message);
  }
}

// ── Splitter Drag ──
function initSplitters() {
  // Left sidebar splitter
  makeSplitter('splitterLeft', 'sidebarLeft', null, 'horizontal', 160, 400);
  // Right sidebar splitter
  makeSplitter('splitterRight', null, 'sidebarRight', 'horizontal', 180, 400);
  // Timeline splitter
  makeSplitter('splitterTimeline', null, 'timelineArea', 'vertical', 100, 500);
}

function makeSplitter(handleId, beforeId, afterId, dir, min, max) {
  const handle = document.getElementById(handleId);
  let dragging = false;
  handle.addEventListener('pointerdown', (e) => {
    dragging = true;
    handle.setPointerCapture(e.pointerId);
    document.body.style.cursor = dir === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    if (dir === 'horizontal' && beforeId) {
      const el = document.getElementById(beforeId);
      const newW = Math.min(max, Math.max(min, e.clientX));
      el.style.width = newW + 'px';
    } else if (dir === 'horizontal' && afterId) {
      const el = document.getElementById(afterId);
      const newW = Math.min(max, Math.max(min, window.innerWidth - e.clientX));
      el.style.width = newW + 'px';
    } else if (dir === 'vertical' && afterId) {
      const el = document.getElementById(afterId);
      const newH = Math.min(max, Math.max(min, window.innerHeight - e.clientY));
      el.style.height = newH + 'px';
    }
  });
  document.addEventListener('pointerup', () => {
    if (dragging) {
      dragging = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });
}

// ── Toast ──
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// ── Keyboard Shortcuts ──
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && !e.target.matches('input,textarea,select')) {
    e.preventDefault();
    playerAction('play');
  }
  if (e.code === 'ArrowLeft') playerAction('prev');
  if (e.code === 'ArrowRight') playerAction('next');
});

// ── Boot ──
initSplitters();
refreshAll().then(() => {
  // Auto-select first project
  if (state.projects.length > 0) {
    const sel = document.getElementById('projectSelect');
    sel.value = state.projects[0].name;
    loadProject(state.projects[0].name);
  }
  // Auto-select latest output video as preview target
  const latestVideo = [...state.output].reverse().find(f => f.type === 'video');
  if (latestVideo) {
    selectFile(latestVideo);
    // Switch to Output tab
    const tabs = document.querySelector('.sidebar-tabs');
    const btns = tabs.querySelectorAll('button');
    btns.forEach(b => b.classList.remove('active'));
    btns[1].classList.add('active');
    document.getElementById('mediaList').style.display = 'none';
    document.getElementById('outputList').style.display = '';
  }
});
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="vibe-mpeg editor server")
    parser.add_argument("--port", type=int, default=3333)
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    server = ReusableHTTPServer((args.host, args.port), EditorHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"  vibe-mpeg editor")
    print(f"  {url}")
    print(f"  Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
