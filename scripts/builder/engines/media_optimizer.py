"""Media optimizer engine for APK size reduction.

Ported from apk-tweak's media_optimizer engine.
Compresses PNG/JPEG images, re-encodes MP3/OGG audio,
and filters DPI-specific drawable resources.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from scripts.builder.engines import EngineContext, EngineResult, EngineStage
from scripts.utils.apk_io import extract_apk, repack_apk

# DPI folders and their Android density values.
DPI_FOLDERS: dict[str, int] = {
    "ldpi": 120,
    "mdpi": 160,
    "hdpi": 240,
    "xhdpi": 320,
    "xxhdpi": 480,
    "xxxhdpi": 640,
    "tvdpi": 213,
    "nodpi": 0,  # Always preserved
}

# Drawable/MIPMAP resource prefixes that contain DPI folders.
_DPI_FOLDER_PREFIXES: tuple[str, ...] = ("drawable-", "mipmap-", "raw-")


def _get_optimal_thread_workers() -> int:
    """Return a reasonable thread worker count for I/O-bound media tasks."""
    return min(32, (os.cpu_count() or 1) + 4)


def _check_dependencies() -> dict[str, bool]:
    """Check availability of optimization tools.

    Returns:
        Dict mapping tool name to availability.
    """
    tools = ["pngquant", "optipng", "jpegoptim", "ffmpeg"]
    return {tool: shutil.which(tool) is not None for tool in tools}


def _find_media_files(
    extract_dir: Path,
    include_images: bool,
    include_audio: bool,
) -> dict[str, list[Path]]:
    """Scan extracted APK for media files.

    Args:
        extract_dir: Directory to scan.
        include_images: Whether to scan for PNG/JPEG files.
        include_audio: Whether to scan for MP3/OGG files.

    Returns:
        Dict with keys 'png', 'jpg', 'audio' containing file paths.
    """
    png_list: list[Path] = []
    jpg_list: list[Path] = []
    audio_list: list[Path] = []

    if not (include_images or include_audio):
        return {"png": [], "jpg": [], "audio": []}

    png_exts = (".png", ".PNG") if include_images else ()
    jpg_exts = (".jpg", ".JPG", ".jpeg", ".JPEG") if include_images else ()
    audio_exts = (".mp3", ".MP3", ".ogg", ".OGG") if include_audio else ()
    valid_exts = png_exts + jpg_exts + audio_exts

    for root, _dirs, files in os.walk(extract_dir):
        root_path = Path(root)
        for file in files:
            if not file.endswith(valid_exts):
                continue
            file_path = root_path / file
            if include_images:
                if file.endswith(png_exts):
                    png_list.append(file_path)
                    continue
                if file.endswith(jpg_exts):
                    jpg_list.append(file_path)
                    continue
            if include_audio and file.endswith(audio_exts):
                audio_list.append(file_path)

    return {"png": png_list, "jpg": jpg_list, "audio": audio_list}


def _optimize_png(path: Path, pngquant_quality: str, optipng_level: int) -> bool:
    """Optimize a single PNG file.

    Prefers pngquant when available; falls back to optipng.

    Args:
        path: PNG file path.
        pngquant_quality: pngquant quality range (e.g., "65-80").
        optipng_level: optipng optimization level (0-7).

    Returns:
        True if optimization succeeded.
    """
    if shutil.which("pngquant"):
        try:
            subprocess.run(
                [
                    "pngquant",
                    f"--quality={pngquant_quality}",
                    "--force",
                    "--skip-if-larger",
                    "--output",
                    str(path),
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    if shutil.which("optipng"):
        try:
            subprocess.run(
                ["optipng", f"-{optipng_level}", str(path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    return False


def _optimize_jpg(path: Path, quality: int) -> bool:
    """Optimize a single JPEG file.

    Args:
        path: JPEG file path.
        quality: Target quality percentage.

    Returns:
        True if optimization succeeded.
    """
    if not shutil.which("jpegoptim"):
        return False
    try:
        subprocess.run(
            ["jpegoptim", f"--size={quality}%", "--strip-all", str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _optimize_audio(path: Path, bitrate: str) -> bool:
    """Re-encode a single MP3 or OGG audio file.

    Args:
        path: Audio file path.
        bitrate: Target bitrate (e.g., "96k").

    Returns:
        True if optimization succeeded.
    """
    if not shutil.which("ffmpeg"):
        return False

    suffix = path.suffix.lower()
    if suffix == ".mp3":
        codec = "libmp3lame"
    elif suffix == ".ogg":
        codec = "libvorbis"
    else:
        return False

    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    temp_file = Path(temp_path)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-codec:a",
                codec,
                "-b:a",
                bitrate,
                str(temp_file),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        if temp_file.exists() and temp_file.stat().st_size > 0:
            shutil.move(str(temp_file), str(path))
            return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    finally:
        temp_file.unlink(missing_ok=True)

    return False


def _filter_dpi_resources(extract_dir: Path, target_dpi: str) -> int:
    """Remove drawable/mipmap resources for non-target DPIs.

    ``nodpi`` is always preserved. Multiple target DPIs can be specified
    comma-separated.

    Args:
        extract_dir: Extracted APK directory.
        target_dpi: Comma-separated list of DPIs to keep.

    Returns:
        Number of directories removed.
    """
    if not target_dpi:
        return 0

    keep_dpis = {dpi.strip().lower() for dpi in target_dpi.split(",")}
    removed = 0

    res_dir = extract_dir / "res"
    if not res_dir.exists():
        return 0

    for entry in res_dir.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name.lower()
        if not any(name.startswith(prefix) for prefix in _DPI_FOLDER_PREFIXES):
            continue

        # Extract DPI qualifier from folder name (e.g., drawable-xxhdpi -> xxhdpi)
        parts = name.split("-")
        if len(parts) < 2:
            continue

        dpi_qualifier = parts[-1]
        # Handle qualifiers like "en-rUS-xxhdpi" where DPI is the last part.
        if dpi_qualifier in DPI_FOLDERS:
            if dpi_qualifier == "nodpi" or dpi_qualifier in keep_dpis:
                continue
            try:
                shutil.rmtree(entry)
                removed += 1
            except OSError:
                pass

    return removed


class MediaOptimizerEngine:
    """Engine that reduces APK size by optimizing media resources."""

    name = "media_optimizer"
    stage = EngineStage.POST_PATCH

    def run(self, ctx: EngineContext) -> EngineResult:
        """Run the media optimizer engine.

        Args:
            ctx: Engine context.

        Returns:
            EngineResult with the optimized APK path.
        """
        options = ctx.app_options.get(self.name, {})
        optimize_images = bool(options.get("optimize_images", False))
        optimize_audio = bool(options.get("optimize_audio", False))
        target_dpi = str(options.get("target_dpi", ""))
        pngquant_quality = str(options.get("pngquant_quality", "65-80"))
        optipng_level = int(options.get("optipng_level", 2))
        jpeg_quality = int(options.get("jpeg_quality", 85))
        audio_bitrate = str(options.get("audio_bitrate", "96k"))

        if not (optimize_images or optimize_audio or target_dpi):
            ctx.log("Media optimizer: nothing to do")
            return EngineResult(success=True, output_apk=ctx.current_apk)

        tools = _check_dependencies()
        missing = [tool for tool, available in tools.items() if not available]
        if missing:
            ctx.log(f"Media optimizer: missing optional tools: {', '.join(missing)}")

        work_dir = ctx.work_dir / self.name
        work_dir.mkdir(parents=True, exist_ok=True)
        extract_dir = work_dir / "extracted"

        ctx.log(f"Media optimizer: extracting {ctx.current_apk.name}")
        if not extract_apk(ctx.current_apk, extract_dir):
            return EngineResult(
                success=False,
                error=f"Failed to extract APK: {ctx.current_apk}",
            )

        if target_dpi:
            removed = _filter_dpi_resources(extract_dir, target_dpi)
            ctx.log(f"Media optimizer: removed {removed} non-target DPI directories")

        stats: dict[str, Any] = {"png": 0, "jpg": 0, "audio": 0, "errors": 0}

        if optimize_images or optimize_audio:
            media = _find_media_files(extract_dir, optimize_images, optimize_audio)

            if optimize_images:
                files = media["png"] + media["jpg"]
                if files:
                    ctx.log(f"Media optimizer: optimizing {len(media['png'])} PNG and {len(media['jpg'])} JPEG files")
                    max_workers = _get_optimal_thread_workers()
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures: dict[Any, str] = {}
                        for path in media["png"]:
                            future = executor.submit(_optimize_png, path, pngquant_quality, optipng_level)
                            futures[future] = "png"
                        for path in media["jpg"]:
                            future = executor.submit(_optimize_jpg, path, jpeg_quality)
                            futures[future] = "jpg"

                        for future in as_completed(futures):
                            kind = futures[future]
                            try:
                                if future.result():
                                    stats[kind] += 1
                            except Exception:
                                stats["errors"] += 1
                else:
                    ctx.log("Media optimizer: no image files found")

            if optimize_audio:
                if media["audio"]:
                    ctx.log(f"Media optimizer: optimizing {len(media['audio'])} audio files")
                    max_workers = _get_optimal_thread_workers()
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {executor.submit(_optimize_audio, path, audio_bitrate): "audio" for path in media["audio"]}
                        for future in as_completed(futures):
                            try:
                                if future.result():
                                    stats["audio"] += 1
                            except Exception:
                                stats["errors"] += 1
                else:
                    ctx.log("Media optimizer: no audio files found")

        output_apk = ctx.output_dir / f"{ctx.current_apk.stem}.media-opt.apk"
        ctx.log(f"Media optimizer: repacking to {output_apk.name}")
        if not repack_apk(extract_dir, output_apk):
            return EngineResult(success=False, error="Failed to repack APK")

        ctx.log(
            f"Media optimizer: done (png={stats['png']}, jpg={stats['jpg']}, "
            f"audio={stats['audio']}, errors={stats['errors']})"
        )

        return EngineResult(success=True, output_apk=output_apk, metadata=stats)
