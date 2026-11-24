from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap


@dataclass
class VideoProbeInfo:
  """Probed metadata for a video file.

  :param path: Full path to the video file.
  :param filename: File basename.
  :param size_bytes: Size in bytes.
  :param size_human: Human-readable size.
  :param duration_seconds: Duration in seconds (0 if unknown).
  :param duration_human: Formatted duration string (e.g. '00:15').
  :param is_valid: Whether the file is a valid, supported video.
  :param validation_message: Human-readable validation status.
  """

  path: Path
  filename: str
  size_bytes: int
  size_human: str
  duration_seconds: float
  duration_human: str
  is_valid: bool
  validation_message: str


class VideoMediaUtils:
  """Helper utilities for probing video files and generating thumbnails."""

  SUPPORTED_EXTENSIONS: set[str] = {".mp4", ".mov", ".webm", ".mkv"}

  @classmethod
  def probe_video(cls, path: Path) -> VideoProbeInfo:
    """Inspect a video file, validate format/size, and probe duration.

    :param path: Path to video file.
    :return: VideoProbeInfo instance.
    """
    filename = path.name
    if not path.exists() or not path.is_file():
      return VideoProbeInfo(
        path=path,
        filename=filename,
        size_bytes=0,
        size_human="0 B",
        duration_seconds=0.0,
        duration_human="--:--",
        is_valid=False,
        validation_message="File not found",
      )

    size_bytes = path.stat().st_size
    size_human = cls.format_size(size_bytes)
    suffix = path.suffix.lower()

    if suffix not in cls.SUPPORTED_EXTENSIONS:
      return VideoProbeInfo(
        path=path,
        filename=filename,
        size_bytes=size_bytes,
        size_human=size_human,
        duration_seconds=0.0,
        duration_human="--:--",
        is_valid=False,
        validation_message=f"Unsupported format ({suffix or 'none'})",
      )

    if size_bytes == 0:
      return VideoProbeInfo(
        path=path,
        filename=filename,
        size_bytes=0,
        size_human="0 B",
        duration_seconds=0.0,
        duration_human="--:--",
        is_valid=False,
        validation_message="Empty file (0 bytes)",
      )

    duration_sec = cls._probe_duration(path)
    duration_human = cls.format_duration(duration_sec) if duration_sec > 0 else "00:05"
    return VideoProbeInfo(
      path=path,
      filename=filename,
      size_bytes=size_bytes,
      size_human=size_human,
      duration_seconds=duration_sec,
      duration_human=duration_human,
      is_valid=True,
      validation_message="Compatible (Ready)",
    )

  @classmethod
  def get_thumbnail(
    cls,
    path: Path,
    cache_dir: Path | None = None,
    width: int = 96,
    height: int = 64,
  ) -> QPixmap:
    """Extract or synthesize a thumbnail pixmap for a video file.

    :param path: Path to video file.
    :param cache_dir: Optional directory to cache extracted PNG thumbnails.
    :param width: Target width.
    :param height: Target height.
    :return: QPixmap thumbnail.
    """
    if cache_dir is not None and path.exists():
      try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.md5(f"{path.resolve()}_{path.stat().st_mtime}".encode("utf-8")).hexdigest()[:16]
        thumb_path = cache_dir / f"thumb_{digest}.png"
        if not thumb_path.exists() and shutil.which("ffmpeg"):
          subprocess.run(
            [
              "ffmpeg",
              "-y",
              "-ss",
              "00:00:00.200",
              "-i",
              str(path),
              "-frames:v",
              "1",
              "-vf",
              f"scale={width}:{height}:force_original_aspect_ratio=decrease",
              str(thumb_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
          )
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
          pix = QPixmap(str(thumb_path))
          if not pix.isNull():
            return pix.scaled(
              width,
              height,
              Qt.AspectRatioMode.KeepAspectRatioByExpanding,
              Qt.TransformationMode.SmoothTransformation,
            )
      except Exception:
        pass

    return cls._build_fallback_thumbnail(path.name, width, height)

  @staticmethod
  def _build_fallback_thumbnail(label_text: str, width: int, height: int) -> QPixmap:
    """Create a sleek dark gradient thumbnail card with a play badge."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor("#1e293b"))
    grad.setColorAt(1.0, QColor("#0f172a"))
    painter.setBrush(grad)
    painter.setPen(QColor("#334155"))
    painter.drawRoundedRect(1, 1, width - 2, height - 2, 8, 8)

    painter.setPen(QColor("#38bdf8"))
    font = QFont("Segoe UI", 9, QFont.Weight.Bold)
    painter.setFont(font)
    short = Path(label_text).stem[:8].upper()
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, f"▶ {short}")
    painter.end()
    return pixmap

  @staticmethod
  def _probe_duration(path: Path) -> float:
    """Probe video duration in seconds using ffprobe if available."""
    if not shutil.which("ffprobe"):
      return 0.0
    try:
      proc = subprocess.run(
        [
          "ffprobe",
          "-v",
          "error",
          "-show_entries",
          "format=duration",
          "-of",
          "default=noprint_wrappers=1:nokey=1",
          str(path),
        ],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
      )
      val = proc.stdout.strip()
      if val:
        return max(0.0, float(val))
    except Exception:
      pass
    return 0.0

  @staticmethod
  def format_duration(seconds: float) -> str:
    """Format duration seconds as MM:SS or HH:MM:SS."""
    total = max(0, int(round(seconds)))
    mins, secs = divmod(total, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
      return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

  @staticmethod
  def format_size(size_bytes: int) -> str:
    """Format byte size into human-readable string."""
    if size_bytes < 1024:
      return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
      return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
      return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
