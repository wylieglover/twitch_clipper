import logging
import subprocess
import time
from pathlib import Path

from config import settings
from app.processing.clips.fetch import get_latest_vod_url
from app.processing.video.spike import detect_audio_spikes

logger = logging.getLogger(__name__)

# Ensure output directory exists
OUTPUT_DIR: Path = settings.vod_output_dir
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_vod(vod_url: str, output_path: Path) -> None:
    """Download a full VOD using streamlink."""
    logger.info("Downloading VOD from %s", vod_url)
    try:
        subprocess.run(
            ["streamlink", vod_url, "best", "-o", str(output_path)],
            check=True
        )
        logger.info("Saved VOD to %s", output_path)
    except subprocess.CalledProcessError as e:
        logger.error("Error downloading VOD from %s: %s", vod_url, e)
        raise RuntimeError(f"Failed to download VOD from {vod_url}") from e


def clip_highlights(vod_path: Path) -> list:
    """Detect audio spikes and create clips around the loudest moments."""
    # Detect spikes
    try:
        spikes = detect_audio_spikes(str(vod_path))
    except Exception as e:
        logger.error("Audio spike detection failed for %s: %s", vod_path, e)
        return []

    if not spikes:
        logger.warning("No spikes detected in %s", vod_path)
        return []

    # Sort by loudness and clip
    spikes = sorted(spikes, key=lambda s: s[1], reverse=True)
    used = set()
    clips = []

    for spike_time, db in spikes:
        if len(clips) >= settings.highlight_max_clips:
            break
        start = max(spike_time - settings.highlight_segment_duration // 2, 0)
        if any(abs(start - u) < settings.highlight_segment_duration for u in used):
            continue
        used.add(start)

        out_path = OUTPUT_DIR / f"vod_highlight_{len(clips)+1}.mp4"
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", str(vod_path),
                "-t", str(settings.highlight_segment_duration),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "fast",
                str(out_path)
            ], check=True)
            logger.info("Clipped highlight at %ds → %s", start, out_path)
            clips.append(str(out_path))
        except subprocess.CalledProcessError as e:
            logger.error("Error clipping highlight at %ds in %s: %s", start, vod_path, e)

    return clips


def process_vod(source: str) -> list:
    """Orchestrate downloading a VOD and extracting highlight clips."""
    vod_url = source if source.startswith("http") else get_latest_vod_url(source)
    if not vod_url:
        logger.error("No VOD URL found for source: %s", source)
        return []

    ts = int(time.time())
    vod_filename = f"full_vod_{ts}.mp4"
    vod_path = OUTPUT_DIR / vod_filename

    download_vod(vod_url, vod_path)
    return clip_highlights(vod_path)