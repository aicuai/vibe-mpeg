#!/usr/bin/env python3
"""
encoder.py - Encode frame images to video using ffmpeg.
"""

import subprocess
import shutil
from pathlib import Path


def check_ffmpeg() -> str:
    """Find ffmpeg binary. Raises RuntimeError if not found."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found. Install it:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: winget install ffmpeg"
        )
    return ffmpeg


def encode_video(
    frames_dir: str | Path,
    output: str | Path,
    fps: int = 30,
    codec: str = "libx264",
    crf: int = 23,
    pixel_format: str = "yuv420p",
    audio: str | None = None,
    audio_codec: str = "aac",
) -> Path:
    """
    Encode PNG frames to video with ffmpeg.

    Args:
        frames_dir: Directory containing frame_NNNNNN.png files
        output: Output video file path
        fps: Frames per second
        codec: Video codec (libx264, libx265, libvpx-vp9, etc.)
        crf: Constant Rate Factor (quality, lower=better)
        pixel_format: Pixel format
        audio: Optional audio file to mux in
        audio_codec: Audio codec when muxing audio

    Returns:
        Path to output video file
    """
    ffmpeg = check_ffmpeg()
    frames_dir = Path(frames_dir)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",  # Overwrite
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%06d.png"),
    ]

    # Add audio if provided
    if audio:
        cmd.extend(["-i", str(audio), "-c:a", audio_codec, "-shortest"])

    cmd.extend([
        "-c:v", codec,
        "-crf", str(crf),
        "-pix_fmt", pixel_format,
        str(output),
    ])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")

    return output


def concat_videos(
    videos: list[str | Path],
    output: str | Path,
    codec: str = "libx264",
) -> Path:
    """
    Concatenate multiple videos into one using ffmpeg.

    Args:
        videos: List of video file paths
        output: Output video file path
        codec: Video codec for re-encoding

    Returns:
        Path to output video file
    """
    ffmpeg = check_ffmpeg()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Build filter_complex for concat
    inputs = []
    filter_parts = []
    for i, v in enumerate(videos):
        inputs.extend(["-i", str(v)])
        filter_parts.append(f"[{i}:v:0]")

    filter_str = "".join(filter_parts) + f"concat=n={len(videos)}:v=1:a=0[outv]"

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", codec,
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr[-2000:]}")

    return output
