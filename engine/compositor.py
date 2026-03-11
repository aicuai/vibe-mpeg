#!/usr/bin/env python3
"""
compositor.py - Frame-by-frame HTML renderer using Playwright.

Renders an HTML template for each frame, capturing screenshots.
The template receives frame number, fps, and composition data as JS globals.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path


def render_frames(
    template_html: str,
    total_frames: int,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    props: dict | None = None,
    output_dir: str | None = None,
    on_progress: callable = None,
) -> Path:
    """
    Render an HTML template frame-by-frame to PNG images.

    Args:
        template_html: Path to HTML template or HTML string
        total_frames: Total number of frames to render
        fps: Frames per second
        width: Video width in pixels
        height: Video height in pixels
        props: Data passed to the template as window.__VIBE_PROPS__
        output_dir: Directory for frame PNGs (auto-created if None)
        on_progress: Callback(frame_num, total_frames) for progress

    Returns:
        Path to directory containing frame_NNNNNN.png files
    """
    from playwright.sync_api import sync_playwright

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="vibe-frames-")
    else:
        os.makedirs(output_dir, exist_ok=True)

    output_path = Path(output_dir)

    # Resolve template
    if os.path.isfile(template_html):
        template_path = Path(template_html).resolve()
        template_url = f"file://{template_path}"
    else:
        # Write HTML string to temp file
        tmp = output_path / "_template.html"
        tmp.write_text(template_html)
        template_url = f"file://{tmp.resolve()}"

    props_json = json.dumps(props or {})

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})

        # Inject vibe-mpeg globals before page load
        init_script = f"""
            window.__VIBE_FPS__ = {fps};
            window.__VIBE_TOTAL_FRAMES__ = {total_frames};
            window.__VIBE_PROPS__ = {props_json};
            window.__VIBE_FRAME__ = 0;
        """
        page.add_init_script(init_script)
        page.goto(template_url, wait_until="networkidle")

        for frame_num in range(total_frames):
            # Update frame number
            page.evaluate(f"""() => {{
                window.__VIBE_FRAME__ = {frame_num};
                if (typeof window.__VIBE_RENDER_FRAME__ === 'function') {{
                    window.__VIBE_RENDER_FRAME__({frame_num});
                }}
                // Dispatch event for templates using event listeners
                window.dispatchEvent(new CustomEvent('vibe-frame', {{
                    detail: {{ frame: {frame_num}, fps: {fps}, total: {total_frames} }}
                }}));
            }}""")

            # Small wait for animations to settle
            page.wait_for_timeout(16)

            # Screenshot
            frame_file = output_path / f"frame_{frame_num:06d}.png"
            page.screenshot(path=str(frame_file))

            if on_progress:
                on_progress(frame_num, total_frames)

        browser.close()

    return output_path
