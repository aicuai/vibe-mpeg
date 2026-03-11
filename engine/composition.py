#!/usr/bin/env python3
"""
composition.py - Composition definition and rendering pipeline.

A Composition ties together a template, duration, resolution, and props,
then orchestrates compositor + encoder to produce a video file.
"""

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .compositor import render_frames
from .encoder import encode_video


@dataclass
class Composition:
    """A video composition definition."""
    id: str
    template: str  # Path to HTML template
    duration_seconds: float
    fps: int = 30
    width: int = 1920
    height: int = 1080
    props: dict = field(default_factory=dict)

    @property
    def total_frames(self) -> int:
        return int(self.duration_seconds * self.fps)

    def render(
        self,
        output: str | Path = None,
        codec: str = "libx264",
        crf: int = 23,
        audio: str | None = None,
        keep_frames: bool = False,
    ) -> Path:
        """
        Render this composition to a video file.

        Args:
            output: Output path (default: out/<id>.mp4)
            codec: Video codec
            crf: Quality (lower=better, 0=lossless)
            audio: Optional audio file
            keep_frames: Keep intermediate frame PNGs

        Returns:
            Path to rendered video file
        """
        if output is None:
            output = Path("out") / f"{self.id}.mp4"
        output = Path(output)

        frames_dir = tempfile.mkdtemp(prefix=f"vibe-{self.id}-")

        try:
            # Step 1: Render frames
            print(f"[vibe-mpeg] Rendering {self.total_frames} frames...", file=sys.stderr)
            render_frames(
                template_html=self.template,
                total_frames=self.total_frames,
                fps=self.fps,
                width=self.width,
                height=self.height,
                props=self.props,
                output_dir=frames_dir,
                on_progress=lambda f, t: print(
                    f"\r  Frame {f+1}/{t}", end="", file=sys.stderr
                ) if f % 10 == 0 else None,
            )
            print(file=sys.stderr)

            # Step 2: Encode to video
            print(f"[vibe-mpeg] Encoding to {output}...", file=sys.stderr)
            encode_video(
                frames_dir=frames_dir,
                output=output,
                fps=self.fps,
                codec=codec,
                crf=crf,
                audio=audio,
            )

            print(f"[vibe-mpeg] Done: {output} ({output.stat().st_size / 1024:.1f} KB)", file=sys.stderr)
            return output

        finally:
            if not keep_frames:
                shutil.rmtree(frames_dir, ignore_errors=True)
